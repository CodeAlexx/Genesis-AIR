"""Two native sessions must not overwrite media, reset mailboxes, or cancel each other."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import wave
from array import array

from media_runtime import tool
from media_session import session_env, session_root

FLAGS = 0x08000000 if os.name == "nt" else 0


def run(argv, env=None):
    result = subprocess.run(list(map(str, argv)), env=env, capture_output=True, timeout=60,
                            creationflags=FLAGS)
    assert result.returncode == 0, (argv, result.stdout, result.stderr)
    return result


def wait_for(paths, processes):
    deadline = time.monotonic() + 20
    while not all(path.is_file() for path in paths):
        assert time.monotonic() < deadline and all(p.poll() is None for p in processes), paths
        time.sleep(.005)


def tone(path, expected):
    with wave.open(str(path), "rb") as audio:
        assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth(), audio.getnframes()) == (48000, 2, 2, 9600)
        values = array("h", audio.readframes(9600))[::2]
    def amplitude(frequency):
        sine = sum(value * math.sin(2 * math.pi * frequency * n / 48000) for n, value in enumerate(values))
        cosine = sum(value * math.cos(2 * math.pi * frequency * n / 48000) for n, value in enumerate(values))
        return math.hypot(sine, cosine) * 2 / len(values)
    assert amplitude(expected) > 2000 and amplitude(1320-expected) < 10, (path, expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    fixture, worker, binary = (p.resolve() for p in (args.fixture, args.worker, args.binary))
    with tempfile.TemporaryDirectory(prefix="genesis-media-sessions-") as temporary:
        root = Path(temporary)
        shared = root / "shared settings"
        shared.mkdir()
        sentinels = {"theme.txt": b"light\n", "autosave.air": b"legacy recovery",
                     "errors.jsonl": b"existing diagnostic\n"}
        recovery = shared / "recovery"
        recovery.mkdir()
        (recovery / "foreign.air").write_bytes(b"foreign recovery snapshot")
        for name, data in sentinels.items():
            (shared / name).write_bytes(data)
        sources = []
        for color, frequency in (("red", 440), ("blue", 880)):
            source = root / f"{color}.mkv"
            run([tool(worker, "ffmpeg"), "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                 f"color={color}:s=320x180:r=30", "-f", "lavfi", "-i",
                 f"sine=frequency={frequency}:sample_rate=48000", "-t", "0.2",
                 "-c:v", "ffv1", "-c:a", "pcm_s16le", source])
            sources.append(source)
        processes = []
        reports = [root / f"session-{n}.txt" for n in range(2)]
        try:
            for index, color in enumerate(("red", "blue")):
                processes.append(subprocess.Popen(list(map(str, [fixture, shared, sources[index], worker,
                                      reports[index], color])), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      creationflags=FLAGS))
            media = [session_root(report, process) for report, process in zip(reports, processes)]
            assert media[0] != media[1] and all(p.parent == shared / "media" for p in media)
            for round in range(3):
                wait_for([p / f"ready-{round}" for p in media], processes)
                # Each worker resets its own queues. Other-session mailbox evidence
                # must survive those resets, not merely have different path strings.
                for index, path in enumerate(media):
                    for task in ("preview", "timeline-strips", "audio-playback"):
                        (path / task).mkdir(exist_ok=True)
                        (path / task / "foreign-marker").write_text(str(index))
                for path in media:
                    (path / f"go-{round}").write_text("go")
                wait_for([p / f"done-{round}" for p in media], processes)
                for index, path in enumerate(media):
                    tone(path / "audition.wav", (440, 880)[index])
                    assert (path / "export.progress").read_text() == ("17", "43")[index]
                    assert (path / "export.cancel").is_file() == (index == 0)
                    for task in ("preview", "timeline-strips", "audio-playback"):
                        assert (path / task / "foreign-marker").read_text() == str(index)
                    assert (path / "frame.rgba").stat().st_size == 160 * 90 * 4
                for path in media:
                    (path / f"check-{round}").write_text("checked")
            for process in processes:
                output, _ = process.communicate(timeout=20)
                assert process.returncode == 0, output
            for name, data in sentinels.items():
                assert (shared / name).read_bytes() == data
            assert (recovery / "foreign.air").read_bytes() == b"foreign recovery snapshot"
            assert not (shared / "program.rgba").exists() and not (shared / "audition.wav").exists()
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
        # An explicit receipt is caller-owned, exclusive and never overwritten.
        env = dict(os.environ, GENESIS_FAKE_PROVIDER="1", GENESIS_SCRATCH=str(shared))
        current, receipt = session_env(env, root)
        run([binary, "demo", root / "demo.png"], current)
        first = session_root(receipt)
        original = receipt.read_bytes()
        refused = subprocess.run(list(map(str, [binary, "demo", root / "refused.png"])), env=current,
                                 capture_output=True, timeout=30, creationflags=FLAGS)
        assert refused.returncode != 0 and b"GA_MEDIA_SESSION_REPORT" in refused.stdout
        assert receipt.read_bytes() == original and not (root / "refused.png").exists()
        fresh, fresh_receipt = session_env(env, root)
        run([binary, "demo", root / "retry.png"], fresh)
        assert session_root(fresh_receipt) != first
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(dict(schema="genesis.media_sessions.v1", passed=True,
            concurrent_processes=2, rounds_per_process=3, decoded_frames=6, cached_frames=6,
            pcm_mixes=6, frames_per_mix=9600, sample_rate=48000, channels=2,
            independent_tone_oracles=True, cancellation_isolated=True, shared_state_preserved=True,
            exclusive_report_refusal_and_retry=True), indent=2) + "\n", encoding="utf-8")
    print("Media sessions: two concurrent workers, six real frame/cache reads and PCM mixes, private resets/cancel, shared-state preservation and exclusive receipt retry passed")


if __name__ == "__main__":
    main()
