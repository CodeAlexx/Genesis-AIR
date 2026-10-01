#!/usr/bin/env python3
"""Measure retained precision, HDR transfer tags and audio after three minutes."""
import argparse
from array import array
import copy
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import quote
from PIL import Image

from real_media import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--hdr-source", type=Path)
    args = parser.parse_args()
    args.binary, args.worker = args.binary.resolve(), args.worker.resolve()
    with TemporaryDirectory(prefix="genesis-precision-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(args.worker),
                   GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        width, height = 1024, 64
        # 1024 distinct values in a narrow band. An eight-bit bridge collapses
        # this to fewer than 30 values, even if the export container says 16-bit.
        row = array("H", [6554 + x * 6 for x in range(width)])
        raw = root / "ramp.gbrp16"
        raw.write_bytes((row * height * 3).tobytes())
        source = root / "16-bit ramp.mkv"
        run(["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gbrp16le",
             "-s", f"{width}x{height}", "-r", "30", "-i", raw, "-frames:v", "1",
             "-c:v", "ffv1", "-level", "3", source])
        project = root / "precision.air"
        run([args.binary, "probe", source, root / "ui.png", project], env)
        doc = json.loads(project.read_text(encoding="utf-8"))
        doc["sequences"][0].update(width=width, height=height, fps=30)
        clip = doc["clips"][0]
        clip.update(length=1)
        # Three lanes force a float intermediate; an upper picture filter forces
        # another preparation pass before that lane is composited.
        for index in range(2):
            track = dict(doc["tracks"][-1], id=20 + index, order=4 + index,
                         name=f"Precision {index}", kind=0)
            doc["tracks"].append(track)
            doc["clips"].append(dict(clip, id=30 + index, track=track["id"]))
        doc["filters"] = [dict(id=40, clip=31, kind="brightness", order=0, enabled=True)]
        doc["filter_params"] = [dict(filter=40, name="level", value=1.01)]
        doc["next_id"] = 50
        project.write_text(json.dumps(doc), encoding="utf-8")
        output = root / "lossless 16-bit.mkv"
        run([args.binary, "export", output, project], env)
        info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", output]).stdout)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert video["codec_name"] == "ffv1" and video["pix_fmt"] == "gbrp16le", video
        result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1",
                                 "-f", "rawvideo", "-pix_fmt", "gbrp16le", "pipe:1"],
                                capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr
        samples = array("H"); samples.frombytes(result.stdout)
        values = samples[width * 32:width * 33]
        assert len(set(values)) >= 1000, len(set(values))
        assert all(b > a for a, b in zip(values, values[1:])), "ramp lost monotonicity"
        print(f"16-bit master: {len(set(values))} distinct narrow-band values survived filtered three-lane compositing", flush=True)

        # SDR title white must become 100-nit PQ white, rather than 10,000-nit code 1.
        titled = copy.deepcopy(doc)
        titled["filters"].append(dict(id=41, clip=31, kind="text", order=1, enabled=True))
        titled["filter_params"].append(dict(filter=41, name="size", value=200.0))
        titled["filter_text_params"] = [dict(filter=41, name="content", value="AIR")]
        title_project = root / "HDR-title.air"
        title_project.write_text(json.dumps(titled), encoding="utf-8")
        title_master = root / "HDR-title.mkv"
        run([args.binary, "export", title_master, title_project, "--hdr"], env)
        title_pixels = subprocess.run(["ffmpeg", "-v", "error", "-i", str(title_master),
                                       "-frames:v", "1", "-f", "rawvideo", "-pix_fmt",
                                       "gbrp16le", "pipe:1"], capture_output=True, timeout=60)
        assert title_pixels.returncode == 0, title_pixels.stderr
        title_values = array("H"); title_values.frombytes(title_pixels.stdout)
        assert 32500 < max(title_values) < 34500, max(title_values)
        assert sum(v > 32000 for v in title_values) > 30, "HDR title has no covered white glyphs"
        hevc_hdr = root / "HDR-title.mp4"
        run([args.binary, "export", hevc_hdr, title_project, "--hdr"], env)
        info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", hevc_hdr]).stdout)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert video["codec_name"] == "hevc" and video["pix_fmt"] == "yuv420p10le", video
        assert video["color_transfer"] == "smpte2084" and video["color_primaries"] == "bt2020", video
        print("HDR titles: 100-nit PQ white retained; HEVC 10-bit PQ/BT.2020 profile passed", flush=True)

        if args.hdr_source:
            hdr_project = root / "HDR.air"
            run([args.binary, "probe", args.hdr_source.resolve(), root / "hdr-ui.png", hdr_project], env)
            hdr = json.loads(hdr_project.read_text(encoding="utf-8"))
            source_info = hdr["sources"][0]
            hdr["sequences"][0].update(width=source_info["width"], height=source_info["height"], fps=source_info["fps"])
            hdr["clips"][0].update(length=2)
            hdr_project.write_text(json.dumps(hdr), encoding="utf-8")
            hdr_output = root / "HDR16.mkv"
            run([args.binary, "export", hdr_output, hdr_project, "--hdr"], env, timeout=240)
            streams = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", hdr_output]).stdout)["streams"]
            video = next(s for s in streams if s["codec_type"] == "video")
            assert video["pix_fmt"] == "gbrp16le" and video["color_transfer"] == "smpte2084" and video["color_primaries"] == "bt2020", video
            assert (video["width"], video["height"]) == (3840, 2160), video
            def first_rgb16(path):
                decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1",
                                          "-f", "rawvideo", "-pix_fmt", "rgb48le", "pipe:1"],
                                         capture_output=True, timeout=60)
                assert decoded.returncode == 0, decoded.stderr
                values = array("H"); values.frombytes(decoded.stdout)
                return values
            original, exported = first_rgb16(args.hdr_source), first_rgb16(hdr_output)
            error = sum(abs(a - b) for a, b in zip(original[::97], exported[::97])) / len(original[::97])
            assert error < 65, f"PQ signal changed before the lossless encoder: {error}"
            print("Actual 4K AV1 HDR source: native-size 16-bit PQ/BT.2020 master passed", flush=True)
            preview = root / "HDR-preview.png"
            run([args.binary, "preview", preview, hdr_project], env)
            chain = ("zscale=transfer=linear:npl=100,format=gbrpf32le,zscale=primaries=bt709,"
                     "tonemap=tonemap=hable:desat=2,zscale=transfer=bt709:matrix=gbr:range=full,"
                     "format=gbrp16le,scale=1280:720:flags=bicubic")
            reference = subprocess.run(["ffmpeg", "-v", "error", "-i", str(args.hdr_source), "-vf", chain,
                                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                                       capture_output=True, timeout=60)
            assert reference.returncode == 0, reference.stderr
            with Image.open(preview) as opened_image:
                shown = opened_image.convert("RGB").tobytes()
            # The AIR monitor samples top-left integer coordinates, whereas
            # Pillow's nearest resampler chooses pixel centers.
            with Image.open(preview) as opened_image:
                shown_image = opened_image.copy()
            expected = b"".join(reference.stdout[(y * 720 // shown_image.height * 1280 + x * 1280 // shown_image.width) * 3:
                                                  (y * 720 // shown_image.height * 1280 + x * 1280 // shown_image.width) * 3 + 3]
                                for y in range(shown_image.height) for x in range(shown_image.width))
            assert len(shown) == len(expected)
            error = sum(abs(a - b) for a, b in zip(shown[::37], expected[::37])) / len(shown[::37])
            assert error < 3, f"HDR preview differs from the floating-point reference: {error}"
            print(f"HDR preview: Rec.709 tone mapping agrees with FFmpeg reference (mean error {error:.2f}/255)", flush=True)

        tone = root / "long-tone.wav"
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=182",
             "-c:a", "pcm_s16le", tone])
        wav = root / "long-program.wav"
        token = lambda p: quote(str(p), safe="/:\\")
        commands = f"WAVE {token(wav)} 182\nAUDIO {token(tone)} 0 182 0 1 0 0 182 0 -\nWAVECLOSE {token(wav)}\n"
        worker = subprocess.run([str(args.worker), "--serve", "--size", "64", "64"], input=commands,
                                capture_output=True, text=True, env=env, timeout=120)
        assert worker.returncode == 0 and "ERR" not in worker.stdout, (worker.stdout, worker.stderr)
        tail = subprocess.run(["ffmpeg", "-v", "error", "-ss", "181", "-i", str(wav), "-t", "0.1",
                               "-f", "f32le", "pipe:1"], capture_output=True, timeout=30)
        samples = array("f"); samples.frombytes(tail.stdout)
        assert samples and max(map(abs, samples)) > 0.05, "audio was truncated at three minutes"
        print("Program audio: samples after 181 seconds are audible", flush=True)


if __name__ == "__main__":
    main()
