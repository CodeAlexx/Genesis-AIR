"""Cuts must retain ordered Delay/Reverb DSP and own its actual EOF tail once.

The independent reference runs authored PCM through shared MM-AIR FFmpeg to
actual EOF, without a Genesis cache, body cap, output padding or candidate input.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import tempfile
import time
import wave

import numpy as np
from audio_mix_project import document
from audio_nested import effect
from media_runtime import tool
from audio_nested_cancel import children, image, worker_handle, handle_alive, terminate_children

SR = 48000
SPF = 1600
BODY = 60 * SPF
TOTAL = 180 * SPF
FLAGS = 0x08000000 if os.name == "nt" else 0
SEGMENTS = {
    # Original frame offset, surviving body length, destination start, final owner.
    "unedited": [(0, 60, 0, True)],
    "split": [(0, 30, 0, False), (30, 30, 30, True)],
    "head": [(15, 45, 15, True)],
    "interior": [(0, 15, 0, False), (45, 15, 45, True)],
    "tail": [(0, 30, 0, False)],
    "moved": [(0, 30, 0, False), (30, 30, 60, True)],
    "repeated": [(0, 30, 0, False), (40, 15, 40, False)],
    "saveopen": [(0, 30, 0, False), (30, 30, 30, True)],
}
MASTER_VARIANTS = ("unedited", "split", "head", "tail", "moved")


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def run(argv, **kwargs):
    p = subprocess.run(list(map(str, argv)), capture_output=True, timeout=180,
                       creationflags=FLAGS, **kwargs)
    assert p.returncode == 0, (argv, p.returncode, p.stdout[-2000:], p.stderr[-2000:])
    return p.stdout


def pcm(path):
    with wave.open(str(path), "rb") as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate()) == (2, 2, SR)
        return np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").reshape(-1, 2).copy()


def quantize(v):
    return (np.sign(v) * np.floor(np.abs(np.clip(v, -1, 1)) * 32767 + .5)).astype(np.int16)


def compare(actual, expected, label):
    assert actual.shape == expected.shape, (label, actual.shape, expected.shape)
    assert np.all(np.isfinite(actual)) and np.all(np.isfinite(expected)), (label, "nonfinite PCM")
    error = int(np.max(np.abs(actual.astype(np.int32) - expected.astype(np.int32)), initial=0))
    assert error <= 1, (label, "PCM16 error", error)
    return actual.size, error


def target(full, variant):
    out = np.zeros((TOTAL, 2), dtype=np.float32)
    for offset, length, start, final in SEGMENTS[variant]:
        out[start*SPF:(start+length)*SPF] += full[offset*SPF:(offset+length)*SPF]
        if final:
            tail = full[BODY:]
            begin = (start+length)*SPF
            out[begin:begin+len(tail)] += tail
    return out



def master_target(full, variant):
    # Unmarked export allocates through the accepted audible EOF, while the
    # silent timeline filler still declares all 180 video frames. This endpoint
    # is derived solely from the independent original DSP output and authored
    # surviving-piece geometry, never from the candidate master or signal level.
    assert BODY < len(full) <= BODY + 5*SR
    tail_frames = len(full) - BODY
    audible_end = max((start+length)*SPF + (tail_frames if final else 0)
                      for _, length, start, final in SEGMENTS[variant])
    assert 0 < audible_end <= TOTAL, (variant, "independent audible EOF outside timeline", audible_end)
    return target(full, variant)[:audible_end]


def graph_check(doc, variant, authored):
    audio = sorted((c for c in doc["clips"] if c["source"] == 7), key=lambda c: c["start"])
    expected = SEGMENTS[variant]
    assert len(audio) == len(expected), (variant, "clip count")
    filters = authored["filters"]
    for clip, (offset, length, start, _) in zip(audio, expected):
        assert (clip["length"], clip["start"], clip["source_in"], clip["streams"],
                clip["speed"], clip["reverse"], clip["gain"]) == (length, start, offset, 2, 1, False, 1)
        context = clip.get("audio_context")
        if variant == "unedited":
            assert context is None, "unedited legacy graph gained context"
        else:
            assert context is not None, (variant, "durable DSP context missing")
            for key, value in dict(source_in=0, length=60, offset=offset, fps=30, rate=1,
                                   reverse=False, origin=0, crop_start=offset*SPF,
                                   output_frames=BODY).items():
                assert context[key] == value, (variant, key, context[key], value)
            assert context.get("extent") is None
        owned = sorted((f for f in doc["filters"] if f["clip"] == clip["id"]), key=lambda f: f["order"])
        assert [(f["kind"], f["enabled"], f["order"]) for f in owned] == [
            (f["kind"], f["enabled"], f["order"]) for f in filters]
        for original, actual in zip(filters, owned):
            a = sorted((p["name"], p["value"]) for p in authored["filter_params"] if p["filter"] == original["id"])
            b = sorted((p["name"], p["value"]) for p in doc["filter_params"] if p["filter"] == actual["id"])
            assert a == b, (variant, "ordered filter parameters changed", a, b)
    assert len({f["id"] for f in doc["filters"]}) == len(doc["filters"])
    assert doc["keys"] == authored["keys"] and doc["filter_text_params"] == authored["filter_text_params"]
    if variant != "unedited":
        assert doc["revision"] == 3, (variant, "context codec revision")


def cancellation(root, client, worker, recovery, reference):
    source = root/"30-minute-cold-original.wav"
    size = SR*1800*4
    with source.open("wb") as f:
        f.write(struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", size+36, b"WAVE", b"fmt ",
                            16, 1, 2, SR, SR*4, 4, 16, b"data", size))
        f.seek(44+size-1); f.write(b"\0")
    doc = document([source], (0,))
    doc["sources"][0].update(frames=54000)
    doc["clips"][0].update(length=54000, streams=2)
    doc["next_id"] = 100
    effect(doc, 20, "delay", dict(time=350, decay=.4))
    source_hash = sha(source)
    rows = []
    for mode in ("superseded", "stop"):
        owned = root/("cancel-"+mode); owned.mkdir()
        project = owned/"cancel.air"; project.write_text(json.dumps(doc), encoding="utf8")
        short = owned/"recovery.air"; short.write_text(json.dumps(recovery), encoding="utf8")
        originals = {p.name: sha(p) for p in (project, short)}
        marker = owned/"request.id"; marker.write_text("1")
        process = subprocess.Popen(list(map(str, [client, worker, owned, "--cancel"])),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=FLAGS)
        handle = None
        try:
            deadline = time.monotonic()+20
            witness = None
            while witness is None:
                assert process.poll() is None, (mode, "cold render ended before real cache witness")
                assert time.monotonic() < deadline, (mode, "cold cache witness deadline")
                for candidate in owned.rglob("*.rf64"):
                    try:
                        if candidate.stat().st_size >= 80+5*SR*8:
                            witness = candidate
                            break
                    except OSError:
                        pass
                if witness is None:
                    time.sleep(.002)
            pids = [pid for pid in children(process.pid) if image(pid) == worker]
            assert len(pids) == 1, (mode, "exact test-owned worker", pids)
            handle = worker_handle(pids[0]); started = time.monotonic()
            if mode == "stop":
                (owned/"stop").write_text("stop")
            else:
                marker.write_text("2")
            stdout, stderr = process.communicate(timeout=10)
            elapsed = time.monotonic()-started
            (owned/"stdout.log").write_bytes(stdout); (owned/"stderr.log").write_bytes(stderr)
            assert process.returncode == 0, (mode, process.returncode, stdout, stderr)
            assert "GA_AUDIO_STREAM_CANCELLED" in (owned/"cancel-result.txt").read_text()
            assert elapsed <= 2.5 and not handle_alive(handle), (mode, elapsed, "old worker not joined")
            assert not (owned/"cancelled.wav").exists()
            assert not list(owned.rglob("*.rf64")) and not list(owned.rglob(".genesis-nested-*"))
            count, error = compare(pcm(owned/"recovered.wav"), quantize(reference[:15*SPF]), mode+" fresh recovery")
            assert all(sha(owned/name) == value for name, value in originals.items())
            rows.append(dict(mode=mode, actual_cache_warm_frames_at_least=5*SR,
                             cancel_and_independent_recovery_seconds=elapsed, worker_joined=True,
                             unpublished_output_absent=True, owned_cache_removed=True,
                             recovery_pcm_values=count, recovery_max_error=error))
        finally:
            if process.poll() is None:
                (owned/"stop").write_text("stop")
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate_children(process.pid, worker)
                    process.kill(); process.communicate(timeout=5)
            if handle is not None and os.name == "nt":
                import ctypes
                kernel = ctypes.WinDLL("kernel32")
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel.CloseHandle(handle)
    assert sha(source) == source_hash
    return dict(cases=rows, source_sha256=source_hash, source_frames=54000)


def check(args, root):
    worker, client = args.worker.resolve(), args.client.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    report = dict(schema="genesis.audio-tail-history.v1", passed=False, cases=[], masters=[],
                  thresholds=dict(pcm16_codes=1, lossless_float=2e-6, actual_tail_seconds=5),
                  reference="Original authored 48k PCM -> ordered MM-AIR DSP -> actual EOF; analytic body crops and original-end-only tail ownership",
                  worker_sha256=sha(worker), client_sha256=sha(client), ffmpeg_sha256=sha(ffmpeg),
                  checker_sha256=sha(__file__), fixture_sha256=sha(Path(__file__).with_suffix(".ai")),
                  work_root=str(root), mode="unedited-only" if args.unedited_only else "pcm-only" if args.skip_masters else "complete",
                  witnesses=[])
    try:
        t = np.arange(BODY) / SR
        # Distinct channels and the final nonzero pulse expose echo beyond the
        # original end; a quiet middle exposes compressor release/order history.
        amp = np.where(t < .45, .18, np.where(t < 1.55, .025, .24))
        raw = np.column_stack((amp*np.sin(2*np.pi*173*t), .79*amp*np.cos(2*np.pi*317*t)))
        encoded = np.rint(raw*32767).astype("<i2")
        source = root / "authored-stereo.wav"
        with wave.open(str(source), "wb") as f:
            f.setparams((2, 2, SR, 0, "NONE", "not compressed")); f.writeframes(encoded.tobytes())
        report["source_sha256"] = sha(source)
        compressor = ("compressor", dict(threshold=-18, ratio=4, attack=12, release=250),
                      "acompressor=threshold="+str(10**(-18/20))+":ratio=4:attack=12:release=250")
        delay = ("delay", dict(time=350, decay=.4), "aecho=0.8:0.9:350:0.4")
        reverb = ("reverb", dict(amount=.35, room=.8),
                  "aecho=0.8:0.9:61|126|196|274:0.175|0.14|0.105|0.07")
        specs = [("delay", [delay]), ("reverb", [reverb]),
                 ("delay-compressor", [delay, compressor]), ("compressor-delay", [compressor, delay])]
        references, projects, project_hashes = {}, {}, {}
        for name, effects in specs:
            doc = document([source], (0,))
            doc["sources"][0].update(frames=60)
            doc["clips"][0].update(length=60, streams=2)
            # This silent clip declares a longer timeline so the actual original
            # EOF tail is audible after the source clip, including fresh seeks.
            silent_source = copy.deepcopy(doc["sources"][0])
            silent_source.update(id=8, frames=180, has_audio=False)
            tr = copy.deepcopy(doc["tracks"][0]); tr.update(id=4, order=1)
            silent = copy.deepcopy(doc["clips"][0]); silent.update(id=21, source=8, track=4, length=180)
            doc["sources"].append(silent_source); doc["tracks"].append(tr); doc["clips"].append(silent)
            for order, (kind, values, _) in enumerate(effects):
                effect(doc, 20, kind, values, 50+order); doc["filters"][-1]["order"] = order
            doc["next_id"] = 100
            path = root / (name+".air")
            path.write_text(json.dumps(doc), encoding="utf8")
            projects[name] = doc; project_hashes[name] = sha(path)
            # No Genesis output, cache or end trim enters this independent graph.
            chain = ",".join(s[2] for s in effects)+",aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo"
            data = run([ffmpeg, "-nostdin", "-v", "error", "-f", "f32le", "-ar", SR, "-ac", 2,
                        "-i", "pipe:0", "-af", chain, "-f", "f32le", "pipe:1"],
                       input=(encoded.astype(np.float32)/32768).astype("<f4").tobytes())
            full = np.frombuffer(data, dtype="<f4").reshape(-1, 2).copy()
            assert np.all(np.isfinite(full)) and BODY < len(full) <= BODY+5*SR
            nonzero = int(np.count_nonzero(full[BODY:]))
            assert nonzero > 100, (name, "independent postbody tail witness absent")
            reference_file = root / (name+"-actual-eof-reference.f32")
            reference_file.write_bytes(data); references[name] = full
            report["witnesses"].append(dict(name=name, body_frames=BODY, actual_frames=len(full),
                                            tail_frames=len(full)-BODY, nonzero_tail_values=nonzero,
                                            reference_sha256=sha(reference_file)))
        assert np.max(np.abs(references["delay-compressor"]-references["compressor-delay"])) > .001
        (root/"cases.tsv").write_text("\n".join(projects)+"\n", encoding="utf8")
        command = [client, worker, root]+(["--unedited-only"] if args.unedited_only else [])
        done = subprocess.run(list(map(str, command)), capture_output=True, timeout=240, creationflags=FLAGS)
        (root/"client.stdout.log").write_bytes(done.stdout); (root/"client.stderr.log").write_bytes(done.stderr)
        report["client_exit"] = done.returncode
        assert done.returncode == 0, (done.returncode, done.stdout[-2500:], done.stderr[-2500:])
        compared = 0
        variants = ("unedited",) if args.unedited_only else tuple(SEGMENTS)
        for name, full in references.items():
            for variant in variants:
                label = name+"-"+variant; prefix = root/label
                graph_check(json.loads(prefix.with_suffix(".air").read_text()), variant, projects[name])
                expected = target(full, variant)
                want = quantize(expected)
                count, whole_error = compare(pcm(prefix.with_suffix(".wav")), want, label+" whole")
                compared += count
                paths = Path(str(prefix)+"-pulls.txt").read_text().splitlines()
                retained = np.concatenate([pcm(p) for p in paths])
                count, retained_error = compare(retained, want, label+" uneven retained")
                compared += count
                fresh_errors = []
                for first, last in ((61, 96), (91, 126)):
                    count, error = compare(pcm(Path(str(prefix)+f"-fresh{first}.wav")),
                                           want[first*SPF:last*SPF], label+f" fresh {first}")
                    compared += count; fresh_errors.append(error)
                # Omission and duplicate-tail mutants must be detectable by the
                # exact oracle, rather than disappearing below quantization.
                if any(segment[3] for segment in SEGMENTS[variant]):
                    body_only = expected.copy()
                    for _, length, start, final in SEGMENTS[variant]:
                        if final: body_only[(start+length)*SPF:(start+length)*SPF+len(full)-BODY] = 0
                    lost = int(np.count_nonzero(want != quantize(body_only)))
                    assert lost > 100, (label, "tail omission mutant invisible")
                    doubled = expected.copy()
                    for _, length, start, final in SEGMENTS[variant]:
                        if final:
                            doubled[(start+length)*SPF:(start+length)*SPF+len(full)-BODY] += full[BODY:]
                    duplicates = int(np.count_nonzero(want != quantize(doubled)))
                    assert duplicates > 100, (label, "duplicated tail mutant invisible")
                else:
                    lost = duplicates = 0
                report["cases"].append(dict(name=label, whole_pcm16_max_error=whole_error,
                                             retained_pcm16_max_error=retained_error,
                                             fresh_pcm16_max_errors=fresh_errors,
                                             tail_omission_changed_values=lost,
                                             duplicated_tail_changed_values=duplicates, graph_preserved=True))
        if not args.unedited_only and not args.skip_masters:
            helper = client.parent/("air-file-publish.exe" if os.name == "nt" else "air-file-publish")
            assert helper.is_file(), "Atomic export helper must be beside the fixture client"
            report["export_helper_sha256"] = sha(helper)
            stdout = run([client, worker, root, "--export"])
            (root/"export.stdout.log").write_bytes(stdout)
            for name, full in references.items():
                for variant in MASTER_VARIANTS:
                    label = name+"-"+variant
                    audio = run([ffmpeg, "-nostdin", "-v", "error", "-i", root/(label+"-master.mkv"),
                                 "-map", "0:a:0", "-ar", SR, "-ac", 2, "-f", "f32le", "pipe:1"])
                    actual = np.frombuffer(audio, dtype="<f4").reshape(-1, 2)
                    expected = master_target(full, variant)
                    observation = dict(name=label, actual_sample_frames=actual.shape[0],
                                       expected_sample_frames=expected.shape[0], channels=2,
                                       actual_values=actual.size, expected_values=expected.size,
                                       authored_video_frames=TOTAL//SPF,
                                       finite=bool(np.all(np.isfinite(actual))),
                                       endpoint_policy="Independent original DSP actual EOF + surviving-piece placement; silent filler defines video only")
                    report.setdefault("master_observations", []).append(observation)
                    assert actual.shape == expected.shape, (label, "master PCM count", observation)
                    assert observation["finite"], (label, "nonfinite master PCM", observation)
                    error = float(np.max(np.abs(actual-expected)))
                    assert error <= 2e-6, (label, "lossless master", error)
                    compared += actual.size
                    report["masters"].append(dict(name=label, samples=actual.size, max_float_error=error))
        if not args.unedited_only:
            report["cancellation"] = cancellation(root, client, worker, projects["delay"], references["delay"])
            compared += sum(row["recovery_pcm_values"] for row in report["cancellation"]["cases"])
            report["offline_refusals"] = []
            for name in references:
                message = (root/(name+"-offline-refusal.txt")).read_text()
                assert "[GA_AUDIO_SOURCE_OFFLINE]" in message, (name, message)
                report["offline_refusals"].append(dict(name=name, code="GA_AUDIO_SOURCE_OFFLINE",
                                                       after_body_frames=[61, 96], graph_unchanged=True))
            assert not (root/"offline-unpublished.wav").exists()
        assert len(report["cases"]) == 4*len(variants)
        assert sha(source) == report["source_sha256"]
        assert all(sha(root/(n+".air")) == value for n, value in project_hashes.items())
        assert sha(worker) == report["worker_sha256"] and sha(client) == report["client_sha256"]
        assert not list(root.rglob("*.rf64")) and not list(root.rglob(".genesis-nested-*"))
        report.update(passed=True, compared_pcm_values=compared,
                      original_projects_sha256=project_hashes, originals_unchanged=True,
                      owned_cache_removed=True, masters_omitted=bool(args.skip_masters or args.unedited_only))
    except BaseException as problem:
        report["error"] = str(problem)
        raise
    finally:
        if args.report:
            with args.report.open("x", encoding="utf8") as output:
                json.dump(report, output, indent=2); output.write("\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--unedited-only", action="store_true", help="Independent legacy whole-tail baseline only")
    parser.add_argument("--skip-masters", action="store_true", help="Private PCM-only component proof; full gate exports masters")
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    assert not args.report.exists(), "Refuse to overwrite a historical receipt"
    if args.work_root:
        args.work_root.mkdir(parents=True, exist_ok=False)
        check(args, args.work_root.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="genesis-audio-tail-") as temporary:
            check(args, Path(temporary))


if __name__ == "__main__":
    main()
