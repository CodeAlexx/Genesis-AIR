#!/usr/bin/env python3
"""Cancel the native export CLI during real pipe waits, then retry its output."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import time

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
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("native Windows process-exit verification is required")
    binary, worker, wrapper = (p.resolve() for p in (args.binary, args.worker, args.wrapper))
    with TemporaryDirectory(prefix="genesis-export-cancel-") as directory:
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
            partial = Path(str(movie) + ".genesis-air-part.mp4")
            marker = work / "blocked.pid"
            starts = work / "starts.log"
            scratch = work / "scratch"
            scratch.mkdir()
            test_env = dict(env, GENESIS_GCOMPOSE=str(wrapper), GENESIS_SCRATCH=str(scratch),
                            GENESIS_TEST_WORKER=str(worker), GENESIS_TEST_STARTS=str(starts),
                            GENESIS_TEST_EXPORT_BLOCK=str(marker), GENESIS_TEST_EXPORT_PHASE=phase,
                            GENESIS_TEST_EXPORT_PARTIAL=str(partial))
            argv = [binary, "export", movie, project]
            exporting = subprocess.Popen([str(a) for a in argv], env=test_env, text=True,
                                         encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 20
                pid = None
                while exporting.poll() is None and time.monotonic() < deadline:
                    try:
                        pid = int(marker.read_text())
                        break
                    except (OSError, ValueError):
                        time.sleep(0.005)
                assert pid is not None, (phase, "worker did not enter blocked phase", exporting.poll())
                assert partial.read_bytes() == b"partial"
                # Ensure the exit fixture has reached wait(), after receiving DONE.
                if phase == "exit":
                    time.sleep(0.15)
                started = time.monotonic()
                (scratch / "export.cancel").write_text("cancel\n")
                said, _ = exporting.communicate(timeout=2.5)
                elapsed = (time.monotonic() - started) * 1000
                assert exporting.returncode != 0 and "[GA_EXPORT_CANCELLED]" in said, (phase, said)
                assert_process_exited(pid)
                assert not movie.exists() and not list(work.glob(movie.name + ".*")), (phase, "partial export left")
                assert not (scratch / "export.cancel").exists() and not (scratch / "export.progress").exists()
                assert starts.read_text().splitlines() == ["start"], (phase, starts.read_text())
                print(f"Export {phase}: cancelled in {elapsed:.0f} ms, worker exited and partial removed", flush=True)
            finally:
                if exporting.poll() is None:
                    exporting.kill()
                    exporting.communicate(timeout=5)

            recovered = capture(argv, test_env)
            assert recovered.returncode == 0, (phase, recovered.stdout)
            info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", movie]).stdout)
            video = next(s for s in info["streams"] if s["codec_type"] == "video")
            assert (video["width"], video["height"], int(video["nb_frames"])) == (320, 180, 6), video
            color = pixel(movie, 160, 90, True)
            assert color[0] > 220 and color[1] < 20 and color[2] < 20, color
            assert audio_peak(movie) > 0.01
            assert not partial.exists() and starts.read_text().splitlines() == ["start", "start"]
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
        print("Export refusals: existing final and foreign partial preserved with coded errors", flush=True)


if __name__ == "__main__":
    main()
