"""Independent pixels after actual key navigation/deletion/interpolation dispatch."""
import argparse
from array import array
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from media_runtime import tool


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run(argv, env=None):
    value = subprocess.run([str(x) for x in argv], env=env, capture_output=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert value.returncode == 0, (argv, value.stdout[-4000:], value.stderr[-4000:])
    return value.stdout


def color(frame):
    return 80 + frame % 7, 96 + frame % 11, 112 + frame % 13


def level(frame):
    t = min(frame / 20, 1)
    return 1 - .25 * (3 * t * t - 2 * t * t * t)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    client = args.client.resolve()
    worker = args.worker.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    receipt = {"schema": "genesis.keyframe_controls.media.v1", "passed": False,
        "client_sha256": sha(client), "worker_sha256": sha(worker)}
    try:
        with tempfile.TemporaryDirectory(prefix="genesis-keyframe-controls-") as temporary:
            root = Path(temporary)
            source = root / "keys 日本語.mkv"
            raw = root / "source.rgb"
            # Author 16-bit samples directly. Promoting decoded 8-bit bgr0 uses
            # the runtime scaler's x*256+1 convention, rather than x*257.
            samples = array("H")
            for frame in range(24):
                samples.extend([v * 257 for v in color(frame)] * (64 * 36))
            authored = samples.tobytes()
            raw.write_bytes(authored)
            run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb48le",
                "-s", "64x36", "-r", "30", "-i", raw, "-c:v", "ffv1", "-pix_fmt", "gbrp16le", source])
            assert run([ffmpeg, "-nostdin", "-v", "error", "-i", source, "-f", "rawvideo",
                "-pix_fmt", "rgb48le", "pipe:1"]) == authored, "Source oracle mismatch"
            before = sha(source)
            native = root / "native"
            env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(native))
            env.pop("GENESIS_FAKE_PROVIDER", None)
            output = run([client, native, worker, source], env).decode("utf8", errors="replace")
            doc = json.loads((native / "media/edited.air").read_text(encoding="utf8"))
            saved = [(k["frame"], k["value"], k["interp"]) for k in doc["keys"]]
            assert saved == [(0, 1, 3), (20, .75, 2)], saved
            named = {doc["names"][key["param"] - 1] for key in doc["keys"]}
            assert len(named) == 1 and next(iter(named)).startswith("filter.") and next(iter(named)).endswith("brightness.level"), named
            assert before == sha(source), "Source altered by editing"
            worst_preview = 0
            for index, at in enumerate((0, 5, 10, 15, 20, 0)):
                pixels = run([ffmpeg, "-nostdin", "-v", "error", "-i", native / f"media/{index}.png",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
                assert len(pixels) == 64 * 36 * 3
                expected = [round(v + (level(at) - 1) * 255) for v in color(at)]
                error = max(max(abs(v - wanted) for v in pixels[c::3]) for c, wanted in enumerate(expected))
                assert error <= 1, ("preview", at, error, expected, tuple(pixels[:3]))
                worst_preview = max(error, worst_preview)
            assert (native / "media/0.png").read_bytes() == (native / "media/5.png").read_bytes(), "Rewind differs"
            data = array("H")
            data.frombytes(run([ffmpeg, "-nostdin", "-v", "error", "-i", native / "media/edited.mkv",
                "-f", "rawvideo", "-pix_fmt", "rgb48le", "pipe:1"]))
            assert len(data) == 24 * 64 * 36 * 3, ("Master frame count", len(data))
            worst_master = 0
            for at in range(24):
                frame = data[at * 64 * 36 * 3:(at + 1) * 64 * 36 * 3]
                expected = [round(v * 257 + (level(at) - 1) * 65535) for v in color(at)]
                error = max(max(abs(v - wanted) for v in frame[c::3]) for c, wanted in enumerate(expected))
                assert error <= 5, ("master", at, error, expected, list(frame[:3]))
                worst_master = max(error, worst_master)
            receipt.update(passed=True, previews=6, master_frames=24, native_channel_values=len(data),
                master_max_error_codes=worst_master, preview_max_error_codes=worst_preview,
                source_unchanged=True, source_sha256=before, fixture_stdout=output)
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
    print(f"Key management: 6 previews+24 native master frames passed, max {worst_master}/65535")


if __name__ == "__main__":
    main()
