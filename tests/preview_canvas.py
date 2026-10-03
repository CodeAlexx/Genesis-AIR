"""Small-sequence previews must agree with independently decoded lossless masters."""

from media_runtime import tool as _media_tool
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image
from playback_timing import run, FLAGS
from preview_fit import fitted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg, ffprobe = _media_tool(worker, "ffmpeg"), _media_tool(worker, "ffprobe")
    checks = 0
    with tempfile.TemporaryDirectory(prefix="genesis-preview-canvas-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        for width, height in ((320, 180), (321, 181), (180, 320)):
            # Fine alternating edges expose a blur applied at the wrong canvas scale.
            pixels = bytes(value for y in range(height) for x in range(width)
                           for value in (40 + (x % 12 < 6) * 120, 30 + y % 90, 20 + x % 100))
            raw = root / "detail.rgb"
            raw.write_bytes(pixels)
            source = root / f"detail-{width}x{height}.mkv"
            run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{width}x{height}", "-r", "30", "-i", raw, "-frames:v", "1", "-c:v", "ffv1", source])
            project = root / "sequence.air"
            run([binary, "probe", source, root / "ui.png", project], env)
            document = json.loads(project.read_text(encoding="utf-8"))
            document["sequences"][0].update(width=width, height=height, fps=30)
            document["clips"][0].update(length=1)
            plain = None
            for effects in (False, True):
                current = copy.deepcopy(document)
                if effects:
                    clip = current["clips"][0]["id"]
                    current["filters"] = [dict(id=50, clip=clip, kind="blur", order=0, enabled=True),
                                          dict(id=51, clip=clip, kind="text", order=1, enabled=True)]
                    current["filter_params"] = [dict(filter=50, name="radius", value=3.0),
                                                dict(filter=51, name="size", value=70.0)]
                    current["filter_text_params"] = [dict(filter=51, name="content", value="AIR")]
                    current["next_id"] = 52
                project.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
                preview = root / "preview.png"
                # Each case uses a fresh final output; export deliberately refuses replacement.
                master = root / f"master-{width}x{height}-{int(effects)}.mkv"
                run([binary, "preview", preview, project], env)
                run([binary, "export", master, project], env)
                metadata = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-of", "json", master]).stdout)
                video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
                assert (video["width"], video["height"], video["pix_fmt"]) == (width, height, "gbrp16le"), video
                decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(master),
                                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1"],
                                         capture_output=True, timeout=30, creationflags=FLAGS)
                assert decoded.returncode == 0 and len(decoded.stdout) == width * height * 4, decoded.stderr
                with Image.open(preview) as image:
                    assert image.size == (640, 360), image.size
                    shown = image.convert("RGBA").tobytes()
                expected = fitted(decoded.stdout, width, height, 640, 360)
                differences = [abs(a-b) for a, b in zip(shown, expected)]
                maximum, mean = max(differences), sum(differences) / len(differences)
                assert maximum <= 2 and mean < .6, (width, height, effects, maximum, mean)
                if effects:
                    assert sum(a != b for a, b in zip(shown, plain)) > 10000, "effect output did not change"
                    assert max(shown[::4]) > 220, "title white missing"
                else:
                    plain = shown
                checks += 1
                print(f"Preview canvas: {width}x{height}, effects={effects}, max error={maximum}, mean={mean:.4f}", flush=True)
    assert checks == 6
    print("Preview canvas: six small/odd/portrait preview-to-16-bit-master pixel comparisons passed", flush=True)


if __name__ == "__main__":
    main()
