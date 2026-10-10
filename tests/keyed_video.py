"""Inspector picture-key edits must survive save/open and affect preview/master pixels."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from media_runtime import tool


def run(argv, env=None, timeout=120):
    completed = subprocess.run([str(item) for item in argv], env=env, capture_output=True,
                               timeout=timeout,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert completed.returncode == 0, (argv, completed.stdout[-4000:], completed.stderr[-4000:])
    return completed.stdout


def rgb(frame):
    return 64 + (frame * 7) % 96, 80 + (frame * 11) % 96, 96 + (frame * 13) % 96


def level(local):
    if local <= 12:
        return .75 + (.35 * local / 12)
    return 1.1 + (.15 * (local - 12) / 11)


def check_pixels(data, local, frame, label):
    expected = [round(max(0, min(255, value + (level(local)-1) * 255))) for value in rgb(frame)]
    assert len(data) == 320 * 180 * 3, (label, len(data))
    worst = max(max(abs(actual-wanted) for actual in data[channel::3])
                for channel, wanted in enumerate(expected))
    assert worst <= 3, (label, local, frame, expected, tuple(data[:3]), worst)
    return worst


def check_blend(data, local, label):
    lower, upper = rgb(local*4//5), rgb((12+local)*4//5)
    expected = upper if local < 12 else [min(255, base+over) for base, over in zip(lower, upper)]
    assert len(data) == 320 * 180 * 3, (label, len(data))
    worst = max(max(abs(actual-wanted) for actual in data[channel::3])
                for channel, wanted in enumerate(expected))
    assert worst <= 3, (label, local, expected, tuple(data[:3]), worst)
    return worst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    worker = args.worker.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    with tempfile.TemporaryDirectory(prefix="genesis-keyed-video-") as temporary:
        root = Path(temporary)
        source = root / "frame keyed 日本語.mp4"
        raw = root / "source.rgb"
        frames = b"".join(bytes(rgb(frame)) * (320*180) for frame in range(40))
        raw.write_bytes(frames)
        run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", "320x180", "-r", "24000/1001", "-i", raw, "-c:v", "libx264rgb",
             "-crf", "0", "-preset", "fast", "-bf", "3", "-g", "12", source])
        decoded = run([ffmpeg, "-nostdin", "-v", "error", "-i", source,
                       "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
        assert decoded == frames, "independent lossless source decode changed its frame colors"
        native = root / "native"
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(native))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        output = run([args.client.resolve(), native, worker, source], env)
        print(output.decode("utf-8", errors="replace").strip())
        document = json.loads((native / "edited.air").read_text(encoding="utf-8"))
        assert [(item["frame"], item["value"]) for item in document["keys"]] == [(0, .75), (12, 1.1), (23, 1.25)]
        worst = 0
        for index, local in enumerate((0, 6, 12, 18, 23, 0)):
            image = run([ffmpeg, "-nostdin", "-v", "error", "-i", native / f"{index}.png",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
            worst = max(worst, check_pixels(image, local, (2+local)*4//5, f"preview {index}"))
        assert (native / "0.png").read_bytes() == (native / "5.png").read_bytes(), "rewind changed frame-zero pixels"
        master = run([ffmpeg, "-nostdin", "-v", "error", "-i", native / "edited.mkv",
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
        size = 320 * 180 * 3
        assert len(master) == 24 * size, ("fractional-rate master frame count", len(master)//size)
        for local in range(24):
            worst = max(worst, check_pixels(master[local*size:(local+1)*size], local,
                                           (2+local)*4//5, f"master {local}"))
        print(f"Keyed video: 6 whole preview pictures and 24 master frames match independent source/time/brightness formulas within {worst}/255; save/open and exact rewind passed")
        blend_root = native / "blend"
        blend_worst = 0
        for index, local in enumerate((0, 6, 11, 12, 18, 23, 0)):
            image = run([ffmpeg, "-nostdin", "-v", "error", "-i", blend_root / f"{index}.png",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
            blend_worst = max(blend_worst, check_blend(image, local, f"blend preview {index}"))
        assert (blend_root / "0.png").read_bytes() == (blend_root / "6.png").read_bytes(), "blend rewind changed frame-zero pixels"
        blended_master = run([ffmpeg, "-nostdin", "-v", "error", "-i", blend_root / "edited.mkv",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
        assert len(blended_master) == 24 * size, ("held blend master frame count", len(blended_master)//size)
        for local in range(24):
            blend_worst = max(blend_worst, check_blend(blended_master[local*size:(local+1)*size], local,
                                                     f"blend master {local}"))
        print(f"Held blend keys: 7 whole preview pictures and 24 master frames match independent Normal/Add formulas within {blend_worst}/255, including the exact keyed cut and rewind")


if __name__ == "__main__":
    main()
