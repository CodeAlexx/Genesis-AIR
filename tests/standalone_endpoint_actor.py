"""Actual background actor lifecycle; authored PCM and independent DSP references.

No candidate audio is an oracle input. This gate exercises the existing 26-request
AIR actor fixture, not device playback or the GUI loop. Optional cold cancellation
requires externally observed RF64 samples before cancellation is admitted.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time
import wave

import numpy as np

from audio_mix_project import document
from audio_nested import effect
from media_runtime import tool
from standalone_endpoint_media import BODY, SR, compare, pcm, quantize, run, sha

# Identical independently declared Delay reference to standalone_endpoint_media:
# time=350ms, decay=.4, input gain=.8, output gain=.9, explicit packed48k stereo.
DELAY = "aecho=0.8:0.9:350:0.4"
WHOLE_OUTPUTS = ("whole-first.wav", "recovered.wav", "loop1.wav",
                 "loop2.wav", "after-source.wav")


def require(value, detail):
    if not value:
        raise AssertionError(detail)


def process_rows():
    """Read only process ownership, never inspect or control unrelated apps."""
    if os.name != "nt":
        rows = []
        for folder in Path("/proc").iterdir():
            if not folder.name.isdigit():
                continue
            try:
                fields = (folder / "stat").read_text().rsplit(")", 1)[1].split()
                rows.append((int(folder.name), int(fields[1]),
                             Path(os.readlink(folder / "exe")).name))
            except (OSError, ValueError):
                pass
        return rows
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
                    ("heap", ctypes.c_size_t), ("module", w.DWORD),
                    ("threads", w.DWORD), ("parent", w.DWORD),
                    ("priority", w.LONG), ("flags", w.DWORD),
                    ("exe", w.WCHAR * 260)]
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    api.CreateToolhelp32Snapshot.restype = w.HANDLE
    api.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    api.Process32NextW.argtypes = api.Process32FirstW.argtypes
    api.CloseHandle.argtypes = [w.HANDLE]
    handle = api.CreateToolhelp32Snapshot(2, 0)
    require(handle not in (None, ctypes.c_void_p(-1).value), "process snapshot")
    entry = Entry()
    entry.size = ctypes.sizeof(entry)
    rows = []
    try:
        more = api.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            rows.append((entry.pid, entry.parent, entry.exe))
            more = api.Process32NextW(handle, ctypes.byref(entry))
    finally:
        api.CloseHandle(handle)
    return rows


class OwnedWorkers:
    """Retain OS process identities so observed worker exit cannot be inferred
    merely from cache deletion or a successful client exit."""
    def __init__(self, parent, worker):
        self.parent, self.worker = parent, worker
        self.handles = {}
        self.using_pidfd = hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal")
        if os.name == "nt":
            from ctypes import wintypes as w
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            self.api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
            self.api.OpenProcess.restype = w.HANDLE
            self.api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
            self.api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
            self.api.CloseHandle.argtypes = [w.HANDLE]

    def observe(self):
        rows = process_rows()
        parents = {self.parent}
        while True:
            expanded = parents | {pid for pid, parent, _ in rows if parent in parents}
            if expanded == parents:
                break
            parents = expanded
        for pid, parent, name in rows:
            if parent not in parents or name != self.worker.name or pid in self.handles:
                continue
            if os.name == "nt":
                handle = self.api.OpenProcess(0x100001, False, pid)
                if handle:
                    self.handles[pid] = handle
            elif self.using_pidfd:
                try:
                    self.handles[pid] = os.pidfd_open(pid)
                except ProcessLookupError:
                    pass
            else:
                # Bootstrap Linux gate uses /proc; starttime guards PID reuse.
                try:
                    self.handles[pid] = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
                except OSError:
                    pass

    def joined(self):
        require(self.handles, "No actual owned worker process observed")
        for pid, handle in self.handles.items():
            if os.name == "nt":
                require(self.api.WaitForSingleObject(handle, 0) == 0,
                        ("owned worker still live", pid))
            elif self.using_pidfd:
                require(bool(select.select([handle], [], [], 0)[0]),
                        ("owned worker still live", pid))
            else:
                try:
                    current = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
                except OSError:
                    current = None
                require(current != handle, ("owned worker still live", pid))
        return sorted(self.handles)

    def terminate_live(self):
        """Failure only: use retained HANDLE/pidfd identities, or recheck the
        original /proc starttime immediately before the fallback PID signal.
        Return every cleanup error so an original client failure stays primary."""
        outcomes = []
        for pid, handle in self.handles.items():
            outcome = dict(pid=pid, terminated=False, exited=False)
            try:
                if os.name == "nt":
                    status = self.api.WaitForSingleObject(handle, 0)
                    if status == 258:
                        require(self.api.TerminateProcess(handle, 1), ("TerminateProcess", pid))
                        outcome["terminated"] = True
                    require(self.api.WaitForSingleObject(handle, 5000) == 0, ("worker cleanup join", pid))
                elif self.using_pidfd:
                    if not select.select([handle], [], [], 0)[0]:
                        try:
                            signal.pidfd_send_signal(handle, signal.SIGKILL)
                            outcome["terminated"] = True
                        except ProcessLookupError:
                            pass
                    require(bool(select.select([handle], [], [], 5)[0]), ("worker cleanup join", pid))
                else:
                    def still_owned():
                        try:
                            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                            return fields[19] == handle and fields[0] != "Z"
                        except OSError:
                            return False
                    if still_owned():
                        try:
                            os.kill(pid, signal.SIGKILL)
                            outcome["terminated"] = True
                        except ProcessLookupError:
                            pass
                    deadline = time.monotonic() + 5
                    while still_owned() and time.monotonic() < deadline:
                        time.sleep(.002)
                    require(not still_owned(), ("worker cleanup join", pid))
                outcome["exited"] = True
            except BaseException as error:
                outcome["error"] = repr(error)
            outcomes.append(outcome)
        return outcomes

    def close(self):
        for handle in self.handles.values():
            if os.name == "nt":
                self.api.CloseHandle(handle)
            elif self.using_pidfd:
                os.close(handle)


def terminate_owned(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=10, creationflags=0x08000000)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=10)


def client_run(client, worker, args, folder, cold=False):
    folder.mkdir()
    process = None
    owned = None
    succeeded = False
    result = dict(client_sha256=sha(client), argv=list(map(str, [client, worker, *args, folder])),
                  cold_witness_required=cold)
    try:
        with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(result["argv"], stdout=stdout, stderr=stderr,
                                       creationflags=0x08000000 if os.name == "nt" else 0,
                                       start_new_session=os.name != "nt")
            owned = OwnedWorkers(process.pid, worker)
            deadline = time.monotonic() + 90
            while process.poll() is None:
                owned.observe()
                if cold and "observed_rf64" not in result:
                    require(not (folder / "endpoint.air").exists(),
                            "Cold preparation completed before cancellation witness")
                    for item in folder.rglob("*.rf64"):
                        try:
                            size = item.stat().st_size
                            with item.open("rb") as audio:
                                magic = audio.read(4)
                        except OSError:
                            continue
                        if size > 1048576 and magic == b"RF64":
                            require(owned.handles, "Cold RF64 without observed owned worker")
                            result["observed_rf64"] = dict(path=str(item.relative_to(folder)),
                                                          bytes=size, magic="RF64")
                            (folder / "cancel-now").write_bytes(b"cancel")
                            break
                require(time.monotonic() < deadline, "Actor process deadline")
                time.sleep(.002)
            result["exit_code"] = process.wait(timeout=5)
        require(result["exit_code"] == 0,
                ("actor failed", result["exit_code"], (folder / "stdout.log").read_text(errors="replace"),
                 (folder / "stderr.log").read_text(errors="replace")))
        if cold:
            require("observed_rf64" in result, "No independently witnessed cold RF64")
        result["observed_worker_pids_joined"] = owned.joined()
        result["actor_joined"] = True
        succeeded = True
        return result
    except BaseException as error:
        result["failure"] = repr(error)
        raise
    finally:
        if process is not None and process.poll() is None:
            try:
                terminate_owned(process)
            except BaseException as error:
                result["parent_cleanup_error"] = repr(error)
        if owned is not None:
            if not succeeded:
                result["failed_run_worker_cleanup"] = owned.terminate_live()
            owned.close()
        (folder / "process.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")


def descriptor(path, actual, muted=False):
    lines = path.read_text().splitlines()
    fields = lines[0].split()
    require(len(fields) == 6 and fields[0] == "END1", (path.name, fields))
    require((int(fields[2]), int(fields[3]), int(fields[4]), float(fields[5])) ==
            (BODY, actual, (max(BODY, actual) + 1599) // 1600, 30.), (path.name, fields))
    if muted:
        require(int(fields[1]) == 0 and len(lines) == 1, "Muted endpoint retains graph")
    else:
        require(int(fields[1]) > 0 and len(lines) == 2, "Missing accepted root")
        root = lines[1].split()
        require(root[0] == "n20" and tuple(map(int, root[1:])) == (0, BODY, actual, 1), root)
    return dict(path=str(path), sha256=sha(path), header=fields)


def clean(folder):
    remaining = list(folder.rglob("*.rf64")) + list(folder.rglob(".genesis-nested-*"))
    require(not remaining, ("owned cache retained", [str(p) for p in remaining]))
    for name in ("refused.wav", "unreceived.wav", "unused.wav", "prepare.wav", "audio-cleanup-error.txt"):
        require(not (folder / name).exists(), ("unexpected output", name))
    require((folder / "stop").exists(), "Actor did not publish terminal stop")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--cancel-client", type=Path)
    args = parser.parse_args()
    worker, client = args.worker.resolve(), args.client.resolve()
    work = (args.work or args.report.with_suffix("")).resolve()
    require(not work.exists() and not args.report.exists(), "Exclusive output already exists")
    work.mkdir(parents=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = dict(schema="genesis.standalone_endpoint_actor.v1", passed=False, failures=[],
                  worker_sha256=sha(worker), client_sha256=sha(client), checker_sha256=sha(__file__),
                  fixture_sha256=sha(Path(__file__).with_name("standalone_endpoint_actor_lifecycle.ai")),
                  reference_policy="Authored PCM16 -> independent MM-AIR ordered Delay actual EOF; Source from independent original WAV decode",
                  pcm_threshold_codes=1, requested_actor_requests=26, pcm=[],
                  scope="Actual background actor lifecycle/replay/Source; no device, GUI or physical listening claim",
                  cold_cancel=dict(executed=False, status="not requested"))
    try:
        inputs = work / "inputs"
        inputs.mkdir()
        t = np.arange(BODY) / SR
        amplitude = np.where(t < .45, .18, np.where(t < 1.55, .025, .24))
        raw = np.column_stack((amplitude * np.sin(2*np.pi*173*t),
                               .79*amplitude*np.cos(2*np.pi*317*t)))
        authored = np.rint(raw*32767).astype("<i2")
        source = inputs / "original.wav"
        with wave.open(str(source), "wb") as output:
            output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
            output.writeframes(authored.tobytes())
        graph = document([source], (0,))
        graph["sources"][0]["frames"] = 60
        graph["clips"][0].update(length=60, streams=2)
        effect(graph, 20, "delay", dict(time=350, decay=.4), 50)
        project = inputs / "input.air"
        project.write_text(json.dumps(graph), encoding="utf8")
        protected = {str(p): sha(p) for p in (source, project)}
        ffmpeg = tool(worker, "ffmpeg")
        report["ffmpeg_sha256"] = sha(ffmpeg)
        data = run([ffmpeg, "-nostdin", "-v", "error", "-f", "f32le", "-ar", SR,
                    "-ac", 2, "-i", "pipe:0", "-af", DELAY +
                    ",aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo",
                    "-f", "f32le", "pipe:1"], input=(authored.astype(np.float32)/32768).astype("<f4").tobytes())
        full = np.frombuffer(data, dtype="<f4").reshape(-1, 2).copy()
        require(np.isfinite(full).all() and BODY < len(full) <= BODY + 5*SR,
                "Independent original EOF outside declared bounds")
        require(np.count_nonzero(full[BODY:]) > 100, "No meaningful independently audible tail")
        reference = inputs / "delay-reference.f32"
        reference.write_bytes(data)
        original = run([ffmpeg, "-nostdin", "-v", "error", "-i", source, "-vn", "-ar", SR,
                        "-ac", 2, "-f", "f32le", "pipe:1"])
        native = np.frombuffer(original, dtype="<f4").reshape(-1, 2)
        require(native.shape == (BODY, 2), "Independent Source decode count")
        report.update(authored_source_sha256=protected[str(source)], project_sha256=protected[str(project)],
                      reference_sha256=sha(reference), authored_frames=BODY, actual_eof=len(full),
                      nonzero_tail_values=int(np.count_nonzero(full[BODY:])))
        folder = work / "actor"
        report["actor"] = client_run(client, worker, [project], folder)
        report["descriptors"] = [descriptor(folder / "first-end.air", len(full)),
                                 descriptor(folder / "endpoint.air", len(full)),
                                 descriptor(folder / "muted-end.air", 0, muted=True)]
        expectations = {name: quantize(full) for name in WHOLE_OUTPUTS}
        expectations.update({"gain-edited.wav": quantize(full * np.float32(.5)),
                             "tail-first.wav": quantize(full[BODY+17:BODY+17+4093]),
                             "source.wav": quantize(native[:10*1600])})
        for name, expected in expectations.items():
            count, error = compare(pcm(folder / name), expected, name)
            report["pcm"].append(dict(file=name, values=count, max_error_codes=error,
                                      sha256=sha(folder / name)))
        require(set(p.name for p in folder.glob("*.wav")) == set(expectations), "Unexpected or missing PCM outputs")
        require((folder / "request.id").read_text().strip() == "26", "Not all26 requests completed")
        require((folder / "request.air").read_text().splitlines()[0].split() == ["26", "12", "0"],
                "Final discard/generation identity")
        clean(folder)
        report.update(requests=26, pcm_values=sum(v["values"] for v in report["pcm"]),
                      max_error_codes=max(v["max_error_codes"] for v in report["pcm"]),
                      completed_before_gui_receipt_retired=True, cache_cleanup=True)
        if args.cancel_client:
            # A bounded authored300-second source permits an externally observed
            # cold cache; no protected long media, production barrier or fake delay.
            long_source = inputs / "cold.wav"
            with wave.open(str(long_source), "wb") as output:
                output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
                for _ in range(150):
                    output.writeframesraw(authored.tobytes())
            cold_graph = json.loads(json.dumps(graph))
            cold_graph["sources"][0].update(path=str(long_source), name=long_source.name, frames=9000)
            cold_graph["clips"][0]["length"] = 9000
            cold_project = inputs / "cold.air"
            cold_project.write_text(json.dumps(cold_graph), encoding="utf8")
            protected.update({str(p): sha(p) for p in (long_source, cold_project)})
            cold_folder = work / "cold-cancel"
            report["cold_cancel"] = client_run(args.cancel_client.resolve(), worker,
                                               [cold_project, project], cold_folder, cold=True)
            clean(cold_folder)
            count, error = compare(pcm(cold_folder / "recovery.wav"), quantize(full), "cold recovery")
            ack = int((cold_folder / "cancel-ns.txt").read_text())
            require(0 < ack <= 2000000000, ("cold cancellation acknowledgement", ack))
            report["cold_cancel"].update(executed=True, passed=True, status="passed",
                                         acknowledgement_ns=ack, recovery_pcm_values=count,
                                         recovery_max_error_codes=error, cache_cleanup=True,
                                         fixture_sha256=sha(Path(__file__).with_name("standalone_endpoint_cancel.ai")))
        require({name: sha(Path(name)) for name in protected} == protected, "Authored input bytes changed")
        report.update(inputs_unchanged=True, protected_inputs=protected, passed=True)
    except BaseException as error:
        report["failures"].append(repr(error))
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(f"Standalone actor:26 requests, {report['pcm_values']} independent PCM values, "
          f"max{report['max_error_codes']}code; owned workers joined, cache cleaned", flush=True)


if __name__ == "__main__":
    main()
