#!/usr/bin/env python3
"""Cancel the native export CLI during real pipe waits, then retry its output."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from contextlib import nullcontext
from tempfile import TemporaryDirectory
import hashlib
import time

from media_session import session_env, session_root
from audio_stream import assert_process_exited
from real_media import audio_peak, pixel, run


def capture(argv, env, timeout=30):
    return subprocess.run([str(a) for a in argv], env=env, text=True,
                          encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--wrapper", type=Path, required=True)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.work_root is not None:
        args.work_root.mkdir(parents=True, exist_ok=False)
    if args.report is not None and args.report.exists():
        raise FileExistsError("Preserve existing private proof")
    if os.name != "nt":
        parser.error("native Windows process-exit verification is required")
    binary, worker, wrapper = (p.resolve() for p in (args.binary, args.worker, args.wrapper))
    report = {"schema": "genesis.export-cancel.private.v1", "passed": False, "cases": [],
              "scope": "Private five-phase cancellation/retry proof; no R13 acceptance",
              "inputs": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (binary, worker, wrapper)}}
    def save_report():
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("w", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2)
    save_report()
    with nullcontext(str(args.work_root)) if args.work_root is not None else TemporaryDirectory(prefix="genesis-export-cancel-") as directory:
        root = Path(directory)
        source = root / "red audio.mp4"
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=30",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
             "-t", "0.2", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", source])
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "probe scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        project = root / "project.air"
        run([binary, "probe", source, root / "probe.png", project], env)
        doc = json.loads(project.read_text(encoding="utf-8"))
        doc["sequences"][0].update(width=320, height=180, fps=30)
        doc["clips"][0].update(length=6)
        project.write_text(json.dumps(doc), encoding="utf-8")

        for phase in ("open", "frame", "audio", "close", "exit"):
            work = root / phase
            work.mkdir()
            movie = work / "retry 日本語.mp4"
            reservation = Path(str(movie) + ".genesis-air-owner")
            partial = reservation / "export.mp4"
            marker = work / "blocked.pid"
            starts = work / "starts.log"
            scratch = work / "scratch"
            scratch.mkdir()
            test_env = dict(env, GENESIS_GCOMPOSE=str(wrapper), GENESIS_SCRATCH=str(scratch),
                            GENESIS_TEST_WORKER=str(worker), GENESIS_TEST_STARTS=str(starts),
                            GENESIS_TEST_EXPORT_BLOCK=str(marker), GENESIS_TEST_EXPORT_PHASE=phase,
                            GENESIS_TEST_EXPORT_PARTIAL=str(partial),
                            GENESIS_TEST_EXPORT_TRACE=str(work / "wire.log"))
            argv = [binary, "export", movie, project]
            exporting_env, session_report = session_env(test_env, work)
            exporting = subprocess.Popen([str(a) for a in argv], env=exporting_env, text=True,
                                         encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)
            case = {"phase": phase, "argv": list(map(str, argv)), "client_pid": exporting.pid, "passed": False}
            report["cases"].append(case)
            media_root = None
            said = None
            try:
                media_root = session_root(session_report, exporting)
                case["session_root"] = str(media_root)
                case["session_report"] = str(session_report)
                deadline = time.monotonic() + 20
                pid = None
                while exporting.poll() is None and time.monotonic() < deadline:
                    try:
                        pid = int(marker.read_text())
                        break
                    except (OSError, ValueError):
                        time.sleep(0.005)
                case["blocked_pid"] = pid
                assert pid is not None, (phase, "worker did not enter blocked phase", exporting.poll())
                assert partial.read_bytes() == b"partial"
                trace_path = work / "wire.log"
                wire = trace_path.read_text(encoding="utf-8")
                children = [line.split() for line in wire.splitlines() if line.startswith("CHILD ")]
                joins = [line.split() for line in wire.splitlines() if line.startswith("JOIN ")]
                endpoints = [line.split() for line in wire.splitlines() if line.startswith("OUT DONE NESTEND ")]
                assert len(children) == len(joins) == 1 and endpoints, (phase, "genuine preflight/join witness", wire)
                assert children[0][1] == joins[0][1] and "exit=0" in joins[0] and "active=0" in joins[0], (phase, joins)
                assert all(len(row) == 9 and int(row[5]) > 0 for row in endpoints), (phase, endpoints)
                child_pid = int(children[0][1])
                assert_process_exited(child_pid)
                case.update(genuine_preflight_pid=child_pid, genuine_preflight_joined=True,
                            structured_endpoint_replies=endpoints, wire_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest())
                # Ensure the exit fixture has reached wait(), after receiving DONE.
                if phase == "exit":
                    time.sleep(0.15)
                started = time.monotonic()
                (media_root / "export.cancel").write_text("cancel\n")
                said, _ = exporting.communicate(timeout=2.5)
                elapsed = (time.monotonic() - started) * 1000
                assert exporting.returncode != 0 and "[GA_EXPORT_CANCELLED]" in said, (phase, said)
                assert_process_exited(pid)
                assert not movie.exists() and not list(work.glob(movie.name + ".*")), (phase, "partial export left")
                assert not (media_root / "export.cancel").exists() and not (media_root / "export.progress").exists()
                assert starts.read_text().splitlines() == ["start"], (phase, starts.read_text())
                case.update(cancel_ms=elapsed, cancel_exit=exporting.returncode, cancel_stdout=said, blocked_worker_joined=True)
                print(f"Export {phase}: cancelled in {elapsed:.0f} ms, worker exited and partial removed", flush=True)
            except BaseException as error:
                case["error"] = repr(error)
                raise
            finally:
                if exporting.poll() is None:
                    exporting.kill()
                    said, _ = exporting.communicate(timeout=5)
                elif said is None:
                    said, _ = exporting.communicate(timeout=5)
                case["client_exit"] = exporting.returncode
                case["client_joined"] = exporting.poll() is not None
                case["stdout"] = said
                (work / "cli.stdout.log").write_text(said or "", encoding="utf-8")
                case["marker_exists"] = marker.exists()
                case["starts"] = starts.read_text() if starts.exists() else None
                case["wire"] = (work / "wire.log").read_text(encoding="utf-8", errors="replace") if (work / "wire.log").exists() else None
                case["progress"] = (media_root / "export.progress").read_text() if media_root is not None and (media_root / "export.progress").exists() else None
                save_report()

            recovered = capture(argv, test_env)
            case.update(retry_exit=recovered.returncode, retry_stdout=recovered.stdout)
            (work / "retry.stdout.log").write_text(recovered.stdout, encoding="utf-8")
            save_report()
            assert recovered.returncode == 0, (phase, recovered.stdout)
            info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", movie]).stdout)
            video = next(s for s in info["streams"] if s["codec_type"] == "video")
            assert (video["width"], video["height"], int(video["nb_frames"])) == (320, 180, 6), video
            color = pixel(movie, 160, 90, True)
            assert color[0] > 220 and color[1] < 20 and color[2] < 20, color
            assert audio_peak(movie) > 0.01
            assert not partial.exists() and starts.read_text().splitlines() == ["start", "start"]
            case["passed"] = True
            save_report()
            print(f"Export {phase}: same-path retry has six red frames and audible audio", flush=True)

        # Refusals must preserve somebody else's files and avoid starting a worker.
        work = root / "refusal"
        work.mkdir()
        scratch = work / "scratch"
        scratch.mkdir()
        starts = work / "starts.log"
        test_env = dict(env, GENESIS_GCOMPOSE=str(wrapper), GENESIS_SCRATCH=str(scratch),
                        GENESIS_TEST_WORKER=str(worker), GENESIS_TEST_STARTS=str(starts))
        for name, suffix, code in (("existing", "", "GA_EXPORT_EXISTS"),
                                   ("unfinished", ".genesis-air-part.mp4", "GA_EXPORT_PARTIAL_EXISTS")):
            movie = work / (name + ".mp4")
            foreign = Path(str(movie) + suffix)
            foreign.write_bytes(b"preserve this file")
            refused = capture([binary, "export", movie, project], test_env)
            assert refused.returncode != 0 and code in refused.stdout, refused.stdout
            assert foreign.read_bytes() == b"preserve this file" and not starts.exists()
            assert not (scratch / "export.cancel").exists() and not (scratch / "export.progress").exists()
        report["refusals_passed"] = True
        report["passed"] = True
        save_report()
        print("Export refusals: existing final and foreign partial preserved with coded errors", flush=True)


if __name__ == "__main__":
    main()
