"""Actual compound filmstrip pixels must retain owner time and descendant identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from media_runtime import tool

FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, accepted=True, **kwargs):
    done = subprocess.run(list(map(str, argv)), capture_output=True, timeout=150,
                          creationflags=FLAGS, **kwargs)
    if accepted:
        assert done.returncode == 0, (done.returncode, done.stdout[-6000:], done.stderr[-6000:])
    return done


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    worker, client = args.worker.resolve(), args.client.resolve()
    before = dict(worker=sha(worker), client=sha(client))
    ffmpeg = tool(worker, "ffmpeg")
    with tempfile.TemporaryDirectory(prefix="genesis-compound-filmstrip-") as directory:
        root = Path(directory)
        authored = b"".join(bytes(32+(frame*multiplier) % 192 for multiplier in (37, 73, 109))
                            * (320*180) for frame in range(96))
        raw = root / "authored.rgb"
        raw.write_bytes(authored)
        media = root / "compound frame 日本語 %20.mp4"
        run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
             "-video_size", "320x180", "-framerate", "24000/1001", "-i", raw,
             "-c:v", "libx264rgb", "-crf", "0", "-preset", "fast", "-bf", "3", "-g", "24", media])
        independent = run([ffmpeg, "-nostdin", "-v", "error", "-i", media,
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]).stdout
        assert independent == authored, "Independent fixture decoding changed frame codes"
        media_hash = sha(media)
        env = dict(os.environ, GENESIS_SCRATCH=str(root / "state"), GENESIS_GCOMPOSE=str(worker))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        completed = run([client, root / "native", worker, media], accepted=False, env=env)
        message = completed.stdout.decode("utf-8", errors="replace")
        count = re.search(r"(\d+) actual compound timeline bitmaps checked", message)
        suite = json.loads((root / "native/nested-timeline-bitmaps-tests.json").read_text())
        assert sha(media) == media_hash
        after = dict(worker=sha(worker), client=sha(client))
        assert before == after, "Tested executable changed during acceptance"
        passed = completed.returncode == 0 and count is not None and int(count.group(1)) >= 80
        receipt = dict(passed=passed, images_checked=int(count.group(1)) if count else 0, hashes=before,
                       immutable_binaries=True, source_unchanged=True, suite=suite,
                       exit_code=completed.returncode, output=message,
                       cases=["normal mixed FPS", "reverse", "trim and speed", "descendant grade"],
                       scope="asynchronous compound filmstrip pixels and identity; not sustained playback")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
        assert passed, (completed.returncode, message, completed.stderr[-6000:])
        print(message.strip())


if __name__ == "__main__":
    main()
