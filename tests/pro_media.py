#!/usr/bin/env python3
"""Measured Windows sequence/export gates beyond the ordinary effect fixtures."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image
from real_media import run, pixel, audio_peak


def streams(movie):
    result = run(["ffprobe", "-v", "error", "-show_entries",
                  "stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate,pix_fmt",
                  "-of", "json", movie])
    return json.loads(result.stdout)["streams"]


def raw_frame(movie):
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(movie),
                             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt",
                             "rgb24", "pipe:1"], capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    info = next(s for s in streams(movie) if s["codec_type"] == "video")
    return Image.frombytes("RGB", (info["width"], info["height"]), result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    args.binary = args.binary.resolve()
    args.worker = args.worker.resolve()
    with TemporaryDirectory(prefix="genesis-pro-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(args.worker),
                   GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        detailed = root / "4K detail 日本語.mp4"
        # Four-pixel stripes cannot survive rendering at 1280 pixels then upscaling.
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             "nullsrc=s=3840x2160:r=30000/1001,geq=lum='if(lt(mod(X,8),4),24,232)':cb=128:cr=128",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
             "-frames:v", "6", "-t", "0.2002", "-c:v", "libx264", "-crf", "0",
             "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", detailed])
        project = root / "detail.air"
        run([args.binary, "probe", detailed, root / "detail-ui.png", project], env)
        document = json.loads(project.read_text(encoding="utf-8"))
        document["sequences"][0].update(width=3840, height=2160, fps=30000 / 1001)
        document["clips"][0].update(length=6)
        project.write_text(json.dumps(document), encoding="utf-8")
        mov = root / "4K master 日本語.mov"
        run([args.binary, "export", mov, project], env)
        info = streams(mov)
        video = next(s for s in info if s["codec_type"] == "video")
        assert (video["width"], video["height"], int(video["nb_frames"])) == (3840, 2160, 6), video
        assert video["codec_name"] == "prores" and video["r_frame_rate"] == "30000/1001", video
        assert next(s for s in info if s["codec_type"] == "audio")["codec_name"] == "pcm_s24le", info
        frame = raw_frame(mov)
        dark = sum(frame.getpixel((1200 + x, 1000))[0] for x in (0, 1, 2, 3)) / 4
        light = sum(frame.getpixel((1200 + x, 1000))[0] for x in (4, 5, 6, 7)) / 4
        assert light - dark > 170, (dark, light)
        assert audio_peak(mov) > 0.01
        print("4K ProRes: true fine detail, 3840x2160, 6 frames at 30000/1001 and 24-bit PCM passed", flush=True)

        portrait = root / "portrait.mp4"
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             "color=red:s=1080x1920:r=30,drawbox=x=450:y=870:w=180:h=180:color=white:t=fill",
             "-frames:v", "6", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", portrait])
        portrait_project = root / "portrait.air"
        run([args.binary, "probe", portrait, root / "portrait-ui.png", portrait_project], env)
        portrait_doc = json.loads(portrait_project.read_text(encoding="utf-8"))
        portrait_doc["sequences"][0].update(width=1080, height=1920, fps=30)
        portrait_doc["clips"][0].update(length=6)
        portrait_project.write_text(json.dumps(portrait_doc), encoding="utf-8")
        preview = root / "portrait-preview.png"
        run([args.binary, "preview", preview, portrait_project], env)
        image = Image.open(preview).convert("RGB")
        points = [(x, y) for y in range(image.height) for x in range(image.width)
                  if min(image.getpixel((x, y))) > 200]
        assert points
        xs, ys = zip(*points)
        box_w, box_h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        assert abs(box_w - box_h) <= 3, (box_w, box_h)
        assert max(image.getpixel((10, image.height // 2))) < 15
        assert image.getpixel((image.width // 2, 20))[0] > 200
        for extra, codec, name in (([], "h264", "portrait-h264.mp4"),
                                    (["--hevc"], "hevc", "portrait-hevc.mp4")):
            output = root / name
            run([args.binary, "export", output, portrait_project, *extra], env)
            video = next(s for s in streams(output) if s["codec_type"] == "video")
            assert (video["codec_name"], video["width"], video["height"], int(video["nb_frames"])) == (codec, 1080, 1920, 6), video
        print("Portrait: unstretched square in letterboxed preview, 1080x1920 H.264 and HEVC exports passed", flush=True)

        red, blue = root / "camera-red.mp4", root / "camera-blue.mp4"
        for color, destination in (("red", red), ("blue", blue)):
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color={color}:s=320x180:r=30",
                 "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                 "-t", "3", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", destination])
        camera_project = root / "multicam.air"
        run([args.binary, "probe", red, root / "multicam-ui.png", camera_project], env)
        camera = json.loads(camera_project.read_text(encoding="utf-8"))
        camera["sequences"][0].update(width=640, height=360)
        original = camera["clips"][0]
        original.update(length=90)
        other_source = dict(camera["sources"][0], id=90, path=str(blue), has_audio=False)
        camera["sources"].append(other_source)
        camera["clips"].append(dict(original, id=91, source=90, track=6))
        # Exactly the held opacity keys emitted by std.editor.cut_camera. Both source
        # positions and lengths stay unchanged; the exported picture must switch hard.
        camera["names"].append("opacity")
        opacity_param = len(camera["names"])
        camera["keys"] = [dict(clip=clip, owner=original["owner"], param=opacity_param,
                               frame=at, value=value, interp=4)
                          for clip, pairs in ((original["id"], ((0, 0.0), (30, 1.0), (60, 0.0))),
                                              (91, ((0, 1.0), (30, 0.0), (60, 1.0))))
                          for at, value in pairs]
        camera["next_id"] = 92
        camera_project.write_text(json.dumps(camera), encoding="utf-8")
        for at, is_blue in ((29, True), (30, False), (59, False), (60, True)):
            shown = copy.deepcopy(camera)
            shown["program"]["frame"] = at
            camera_project.write_text(json.dumps(shown), encoding="utf-8")
            output = root / f"camera-{at}.png"
            run([args.binary, "preview", output, camera_project], env)
            rgb = pixel(output, 320, 180)
            assert (rgb[2] > 200 and rgb[0] < 30) if is_blue else (rgb[0] > 200 and rgb[2] < 30), (at, rgb)
        camera_project.write_text(json.dumps(camera), encoding="utf-8")
        movie = root / "multicam.mp4"
        run([args.binary, "export", movie, camera_project], env)
        assert audio_peak(movie) > 0.01
        for at, is_blue in ((29, True), (30, False), (59, False), (60, True)):
            rgb = pixel(movie, 320, 180, True, at / 30)
            assert (rgb[2] > 200 and rgb[0] < 30) if is_blue else (rgb[0] > 200 and rgb[2] < 30), (at, rgb)
        print("Multicam: exact held cuts at frames 30/60 in preview and export, source positions unchanged and audio audible passed", flush=True)


if __name__ == "__main__":
    main()
