#!/usr/bin/env python3
"""Bounded preview/export integration test against a source-built gcompose worker."""
import argparse
from array import array
import json
import math
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def run(argv, env=None, timeout=180, cwd=None):
    done = subprocess.run([str(a) for a in argv], env=env, capture_output=True,
                          text=True, timeout=timeout, cwd=cwd)
    assert done.returncode == 0, f"{argv}\n{done.stdout}\n{done.stderr}"
    return done


def pixel(path, x, y, movie=False, time_s=0.1):
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if movie:
        argv += ["-ss", str(time_s)]
    argv += ["-i", str(path), "-vf", f"crop=2:2:{x}:{y},scale=1:1", "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    done = subprocess.run(argv, capture_output=True, timeout=30)
    assert done.returncode == 0 and len(done.stdout) == 3, done.stderr
    return tuple(done.stdout)


def rgb_frame(path, movie=False, time_s=0.1):
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if movie:
        argv += ["-ss", str(time_s)]
    argv += ["-i", str(path), "-vf", "scale=640:360", "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    done = subprocess.run(argv, capture_output=True, timeout=30)
    assert done.returncode == 0 and len(done.stdout) == 640 * 360 * 3, done.stderr
    return done.stdout


def light_points(path, box, movie=False, time_s=0.1, threshold=150):
    frame = rgb_frame(path, movie, time_s)
    left, top, right, bottom = box
    found = []
    for y in range(top, bottom):
        for x in range(left, right):
            at = (y * 640 + x) * 3
            if frame[at + 1] > threshold and frame[at + 2] > threshold:
                found.append(x)
    return found


def blend_reference(base, over, mode):
    b, o = base / 255, over / 255
    if mode == 0:
        value = o
    elif mode == 1:
        value = min(1, b + o)
    elif mode == 2:
        value = 1 - (1 - b) * (1 - o)
    elif mode == 3:
        value = b * o
    elif mode == 4:
        value = 2 * b * o if b < 0.5 else 1 - 2 * (1 - b) * (1 - o)
    elif mode == 5:
        value = min(b, o)
    elif mode == 6:
        value = max(b, o)
    elif mode == 7:
        value = abs(b - o)
    elif mode == 8:
        value = max(0, b - o)
    elif mode == 9:
        value = 2 * b * o if o < 0.5 else 1 - 2 * (1 - b) * (1 - o)
    elif mode == 10:
        d = ((16 * b - 12) * b + 4) * b if b <= 0.25 else math.sqrt(b)
        value = b - (1 - 2 * o) * b * (1 - b) if o <= 0.5 else b + (2 * o - 1) * (d - b)
    else:
        value = 1 if o >= 1 else min(1, b / (1 - o))
    return round(value * 255)


def audio_peak(movie, channel=None):
    argv = ["ffmpeg", "-v", "error", "-i", str(movie), "-vn"]
    if channel:
        argv += ["-af", f"pan=mono|c0={channel}"]
    argv += ["-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"]
    audio = subprocess.run(argv,
                           capture_output=True, timeout=30)
    assert audio.returncode == 0, audio.stderr
    samples = array("f")
    samples.frombytes(audio.stdout)
    return max((abs(v) for v in samples), default=0.0)


def audio_rms_window(movie, start, duration):
    done = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start),
                           "-i", str(movie), "-t", str(duration), "-vn",
                           "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"],
                          capture_output=True, timeout=30)
    assert done.returncode == 0, done.stderr
    samples = array("f")
    samples.frombytes(done.stdout)
    assert samples
    return (sum(sample * sample for sample in samples) / len(samples)) ** 0.5


def zero_crossings(movie):
    done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(movie), "-vn",
                           "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"],
                          capture_output=True, timeout=30)
    assert done.returncode == 0, done.stderr
    samples = array("f")
    samples.frombytes(done.stdout)
    return sum((a < 0 <= b or b < 0 <= a) and abs(a - b) > 0.002
               for a, b in zip(samples, samples[1:]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--stdlib", type=Path, required=True)
    args = parser.parse_args()
    assert args.binary.exists() and args.worker.exists() and args.stdlib.exists()
    args.binary = args.binary.resolve()
    args.worker = args.worker.resolve()
    args.stdlib = args.stdlib.resolve()
    with TemporaryDirectory(prefix="genesis-air-real-") as temporary:
        root = Path(temporary)
        red, blue, green, gray, key_green = (root / name for name in (
            "red clip.mp4", "blue clip.mp4", "green clip.mp4", "gray clip.mp4",
            "key-green.mp4"))
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=red:s=320x180:r=30",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", "-c:a", "aac", red])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=30",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", blue])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=green:s=320x180:r=30",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", green])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=30",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", gray])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=0x00ff00:s=320x180:r=30",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", key_green])
        env = dict(os.environ, AIR_STDLIB=str(args.stdlib),
                   GENESIS_GCOMPOSE=str(args.worker),
                   GENESIS_SCRATCH=str(root / "scratch"),
                   XDG_CACHE_HOME=str(root / "cache"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        project = root / "project.air"
        run([args.binary, "probe", red.name, root / "panel.png", project], env, cwd=root)
        document = json.loads(project.read_text())
        source = document["sources"][0]
        assert source["fps"] == 30 and source["width"] == 320
        assert source["path"] == str(red), source["path"]
        assert source["has_audio"] is True and source["frames"] == 12
        blue_source = dict(source, id=9, path=str(blue), name="blue",
                           has_audio=False)
        document["sources"].append(blue_source)
        document["clips"].append(dict(document["clips"][0], id=10, source=9,
                                      track=6))
        document["filters"].append(dict(id=11, clip=10, kind="opacity",
                                        order=0, enabled=True))
        document["filter_params"].append(dict(filter=11, name="level",
                                               value=0.5))
        document["next_id"] = 12
        project.write_text(json.dumps(document))

        preview = root / "preview.png"
        movie = root / "export.mp4"
        run([args.binary, "preview", preview, project], env)
        run([args.binary, "export", movie, project], env)
        seen, encoded = pixel(preview, 320, 180), pixel(movie, 960, 540, True)
        assert 100 <= seen[0] <= 155 and seen[1] < 15 and 100 <= seen[2] <= 155, seen
        assert max(abs(a - b) for a, b in zip(seen, encoded)) <= 15, (seen, encoded)

        # An upper clip's grade must affect that clip before blending. Brightening
        # or darkening the finished composite would also change the red base.
        graded_overlay = json.loads(json.dumps(document))
        graded_overlay["filters"].append(dict(id=24, clip=10, kind="brightness",
                                              order=1, enabled=True))
        graded_overlay["filter_params"].append(dict(filter=24, name="level", value=0.0))
        graded_overlay["next_id"] = 25
        graded_project = root / "graded-overlay.air"
        graded_project.write_text(json.dumps(graded_overlay))
        graded_preview = root / "graded-overlay.png"
        graded_movie = root / "graded-overlay.mp4"
        run([args.binary, "preview", graded_preview, graded_project], env)
        run([args.binary, "export", graded_movie, graded_project], env)
        graded_color = pixel(graded_preview, 320, 180)
        graded_encoded = pixel(graded_movie, 960, 540, True)
        assert 100 <= graded_color[0] <= 155 and graded_color[2] < 20, graded_color
        assert max(abs(a - b) for a, b in zip(graded_color, graded_encoded)) <= 15
        overlay_mask = json.loads(json.dumps(document))
        overlay_mask["filters"].append(dict(id=24, clip=10, kind="mask",
                                            order=1, enabled=True))
        overlay_mask["filter_params"].append(dict(filter=24, name="feather", value=0.1))
        overlay_mask["next_id"] = 25
        overlay_mask_project = root / "overlay-mask.air"
        overlay_mask_project.write_text(json.dumps(overlay_mask))
        overlay_mask_output = root / "overlay-mask.png"
        rejected_mask = subprocess.run([str(args.binary), "preview", str(overlay_mask_output),
                                        str(overlay_mask_project)], env=env,
                                       capture_output=True, text=True, timeout=30)
        assert rejected_mask.returncode != 0 and "overlay spatial effect needs per-clip transparency" in (
            rejected_mask.stdout + rejected_mask.stderr)
        assert not overlay_mask_output.exists()
        rotated_overlay = json.loads(json.dumps(document))
        rotated_overlay["filter_params"][0]["value"] = 1.0
        rotated_overlay["filters"].append(dict(id=12, clip=10, kind="rotate",
                                               order=1, enabled=True))
        rotated_overlay["filter_params"].append(dict(filter=12, name="angle", value=45.0))
        rotated_overlay["next_id"] = 13
        rotated_project = root / "rotated-overlay.air"
        rotated_project.write_text(json.dumps(rotated_overlay))
        rotated_preview = root / "rotated-overlay.png"
        rotated_movie = root / "rotated-overlay.mp4"
        run([args.binary, "preview", rotated_preview, rotated_project], env)
        run([args.binary, "export", rotated_movie, rotated_project], env)
        for point, lower in (((20, 300), True), ((320, 180), False)):
            preview_rgb = pixel(rotated_preview, *point)
            movie_rgb = pixel(rotated_movie, point[0] * 3, point[1] * 3, True)
            assert (preview_rgb[0] > 200 and preview_rgb[2] < 30) == lower, (
                point, preview_rgb)
            assert max(abs(a - b) for a, b in zip(preview_rgb, movie_rgb)) <= 18

        media = run(["ffprobe", "-v", "error", "-show_entries",
                     "stream=codec_type,nb_frames,width,height", "-of", "json",
                     movie])
        streams = json.loads(media.stdout)["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        assert (video["width"], video["height"], int(video["nb_frames"])) == (1920, 1080, 12)
        assert any(s["codec_type"] == "audio" for s in streams), streams
        assert audio_peak(movie) > 0.01, "exported audio is silent"

        blend_base = root / "blend-base.mp4"
        blend_over = root / "blend-over.mp4"
        for color, destination in (("0x4060a0", blend_base), ("0xc08040", blend_over)):
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                 "-i", f"color=c={color}:s=320x180:r=30", "-t", "0.4",
                 "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                 destination])
        blend_doc = json.loads(json.dumps(document))
        blend_doc["sources"][0]["path"] = str(blend_base)
        blend_doc["sources"][0]["has_audio"] = False
        blend_doc["sources"][1]["path"] = str(blend_over)
        blend_doc["sources"][1]["has_audio"] = False
        blend_doc["filters"] = [dict(id=11, clip=10, kind="blend", order=0, enabled=True)]
        blend_doc["filter_params"] = [dict(filter=11, name="mode", value=0.0)]
        blend_doc["next_id"] = 12
        blend_project = root / "blend.air"
        base_only = json.loads(json.dumps(blend_doc))
        base_only["clips"] = [base_only["clips"][0]]
        base_only["filters"] = []
        base_only["filter_params"] = []
        blend_project.write_text(json.dumps(base_only))
        base_preview = root / "blend-base.png"
        run([args.binary, "preview", base_preview, blend_project], env)
        base_rgb = pixel(base_preview, 320, 180)
        for mode in range(12):
            blend_doc["filter_params"][0]["value"] = float(mode)
            blend_project.write_text(json.dumps(blend_doc))
            blend_preview = root / f"blend-{mode}.png"
            blend_movie = root / f"blend-{mode}.mp4"
            run([args.binary, "preview", blend_preview, blend_project], env)
            run([args.binary, "export", blend_movie, blend_project], env)
            preview_rgb = pixel(blend_preview, 320, 180)
            movie_rgb = pixel(blend_movie, 960, 540, True)
            if mode == 0:
                over_rgb = preview_rgb
            expected = tuple(blend_reference(b, o, mode) for b, o in zip(base_rgb, over_rgb))
            assert max(abs(a - b) for a, b in zip(preview_rgb, expected)) <= 8, (
                mode, base_rgb, over_rgb, preview_rgb, expected)
            assert max(abs(a - b) for a, b in zip(preview_rgb, movie_rgb)) <= 18, (
                mode, preview_rgb, movie_rgb)

        simple_doc = json.loads(json.dumps(document))
        simple_doc["clips"] = [simple_doc["clips"][0]]
        simple_doc["filters"] = []
        simple_doc["filter_params"] = []
        simple_project = root / "simple-fx.air"
        simple_project.write_text(json.dumps(simple_doc))
        simple_plain = root / "simple-plain.png"
        run([args.binary, "preview", simple_plain, simple_project], env)
        plain_rgb = pixel(simple_plain, 320, 180)
        for kind in ("invert", "sepia", "mono"):
            simple_doc["filters"] = [dict(id=11, clip=simple_doc["clips"][0]["id"], kind=kind,
                                          order=0, enabled=True)]
            simple_doc["filter_params"] = [dict(filter=11, name="amount", value=1.0)]
            simple_project.write_text(json.dumps(simple_doc))
            full_preview = root / f"{kind}-full.png"
            run([args.binary, "preview", full_preview, simple_project], env)
            full_rgb = pixel(full_preview, 320, 180)
            simple_doc["filter_params"][0]["value"] = 0.5
            simple_project.write_text(json.dumps(simple_doc))
            half_preview = root / f"{kind}-half.png"
            half_movie = root / f"{kind}-half.mp4"
            run([args.binary, "preview", half_preview, simple_project], env)
            run([args.binary, "export", half_movie, simple_project], env)
            half_rgb = pixel(half_preview, 320, 180)
            expected = tuple(round((a + b) / 2) for a, b in zip(plain_rgb, full_rgb))
            assert max(abs(a - b) for a, b in zip(half_rgb, expected)) <= 5, (
                kind, half_rgb, expected)
            movie_rgb = pixel(half_movie, 960, 540, True)
            assert max(abs(a - b) for a, b in zip(half_rgb, movie_rgb)) <= 18

        rate24 = json.loads(json.dumps(document))
        rate24["sequences"][0]["fps"] = 24.0
        rate24["clips"] = [rate24["clips"][0]]
        rate24["clips"][0]["length"] = 9
        rate24["program"]["mark_out"] = 9
        rate24["filters"] = []
        rate24["filter_params"] = []
        rate24_project = root / "rate24.air"
        rate24_project.write_text(json.dumps(rate24))
        rate24_preview = root / "rate24.png"
        rate24_movie = root / "rate24.mp4"
        run([args.binary, "preview", rate24_preview, rate24_project], env)
        run([args.binary, "export", rate24_movie, rate24_project], env)
        rate24_probe = run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,nb_frames,avg_frame_rate,duration",
                            "-of", "json", rate24_movie])
        rate24_streams = json.loads(rate24_probe.stdout)["streams"]
        rate24_video = next(s for s in rate24_streams if s["codec_type"] == "video")
        assert (rate24_video["avg_frame_rate"], int(rate24_video["nb_frames"])) == ("24/1", 9)
        assert abs(float(rate24_video["duration"]) - 9 / 24) < 0.03
        assert audio_peak(rate24_movie) > 0.01
        assert max(abs(a - b) for a, b in zip(pixel(rate24_preview, 320, 180),
                                              pixel(rate24_movie, 960, 540, True))) <= 15

        # The inspector's fade keyframes must change actual pixels in both
        # preview and MP4, even when the clip's stored fade is zero.
        fade_doc = json.loads(json.dumps(document))
        fade_doc["clips"] = [fade_doc["clips"][0]]
        fade_doc["filters"] = []
        fade_doc["filter_params"] = []
        fade_doc["names"].append("fade_in")
        fade_param = len(fade_doc["names"])
        fade_clip = fade_doc["clips"][0]
        fade_doc["keys"] = [dict(clip=fade_clip["id"], owner=fade_clip["owner"],
                                 param=fade_param, frame=at, value=12.0, interp=0)
                            for at in (0, 11)]
        fade_project = root / "fade.air"
        fade_project.write_text(json.dumps(fade_doc))
        fade_first = root / "fade-first.png"
        fade_middle = root / "fade-middle.png"
        run([args.binary, "preview", fade_first, fade_project], env)
        fade_doc["program"]["frame"] = 6
        fade_project.write_text(json.dumps(fade_doc))
        run([args.binary, "preview", fade_middle, fade_project], env)
        fade_movie = root / "fade.mp4"
        run([args.binary, "export", fade_movie, fade_project], env)
        first_color = pixel(fade_first, 320, 180)
        middle_color = pixel(fade_middle, 320, 180)
        encoded_middle = pixel(fade_movie, 960, 540, True, 6 / 30)
        assert first_color[0] < 20, first_color
        assert 100 <= middle_color[0] <= 150, middle_color
        assert max(abs(a - b) for a, b in zip(middle_color, encoded_middle)) <= 15, (
            middle_color, encoded_middle)

        # Opacity is also exposed on a sole/base clip. Its filter value must
        # darken that clip in the same preview and encoded paths.
        fade_doc["keys"] = []
        fade_doc["filters"] = [dict(id=20, clip=fade_clip["id"], kind="opacity",
                                    order=0, enabled=True)]
        fade_doc["filter_params"] = [dict(filter=20, name="level", value=0.5)]
        fade_project.write_text(json.dumps(fade_doc))
        base_opacity_preview = root / "base-opacity.png"
        base_opacity_movie = root / "base-opacity.mp4"
        run([args.binary, "preview", base_opacity_preview, fade_project], env)
        run([args.binary, "export", base_opacity_movie, fade_project], env)
        base_color = pixel(base_opacity_preview, 320, 180)
        base_encoded = pixel(base_opacity_movie, 960, 540, True)
        assert 100 <= base_color[0] <= 150 and base_color[1] < 15, base_color
        assert max(abs(a - b) for a, b in zip(base_color, base_encoded)) <= 15, (
            base_color, base_encoded)

        # Feather and invert are the two exposed mask controls. Center and edge
        # pixels verify that both actually reach the image, not just the wire.
        fade_doc["filters"] = [dict(id=20, clip=fade_clip["id"], kind="mask",
                                    order=0, enabled=True)]
        fade_doc["filter_params"] = [dict(filter=20, name="feather", value=0.1),
                                     dict(filter=20, name="invert", value=0.0)]
        fade_project.write_text(json.dumps(fade_doc))
        mask_preview = root / "mask.png"
        mask_movie = root / "mask.mp4"
        run([args.binary, "preview", mask_preview, fade_project], env)
        run([args.binary, "export", mask_movie, fade_project], env)
        mask_center = pixel(mask_preview, 320, 180)
        mask_edge = pixel(mask_preview, 4, 180)
        assert mask_center[0] > 220 and mask_edge[0] < 50, (mask_center, mask_edge)
        assert max(abs(a - b) for a, b in zip(mask_center,
                   pixel(mask_movie, 960, 540, True))) <= 15
        fade_doc["filter_params"][1]["value"] = 1.0
        fade_project.write_text(json.dumps(fade_doc))
        mask_inverse = root / "mask-inverse.png"
        mask_inverse_movie = root / "mask-inverse.mp4"
        run([args.binary, "preview", mask_inverse, fade_project], env)
        run([args.binary, "export", mask_inverse_movie, fade_project], env)
        inverse_center = pixel(mask_inverse, 320, 180)
        inverse_edge = pixel(mask_inverse, 4, 180)
        assert inverse_center[0] < 30 and inverse_edge[0] > 200, (
            inverse_center, inverse_edge)
        assert max(abs(a - b) for a, b in zip(inverse_edge,
                   pixel(mask_inverse_movie, 12, 540, True))) <= 20

        # Window audition uses the same AIR timeline resolver. Inspect the actual
        # WAV that its preparation step hands to the system audio player.
        audition = root / "audition result.wav"
        run([args.binary, "audio", audition, project], env)
        assert audio_peak(audition) > 0.01, "playback WAV is silent"
        wave_meta = run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_name,sample_rate,channels:format=duration",
                         "-of", "json", audition])
        wave_info = json.loads(wave_meta.stdout)
        assert wave_info["streams"][0] == {
            "codec_name": "pcm_s16le", "sample_rate": "48000", "channels": 2
        }, wave_info
        assert 0.39 <= float(wave_info["format"]["duration"]) <= 0.41, wave_info

        # One second of 24 fps media occupies 30 frames in this 30 fps sequence.
        # The editor must retain the native 24-frame probe while allowing the full
        # timeline duration and sampling its last blue native frames.
        mixed_source = root / "mixed-rate.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=red:s=320x180:r=24:d=0.5",
             "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=24:d=0.5",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
             "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
             "-map", "[v]", "-map", "2:a", "-t", "1", "-c:v", "libx264",
             "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
             mixed_source])
        mixed_project = root / "mixed-rate.air"
        run([args.binary, "probe", mixed_source, root / "mixed-panel.png",
             mixed_project], env)
        mixed_doc = json.loads(mixed_project.read_text())
        assert mixed_doc["sources"][0]["frames"] == 24
        mixed_doc["clips"][0]["length"] = 30
        mixed_doc["program"]["frame"] = 29
        mixed_project.write_text(json.dumps(mixed_doc))
        mixed_preview = root / "mixed-preview.png"
        mixed_movie = root / "mixed-export.mp4"
        run([args.binary, "preview", mixed_preview, mixed_project], env)
        run([args.binary, "export", mixed_movie, mixed_project], env)
        mixed_color = pixel(mixed_preview, 320, 180)
        assert mixed_color[2] > 200 and mixed_color[0] < 30, mixed_color
        mixed_meta = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=nb_frames", "-of", "json", mixed_movie])
        assert int(json.loads(mixed_meta.stdout)["streams"][0]["nb_frames"]) == 30
        assert audio_peak(mixed_movie) > 0.01

        # The library Speed filter and the clip Rate property share one source
        # clock. Twice the source rate fits one source second into 15 sequence
        # frames and retimes its audio to the same half-second output.
        speed_doc = json.loads(json.dumps(mixed_doc))
        speed_doc["clips"][0]["length"] = 15
        speed_doc["program"]["frame"] = 14
        speed_doc["filters"] = [dict(id=70, clip=speed_doc["clips"][0]["id"],
                                     kind="speed", order=0, enabled=True)]
        speed_doc["filter_params"] = [dict(filter=70, name="rate", value=2.0)]
        speed_doc["next_id"] = 71
        speed_project = root / "speed.air"
        speed_project.write_text(json.dumps(speed_doc))
        speed_preview = root / "speed-preview.png"
        speed_movie = root / "speed.mp4"
        run([args.binary, "preview", speed_preview, speed_project], env)
        run([args.binary, "export", speed_movie, speed_project], env)
        speed_color = pixel(speed_preview, 320, 180)
        speed_encoded = pixel(speed_movie, 960, 540, True, 14 / 30)
        assert speed_color[2] > 200 and speed_color[0] < 30, speed_color
        assert max(abs(a - b) for a, b in zip(speed_color, speed_encoded)) <= 15
        speed_meta = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=nb_frames", "-of", "json", speed_movie])
        assert int(json.loads(speed_meta.stdout)["streams"][0]["nb_frames"]) == 15
        assert audio_peak(speed_movie) > 0.01

        # A video clip can carry picture and sound filters at once. The picture path
        # must ignore audio filters and the audio path must ignore picture filters.
        filtered = json.loads(json.dumps(document))
        base_id = filtered["clips"][0]["id"]
        filtered["filters"].extend([
            dict(id=12, clip=base_id, kind="brightness", order=0, enabled=True),
            dict(id=13, clip=base_id, kind="gain", order=1, enabled=True),
        ])
        filtered["filter_params"].extend([
            dict(filter=12, name="level", value=0.8),
            dict(filter=13, name="level", value=-12.0),
        ])
        filtered["next_id"] = 14
        filtered_project = root / "filtered.air"
        filtered_project.write_text(json.dumps(filtered))
        filtered_movie = root / "filtered.mp4"
        run([args.binary, "export", filtered_movie, filtered_project], env)
        assert 0.0 < audio_peak(filtered_movie) < audio_peak(movie) * 0.4
        # A low pass on the 440 Hz tone must change the encoded samples, so an
        # accepted command that silently falls back to unfiltered audio fails here.
        filtered["filters"][2] = dict(id=13, clip=base_id, kind="low_pass",
                                      order=1, enabled=True)
        filtered["filter_params"][2] = dict(filter=13, name="cutoff", value=100.0)
        filtered_project.write_text(json.dumps(filtered))
        low_movie = root / "low-pass.mp4"
        run([args.binary, "export", low_movie, filtered_project], env)
        assert 0.0 < audio_peak(low_movie) < audio_peak(movie) * 0.55
        filtered["filters"][2]["kind"] = "compressor"
        filtered["filter_params"] = [dict(filter=12, name="level", value=0.8),
                                     dict(filter=13, name="threshold", value=-30.0),
                                     dict(filter=13, name="ratio", value=10.0),
                                     dict(filter=13, name="attack", value=1.0),
                                     dict(filter=13, name="release", value=20.0)]
        filtered_project.write_text(json.dumps(filtered))
        compressed_movie = root / "compressed.mp4"
        run([args.binary, "export", compressed_movie, filtered_project], env)
        assert 0.0 < audio_peak(compressed_movie) < audio_peak(movie) * 0.8
        filtered["filters"][2]["kind"] = "pitch"
        filtered["filter_params"] = [dict(filter=12, name="level", value=0.8),
                                     dict(filter=13, name="semitones", value=12.0)]
        filtered_project.write_text(json.dumps(filtered))
        pitched_movie = root / "pitched.mp4"
        run([args.binary, "export", pitched_movie, filtered_project], env)
        assert zero_crossings(pitched_movie) > zero_crossings(movie) * 1.5
        for kind in ("eq_3band", "eq_10band", "gate", "normalize", "delay", "reverb", "notch",
                     "chorus", "flanger", "phaser", "limiter"):
            effect_project = json.loads(json.dumps(document))
            effect_project["filters"].append(dict(id=12, clip=base_id, kind=kind,
                                                   order=0, enabled=True))
            effect_project["next_id"] = 13
            effect_file = root / f"audio-{kind}.air"
            effect_file.write_text(json.dumps(effect_project))
            effect_movie = root / f"audio-{kind}.mp4"
            run([args.binary, "export", effect_movie, effect_file], env)
            assert audio_peak(effect_movie) > 0.0, kind

        # Track.order is the toolkit's display order. Reordering the lanes must
        # change which opaque clip is on top in the program monitor as well.
        ordered = json.loads(json.dumps(document))
        ordered["filters"] = []
        ordered["filter_params"] = []
        ordered_project = root / "ordered.air"
        ordered_project.write_text(json.dumps(ordered))
        top_before = root / "top-before.png"
        run([args.binary, "preview", top_before, ordered_project], env)
        assert pixel(top_before, 320, 180)[2] > 180
        base_track = ordered["clips"][0]["track"]
        over_track = ordered["clips"][1]["track"]
        for track in ordered["tracks"]:
            if track["id"] == base_track:
                track["order"] = 3
            if track["id"] == over_track:
                track["order"] = 2
        ordered_project.write_text(json.dumps(ordered))
        top_after = root / "top-after.png"
        run([args.binary, "preview", top_after, ordered_project], env)
        assert pixel(top_after, 320, 180)[0] > 180

        graded = json.loads(json.dumps(document))
        graded["sources"][0]["path"] = str(gray)
        graded["sources"][0]["has_audio"] = False
        graded["clips"] = [graded["clips"][0]]
        graded["filters"] = []
        graded["filter_params"] = []
        grade_project = root / "grade.air"
        grade_project.write_text(json.dumps(graded))
        plain_grade = root / "plain-grade.png"
        run([args.binary, "preview", plain_grade, grade_project], env)
        original_gray = pixel(plain_grade, 320, 180)[0]
        graded["filters"] = [dict(id=11, clip=base_id, kind="gamma", order=0,
                                   enabled=True)]
        graded["filter_params"] = [dict(filter=11, name="level", value=1.8)]
        graded["next_id"] = 12
        grade_project.write_text(json.dumps(graded))
        gamma_preview = root / "gamma.png"
        run([args.binary, "preview", gamma_preview, grade_project], env)
        assert pixel(gamma_preview, 320, 180)[0] > original_gray + 25
        graded["filters"][0]["kind"] = "sepia"
        graded["filter_params"][0] = dict(filter=11, name="amount", value=1.0)
        grade_project.write_text(json.dumps(graded))
        sepia_preview = root / "sepia.png"
        run([args.binary, "preview", sepia_preview, grade_project], env)
        sepia_pixel = pixel(sepia_preview, 320, 180)
        assert sepia_pixel[0] > sepia_pixel[1] > sepia_pixel[2], sepia_pixel
        graded["filters"][0]["kind"] = "vignette"
        graded["filter_params"][0] = dict(filter=11, name="amount", value=1.0)
        grade_project.write_text(json.dumps(graded))
        vignette_preview = root / "vignette.png"
        run([args.binary, "preview", vignette_preview, grade_project], env)
        assert pixel(vignette_preview, 30, 30)[0] < pixel(plain_grade, 30, 30)[0] - 20
        vignette_edges = []
        for softness in (0.0, 1.0):
            graded["filter_params"] = [dict(filter=11, name="amount", value=1.0),
                                       dict(filter=11, name="softness", value=softness)]
            grade_project.write_text(json.dumps(graded))
            soft_preview = root / f"vignette-soft-{softness}.png"
            soft_movie = root / f"vignette-soft-{softness}.mp4"
            run([args.binary, "preview", soft_preview, grade_project], env)
            run([args.binary, "export", soft_movie, grade_project], env)
            edge_rgb = pixel(soft_preview, 100, 180)
            movie_rgb = pixel(soft_movie, 300, 540, True)
            assert max(abs(a - b) for a, b in zip(edge_rgb, movie_rgb)) <= 18
            vignette_edges.append(edge_rgb[0])
        assert vignette_edges[0] > vignette_edges[1] + 20, vignette_edges
        graded["filters"][0]["kind"] = "levels"
        graded["filter_params"] = [dict(filter=11, name="white", value=0.7)]
        grade_project.write_text(json.dumps(graded))
        levels_preview = root / "levels.png"
        run([args.binary, "preview", levels_preview, grade_project], env)
        assert pixel(levels_preview, 320, 180)[0] > original_gray + 20
        graded["filters"][0]["kind"] = "crop"
        graded["filter_params"] = [dict(filter=11, name=edge, value=0.2)
                                   for edge in ("left", "top", "right", "bottom")]
        grade_project.write_text(json.dumps(graded))
        crop_preview = root / "crop.png"
        run([args.binary, "preview", crop_preview, grade_project], env)
        assert pixel(crop_preview, 30, 30)[0] < 20
        graded["filter_params"] = [dict(filter=11, name=edge, value=value)
                                   for edge, value in (("left", 0.30), ("top", 0.10),
                                                       ("right", 0.05), ("bottom", 0.25))]
        grade_project.write_text(json.dumps(graded))
        asymmetric_preview = root / "asymmetric-crop.png"
        asymmetric_movie = root / "asymmetric-crop.mp4"
        run([args.binary, "preview", asymmetric_preview, grade_project], env)
        run([args.binary, "export", asymmetric_movie, grade_project], env)
        for point, black in (((100, 180), True), ((320, 20), True),
                             ((320, 320), True), ((580, 180), False),
                             ((320, 180), False)):
            preview_rgb = pixel(asymmetric_preview, *point)
            movie_rgb = pixel(asymmetric_movie, point[0] * 3, point[1] * 3, True)
            assert (preview_rgb[0] < 20) == black, (point, preview_rgb)
            assert max(abs(a - b) for a, b in zip(preview_rgb, movie_rgb)) <= 18
        graded["filters"][0]["kind"] = "white_balance"
        graded["filter_params"] = [dict(filter=11, name="temperature", value=100.0)]
        grade_project.write_text(json.dumps(graded))
        warm_preview = root / "warm.png"
        warm_movie = root / "warm.mp4"
        run([args.binary, "preview", warm_preview, grade_project], env)
        run([args.binary, "export", warm_movie, grade_project], env)
        warm = pixel(warm_preview, 320, 180)
        assert 185 < warm[0] < 245 and 10 < warm[2] < 80, warm
        assert max(abs(a - b) for a, b in zip(warm,
            pixel(warm_movie, 960, 540, True, 0.1))) <= 18
        graded["filter_params"] = [dict(filter=11, name="tint", value=100.0)]
        grade_project.write_text(json.dumps(graded))
        tint_preview = root / "tint.png"
        tint_movie = root / "tint.mp4"
        run([args.binary, "preview", tint_preview, grade_project], env)
        run([args.binary, "export", tint_movie, grade_project], env)
        tinted = pixel(tint_preview, 320, 180)
        assert tinted[1] > tinted[0] + 45 and tinted[1] > tinted[2] + 45, tinted
        assert max(abs(a - b) for a, b in zip(tinted,
            pixel(tint_movie, 960, 540, True, 0.1))) <= 18
        graded["filters"].append(dict(id=12, clip=base_id, kind="lift_gamma_gain",
                                      order=1, enabled=True))
        graded["filter_params"].append(dict(filter=12, name="gain", value=0.8))
        graded["next_id"] = 13
        grade_project.write_text(json.dumps(graded))
        tinted_gain_preview = root / "tinted-gain.png"
        run([args.binary, "preview", tinted_gain_preview, grade_project], env)
        tinted_gain = pixel(tinted_gain_preview, 320, 180)
        assert tinted_gain[1] < tinted[1] - 20, (tinted_gain, tinted)
        graded["filters"][0]["order"] = 1
        graded["filters"][1]["order"] = 0
        grade_project.write_text(json.dumps(graded))
        reversed_gain_preview = root / "reversed-gain.png"
        run([args.binary, "preview", reversed_gain_preview, grade_project], env)
        assert max(abs(a - b) for a, b in zip(tinted_gain,
            pixel(reversed_gain_preview, 320, 180))) <= 2
        cube = root / "swap channels.cube"
        cube.write_text("TITLE \"RB swap\"\nLUT_3D_SIZE 2\n"
                        "DOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" +
                        "".join(f"{blue_value} {green_value} {red_value}\n"
                                for blue_value in (0, 1)
                                for green_value in (0, 1)
                                for red_value in (0, 1)))
        lut_doc = json.loads(json.dumps(document))
        lut_doc["clips"] = [lut_doc["clips"][0]]
        lut_doc["filters"] = [dict(id=11, clip=base_id, kind="lut3d",
                                   order=0, enabled=True)]
        lut_doc["filter_params"] = [dict(filter=11, name="amount", value=1.0)]
        lut_doc["filter_text_params"] = [dict(filter=11, name="path", value=str(cube))]
        lut_doc["next_id"] = 12
        lut_project = root / "lut.air"
        lut_project.write_text(json.dumps(lut_doc))
        lut_preview = root / "lut.png"
        lut_movie = root / "lut.mp4"
        run([args.binary, "preview", lut_preview, lut_project], env)
        run([args.binary, "export", lut_movie, lut_project], env)
        swapped = pixel(lut_preview, 320, 180)
        assert swapped[2] > 200 and swapped[0] < 40, swapped
        assert max(abs(a - b) for a, b in zip(swapped,
            pixel(lut_movie, 960, 540, True, 0.1))) <= 18
        lut_doc["filter_params"][0]["value"] = 0.5
        lut_project.write_text(json.dumps(lut_doc))
        half_lut_preview = root / "half-lut.png"
        run([args.binary, "preview", half_lut_preview, lut_project], env)
        half_swapped = pixel(half_lut_preview, 320, 180)
        assert 85 < half_swapped[0] < 170 and 85 < half_swapped[2] < 170, half_swapped
        lut_doc["names"].append("lut3d.amount")
        amount_id = len(lut_doc["names"])
        lut_doc["keys"] = [dict(clip=base_id, owner=lut_doc["active"],
                                param=amount_id, frame=frame, value=value, interp=0)
                           for frame, value in ((0, 0.0), (11, 1.0))]
        lut_doc["program"]["frame"] = 0
        lut_project.write_text(json.dumps(lut_doc))
        keyed_lut_start = root / "keyed-lut-start.png"
        run([args.binary, "preview", keyed_lut_start, lut_project], env)
        lut_doc["program"]["frame"] = 11
        lut_project.write_text(json.dumps(lut_doc))
        keyed_lut_end = root / "keyed-lut-end.png"
        run([args.binary, "preview", keyed_lut_end, lut_project], env)
        assert pixel(keyed_lut_start, 320, 180)[0] > 200
        assert pixel(keyed_lut_end, 320, 180)[2] > 200
        lut_doc["keys"] = []
        lut_doc["filter_text_params"][0]["value"] = str(root / "missing.cube")
        lut_project.write_text(json.dumps(lut_doc))
        missing_lut = subprocess.run([str(args.binary), "preview",
                                      str(root / "missing-lut.png"), str(lut_project)],
                                     env=env, capture_output=True, text=True, timeout=30)
        assert missing_lut.returncode != 0 and "LUT file is unavailable" in missing_lut.stdout
        cube.write_text("LUT_3D_SIZE 2\n0 0 0\n")
        lut_doc["filter_text_params"][0]["value"] = str(cube)
        lut_project.write_text(json.dumps(lut_doc))
        malformed_lut = subprocess.run([str(args.binary), "preview",
                                        str(root / "malformed-lut.png"), str(lut_project)],
                                       env=env, capture_output=True, text=True, timeout=30)
        assert malformed_lut.returncode != 0 and "supported 3D .cube" in malformed_lut.stdout
        title_doc = json.loads(json.dumps(document))
        title_doc["clips"] = [title_doc["clips"][0]]
        title_doc["filters"] = [dict(id=11, clip=base_id, kind="text",
                                     order=0, enabled=True)]
        title_doc["filter_params"] = [dict(filter=11, name="size", value=36.0),
                                       dict(filter=11, name="x", value=0.0),
                                       dict(filter=11, name="y", value=0.0)]
        title_doc["filter_text_params"] = [dict(filter=11, name="content", value="AIR")]
        title_doc["next_id"] = 12
        title_project = root / "title.air"
        title_project.write_text(json.dumps(title_doc))
        title_preview = root / "title.png"
        title_movie = root / "title.mp4"
        run([args.binary, "preview", title_preview, title_project], env)
        run([args.binary, "export", title_movie, title_project], env)
        title_points = light_points(title_preview, (170, 130, 470, 230))
        encoded_title = light_points(title_movie, (170, 130, 470, 230), True)
        assert len(title_points) > 40, len(title_points)
        assert abs(len(encoded_title) - len(title_points)) < len(title_points) * 0.4
        title_doc["filters"].append(dict(id=12, clip=base_id, kind="brightness",
                                         order=1, enabled=True))
        title_doc["filter_params"].append(dict(filter=12, name="level", value=0.5))
        title_doc["next_id"] = 13
        title_project.write_text(json.dumps(title_doc))
        graded_title = root / "graded-title.png"
        run([args.binary, "preview", graded_title, title_project], env)
        assert 100 <= pixel(graded_title, 30, 30)[0] <= 150
        title_doc["filters"].pop()
        title_doc["filter_params"].pop()
        title_doc["next_id"] = 12
        title_doc["filter_text_params"][0]["value"] = "Café"
        title_project.write_text(json.dumps(title_doc))
        unsupported_glyph = subprocess.run([str(args.binary), "preview",
                                            str(root / "unicode-title.png"),
                                            str(title_project)], env=env,
                                           capture_output=True, text=True, timeout=30)
        assert unsupported_glyph.returncode != 0 and "printable ASCII" in unsupported_glyph.stdout
        title_doc["filter_text_params"][0]["value"] = "AIR"
        title_doc["filter_params"][1]["value"] = 0.5
        title_project.write_text(json.dumps(title_doc))
        moved_title = root / "title-right.png"
        run([args.binary, "preview", moved_title, title_project], env)
        moved_points = light_points(moved_title, (170, 130, 620, 230))
        assert sum(moved_points) / len(moved_points) > sum(title_points) / len(title_points) + 120
        title_doc["filter_params"][1]["value"] = 0.0
        title_doc["filter_params"][2]["value"] = -0.5
        title_project.write_text(json.dumps(title_doc))
        raised_title = root / "title-raised.png"
        run([args.binary, "preview", raised_title, title_project], env)
        assert len(light_points(raised_title, (170, 50, 470, 135))) > 40
        assert len(light_points(title_preview, (170, 50, 470, 135))) < 10
        title_doc["filter_params"][2]["value"] = 0.0
        title_doc["filter_params"][0]["value"] = 72.0
        title_project.write_text(json.dumps(title_doc))
        large_title = root / "title-large.png"
        run([args.binary, "preview", large_title, title_project], env)
        assert len(light_points(large_title, (170, 130, 470, 250))) > len(title_points) * 1.7
        title_doc["filter_params"][0]["value"] = 36.0
        title_doc["names"].append("text.x")
        title_doc["keys"] = [dict(clip=base_id, owner=title_doc["active"],
                                  param=len(title_doc["names"]), frame=frame,
                                  value=value, interp=0)
                             for frame, value in ((0, 0.0), (11, 0.5))]
        title_doc["program"]["frame"] = 11
        title_project.write_text(json.dumps(title_doc))
        keyed_title = root / "title-keyed.png"
        run([args.binary, "preview", keyed_title, title_project], env)
        keyed_points = light_points(keyed_title, (170, 130, 620, 230))
        assert sum(keyed_points) / len(keyed_points) > sum(title_points) / len(title_points) + 120
        title_doc["filters"][0]["kind"] = "timer"
        title_doc["keys"] = []
        title_doc["filter_text_params"] = []
        title_doc["filter_params"] = [dict(filter=11, name="size", value=36.0)]
        title_doc["program"]["frame"] = 0
        title_project.write_text(json.dumps(title_doc))
        timer_start = root / "timer-start.png"
        run([args.binary, "preview", timer_start, title_project], env)
        title_doc["program"]["frame"] = 11
        title_project.write_text(json.dumps(title_doc))
        timer_end = root / "timer-end.png"
        timer_movie = root / "timer.mp4"
        run([args.binary, "preview", timer_end, title_project], env)
        run([args.binary, "export", timer_movie, title_project], env)
        start_points = light_points(timer_start, (0, 0, 220, 65))
        end_points = light_points(timer_end, (0, 0, 220, 65))
        encoded_timer = light_points(timer_movie, (0, 0, 220, 65), True, 11 / 30)
        assert len(start_points) > 80 and len(end_points) > 80
        assert start_points != end_points
        assert abs(len(encoded_timer) - len(end_points)) < len(end_points) * 0.4
        title_doc["filter_params"][0]["value"] = 72.0
        title_project.write_text(json.dumps(title_doc))
        large_timer = root / "timer-large.png"
        run([args.binary, "preview", large_timer, title_project], env)
        assert len(light_points(large_timer, (0, 0, 500, 120))) > len(end_points) * 1.7
        upper_title = json.loads(json.dumps(document))
        upper_title["filters"].append(dict(id=12, clip=10, kind="text",
                                           order=1, enabled=True))
        upper_title["filter_text_params"] = [dict(filter=12, name="content", value="AIR")]
        upper_title["next_id"] = 13
        upper_project = root / "upper-title.air"
        upper_project.write_text(json.dumps(upper_title))
        upper_preview = root / "upper-title.png"
        upper_movie = root / "upper-title.mp4"
        run([args.binary, "preview", upper_preview, upper_project], env)
        run([args.binary, "export", upper_movie, upper_project], env)
        upper_points = light_points(upper_preview, (170, 130, 470, 230), threshold=90)
        upper_encoded = light_points(upper_movie, (170, 130, 470, 230), True,
                                     threshold=90)
        assert len(upper_points) > 40, len(upper_points)
        assert abs(len(upper_encoded) - len(upper_points)) < len(upper_points) * 0.5
        keyed = json.loads(json.dumps(document))
        keyed["sources"][1]["path"] = str(key_green)
        keyed["filters"][0]["kind"] = "chroma_key"
        keyed["filter_params"] = [dict(filter=11, name="hue", value=120.0),
                                  dict(filter=11, name="tolerance", value=0.25),
                                  dict(filter=11, name="softness", value=0.1)]
        keyed_project = root / "chroma.air"
        keyed_project.write_text(json.dumps(keyed))
        chroma_preview = root / "chroma.png"
        chroma_movie = root / "chroma.mp4"
        run([args.binary, "preview", chroma_preview, keyed_project], env)
        run([args.binary, "export", chroma_movie, keyed_project], env)
        chroma_pixel = pixel(chroma_preview, 320, 180)
        assert chroma_pixel[0] > 180 and chroma_pixel[1] < 80, chroma_pixel
        encoded_chroma = pixel(chroma_movie, 960, 540, True)
        assert max(abs(a - b) for a, b in zip(chroma_pixel, encoded_chroma)) <= 18

        layered = json.loads(json.dumps(document))
        layered["sources"].append(dict(source, id=20, path=str(green), name="green",
                                       has_audio=False))
        top_track = next(track for track in layered["tracks"] if track["id"] == over_track)
        layered["tracks"].append(dict(top_track, id=21, name="V3", order=4))
        layered["clips"].append(dict(layered["clips"][0], id=22, source=20, track=21))
        layered["filters"].append(dict(id=23, clip=22, kind="opacity", order=0,
                                        enabled=True))
        layered["filter_params"].append(dict(filter=23, name="level", value=0.5))
        layered["next_id"] = 24
        layer_project = root / "three-layers.air"
        layer_project.write_text(json.dumps(layered))
        layer_preview = root / "three-layers.png"
        layer_movie = root / "three-layers.mp4"
        run([args.binary, "preview", layer_preview, layer_project], env)
        run([args.binary, "export", layer_movie, layer_project], env)
        third_preview = pixel(layer_preview, 320, 180)
        third_encoded = pixel(layer_movie, 960, 540, True)
        assert all(45 <= value <= 85 for value in third_preview), third_preview
        assert max(abs(a - b) for a, b in zip(third_preview, third_encoded)) <= 18, (
            third_preview, third_encoded)
        assert not list(root.rglob("*.layer*.rgba")), "layer fold left raw frames behind"
        graded_top = json.loads(json.dumps(layered))
        graded_top["filters"].append(dict(id=24, clip=22, kind="brightness",
                                          order=1, enabled=True))
        graded_top["filter_params"].append(dict(filter=24, name="level", value=0.0))
        graded_top["next_id"] = 25
        graded_top_project = root / "graded-top.air"
        graded_top_project.write_text(json.dumps(graded_top))
        graded_top_preview = root / "graded-top.png"
        graded_top_movie = root / "graded-top.mp4"
        run([args.binary, "preview", graded_top_preview, graded_top_project], env)
        run([args.binary, "export", graded_top_movie, graded_top_project], env)
        top_color = pixel(graded_top_preview, 320, 180)
        top_encoded = pixel(graded_top_movie, 960, 540, True)
        assert 45 <= top_color[0] <= 85 and top_color[1] < 20 and 45 <= top_color[2] <= 85, top_color
        assert max(abs(a - b) for a, b in zip(top_color, top_encoded)) <= 18
        assert not list(root.rglob("*.preclip.rgba")), "overlay prepass left raw frames behind"

        captioned = json.loads(json.dumps(layered))
        captioned["subtitles"] = [
            dict(id=24, owner=captioned["active"], start=0, finish=6,
                 text="AIR caption"),
            dict(id=25, owner=captioned["active"], start=6, finish=12,
                 text="NEXT caption"),
        ]
        captioned["next_id"] = 26
        caption_project = root / "caption.air"
        caption_project.write_text(json.dumps(captioned))
        caption_preview = root / "caption.png"
        caption_movie = root / "caption.mp4"
        caption_env = dict(env, GENESIS_SCRATCH=str(root / "fresh-caption-scratch"))
        run([args.binary, "preview", caption_preview, caption_project], caption_env)
        run([args.binary, "export", caption_movie, caption_project], caption_env)
        plain_view, with_caption = rgb_frame(layer_preview), rgb_frame(caption_preview)
        changed = sum(abs(a - b) > 30 for a, b in zip(plain_view, with_caption))
        assert changed > 300, changed
        plain_movie, captioned_movie = rgb_frame(layer_movie, True), rgb_frame(caption_movie, True)
        changed_movie = sum(abs(a - b) > 30 for a, b in zip(plain_movie, captioned_movie))
        assert changed_movie > 300, changed_movie
        second_cue = rgb_frame(caption_movie, True, 0.3)
        changed_cue = sum(abs(a - b) > 30 for a, b in zip(captioned_movie, second_cue))
        assert changed_cue > 100, changed_cue
        assert not list(root.rglob("*.subtitle.rgba")), "caption raster left behind"

        ramp = root / "ramp.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=red:s=320x180:r=30",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
             "-af", "afade=t=in:st=0:d=0.4", "-t", "0.4",
             "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", ramp])
        sped = json.loads(json.dumps(document))
        sped["sources"][0]["path"] = str(ramp)
        sped["clips"] = [sped["clips"][0]]
        sped["clips"][0]["length"] = 6
        sped["clips"][0]["speed"] = 2.0
        sped["clips"][0]["reverse"] = True
        sped["filters"] = []
        sped["filter_params"] = []
        speed_project = root / "reverse-speed.air"
        speed_project.write_text(json.dumps(sped))
        speed_movie = root / "reverse-speed.mp4"
        run([args.binary, "export", speed_movie, speed_project], env)
        first_loudness = audio_rms_window(speed_movie, 0.0, 0.04)
        last_loudness = audio_rms_window(speed_movie, 0.15, 0.04)
        assert first_loudness > last_loudness * 1.7, (first_loudness, last_loudness)
        sped["clips"][0]["length"] = 12
        speed_project.write_text(json.dumps(sped))
        overrun = subprocess.run([str(args.binary), "export", str(root / "overrun.mp4"),
                                  str(speed_project)], env=env, capture_output=True,
                                 text=True, timeout=30)
        assert overrun.returncode != 0 and "exceed its source frames" in overrun.stdout
        assert not (root / "overrun.mp4").exists()
        sped["clips"][0]["length"] = 6
        sped["clips"][0]["speed"] = 0.0
        sped["clips"][0]["reverse"] = False
        speed_project.write_text(json.dumps(sped))
        freeze_movie = root / "freeze.mp4"
        run([args.binary, "export", freeze_movie, speed_project], env)
        assert audio_peak(freeze_movie) == 0.0

        tone = root / "audio only.wav"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=660:sample_rate=48000", "-t", "0.4", tone])
        audio_project = root / "audio.air"
        run([args.binary, "probe", tone, root / "audio-panel.png", audio_project], env)
        audio_doc = json.loads(audio_project.read_text())
        assert audio_doc["sources"][0]["has_audio"] and not audio_doc["sources"][0]["has_video"]
        assert audio_doc["clips"][0]["track"] == 4
        audio_movie = root / "audio-only.mp4"
        run([args.binary, "export", audio_movie, audio_project], env)
        assert audio_peak(audio_movie) > 0.01, "audio-only timeline was silent"
        audio_doc["tracks"][1]["pan"] = 1.0
        audio_project.write_text(json.dumps(audio_doc))
        panned_movie = root / "panned.mp4"
        run([args.binary, "export", panned_movie, audio_project], env)
        left = audio_peak(panned_movie, "FL")
        right = audio_peak(panned_movie, "FR")
        assert right > 0.01 and right > left * 3, (left, right)

        # A touching cut uses the worker's actual crossfade path in both preview and export.
        dissolve = json.loads(project.read_text())
        dissolve["clips"][1]["track"] = 5
        dissolve["clips"][1]["start"] = 12
        dissolve["filters"] = []
        dissolve["filter_params"] = []
        dissolve["program"]["frame"] = 12
        dissolve["names"].append("crossfade")
        dissolve["transitions"] = [dict(id=11, owner=dissolve["active"], track=5,
                                         center=12, duration=6, kind=len(dissolve["names"]))]
        dissolve["next_id"] = 12
        dissolve_project = root / "dissolve.air"
        dissolve_project.write_text(json.dumps(dissolve))
        dissolve_preview = root / "dissolve.png"
        dissolve_movie = root / "dissolve.mp4"
        run([args.binary, "preview", dissolve_preview, dissolve_project], env)
        run([args.binary, "export", dissolve_movie, dissolve_project], env)
        mid = pixel(dissolve_preview, 320, 180)
        encoded_mid = pixel(dissolve_movie, 960, 540, True, 0.4)
        assert 85 <= mid[0] <= 170 and 85 <= mid[2] <= 170, mid
        assert max(abs(a - b) for a, b in zip(mid, encoded_mid)) <= 18, (mid, encoded_mid)
        titled_dissolve = json.loads(json.dumps(dissolve))
        titled_dissolve["filters"] = [dict(id=12, clip=dissolve["clips"][0]["id"],
                                           kind="text", order=0, enabled=True),
                                       dict(id=13, clip=dissolve["clips"][1]["id"],
                                           kind="text", order=0, enabled=True)]
        titled_dissolve["filter_params"] = [dict(filter=12, name="x", value=-0.35),
                                            dict(filter=13, name="x", value=0.35)]
        titled_dissolve["filter_text_params"] = [dict(filter=12, name="content", value="OUT"),
                                                 dict(filter=13, name="content", value="IN")]
        titled_dissolve["next_id"] = 14
        titled_project = root / "titled-dissolve.air"
        titled_project.write_text(json.dumps(titled_dissolve))
        titled_preview = root / "titled-dissolve.png"
        titled_movie = root / "titled-dissolve.mp4"
        run([args.binary, "preview", titled_preview, titled_project], env)
        run([args.binary, "export", titled_movie, titled_project], env)
        for box in ((0, 130, 220, 240), (430, 130, 640, 240)):
            preview_points = light_points(titled_preview, box, threshold=90)
            movie_points = light_points(titled_movie, box, True, 0.4, threshold=90)
            assert len(preview_points) > 20, (box, len(preview_points))
            assert abs(len(movie_points) - len(preview_points)) < len(preview_points) * 0.5
        ui_dissolve = json.loads(json.dumps(dissolve))
        ui_dissolve["names"][-1] = "dissolve"
        ui_dissolve_project = root / "ui-dissolve.air"
        ui_dissolve_project.write_text(json.dumps(ui_dissolve))
        ui_dissolve_preview = root / "ui-dissolve.png"
        ui_dissolve_movie = root / "ui-dissolve.mp4"
        run([args.binary, "preview", ui_dissolve_preview, ui_dissolve_project], env)
        run([args.binary, "export", ui_dissolve_movie, ui_dissolve_project], env)
        dissolve_color = pixel(ui_dissolve_preview, 320, 180)
        dissolve_encoded = pixel(ui_dissolve_movie, 960, 540, True, 0.4)
        assert dissolve_color[2] > 200 and dissolve_color[0] < 30, dissolve_color
        assert max(abs(a - b) for a, b in zip(dissolve_color, dissolve_encoded)) <= 18
        overlap = json.loads(json.dumps(dissolve))
        overlap["clips"][1]["start"] = 8
        overlap["transitions"][0]["center"] = 10  # midpoint of [8, 12)
        overlap["program"]["frame"] = 10
        overlap_project = root / "overlap.air"
        overlap_project.write_text(json.dumps(overlap))
        overlap_preview = root / "overlap.png"
        overlap_movie = root / "overlap.mp4"
        run([args.binary, "preview", overlap_preview, overlap_project], env)
        run([args.binary, "export", overlap_movie, overlap_project], env)
        overlap_color = pixel(overlap_preview, 320, 180)
        overlap_encoded = pixel(overlap_movie, 960, 540, True, 10 / 30)
        assert 85 <= overlap_color[0] <= 170 and 85 <= overlap_color[2] <= 170, overlap_color
        assert max(abs(a - b) for a, b in zip(overlap_color, overlap_encoded)) <= 18
        short_gap = json.loads(json.dumps(dissolve))
        short_gap["clips"][1]["start"] = 16
        short_gap_project = root / "short-gap.air"
        short_gap_project.write_text(json.dumps(short_gap))
        short_gap_preview = root / "short-gap.png"
        short_gap_movie = root / "short-gap.mp4"
        run([args.binary, "preview", short_gap_preview, short_gap_project], env)
        run([args.binary, "export", short_gap_movie, short_gap_project], env)
        gap_color = pixel(short_gap_preview, 320, 180)
        gap_encoded = pixel(short_gap_movie, 960, 540, True, 0.4)
        assert 85 <= gap_color[0] <= 170 and 85 <= gap_color[2] <= 170, gap_color
        assert max(abs(a - b) for a, b in zip(gap_color, gap_encoded)) <= 18

        # Distinct points prove that each named transition reaches its intended
        # geometry, and that the exported frame agrees with the monitor.
        transition_sides = {
            "wipe_lr": ((64, 180), (576, 180)),
            "wipe_rl": ((576, 180), (64, 180)),
            "wipe_up": ((320, 324), (320, 36)),
            "wipe_down": ((320, 36), (320, 324)),
            "slide_lr": ((576, 180), (64, 180)),
            "zoom": ((320, 180), (64, 36)),
            "iris": ((320, 180), (64, 36)),
            "clock": ((64, 36), (576, 36)),
            "barn_door": ((320, 180), (64, 180)),
        }
        for name, (blue_at, red_at) in transition_sides.items():
            variant = json.loads(json.dumps(dissolve))
            variant["names"][-1] = name
            variant_project = root / f"{name}.air"
            variant_project.write_text(json.dumps(variant))
            variant_preview = root / f"{name}.png"
            variant_movie = root / f"{name}.mp4"
            run([args.binary, "preview", variant_preview, variant_project], env)
            run([args.binary, "export", variant_movie, variant_project], env)
            blue_pixel = pixel(variant_preview, *blue_at)
            red_pixel = pixel(variant_preview, *red_at)
            assert blue_pixel[2] > 200 and blue_pixel[0] < 40, (name, blue_pixel)
            assert red_pixel[0] > 200 and red_pixel[2] < 40, (name, red_pixel)
            for point, preview_pixel in ((blue_at, blue_pixel), (red_at, red_pixel)):
                encoded_pixel = pixel(variant_movie, point[0] * 3, point[1] * 3,
                                      True, 0.4)
                assert max(abs(a - b) for a, b in zip(preview_pixel, encoded_pixel)) <= 18, (
                    name, point, preview_pixel, encoded_pixel)

        # Unsupported edits must fail visibly rather than produce a plausible but wrong file.
        document["filters"].append(dict(id=12, clip=8, kind="stabilize",
                                        order=0, enabled=True))
        document["next_id"] = 13
        project.write_text(json.dumps(document))
        bad = subprocess.run([str(args.binary), "export", str(root / "bad.mp4"), str(project)],
                             env=env, capture_output=True, text=True, timeout=30)
        assert bad.returncode != 0 and "unsupported video filter" in bad.stdout
        assert not (root / "bad.mp4").exists()
        audio_bad = json.loads(json.dumps(document))
        audio_bad["filters"] = [dict(id=12, clip=base_id, kind="normalize",
                                     order=0, enabled=True)]
        audio_bad["filter_params"] = [dict(filter=12, name="target", value=0.0)]
        audio_bad["next_id"] = 13
        bad_audio_project = root / "bad-audio.air"
        bad_audio_project.write_text(json.dumps(audio_bad))
        bad_audio = subprocess.run([str(args.binary), "export", str(root / "bad-audio.mp4"),
                                    str(bad_audio_project)], env=env, capture_output=True,
                                   text=True, timeout=30)
        assert bad_audio.returncode != 0 and "unsupported audio filter" in bad_audio.stdout
        assert not (root / "bad-audio.mp4").exists()
        broken_fx = json.loads(json.dumps(audio_bad))
        broken_fx["filters"][0]["kind"] = "notch"
        broken_fx["filter_params"] = [dict(filter=12, name="frequency", value=1000.0),
                                       dict(filter=12, name="width", value=-1.0)]
        broken_project = root / "broken-filter.air"
        broken_project.write_text(json.dumps(broken_fx))
        broken = subprocess.run([str(args.binary), "export", str(root / "broken-filter.mp4"),
                                 str(broken_project)], env=env, capture_output=True,
                                text=True, timeout=30)
        assert broken.returncode != 0 and "audio filter chain" in broken.stdout, broken.stdout
        assert not (root / "broken-filter.mp4").exists()
        print(f"real media: purple preview {seen}, encoded {encoded}; "
              f"keyframed fade {first_color} to {middle_color}, "
              f"base opacity {base_color}; "
              f"mask center/edge {mask_center}/{mask_edge}, inverted "
              f"{inverse_center}/{inverse_edge}; "
              f"12 frames and 24 fps 9-frame AV, 2x speed filter (15-frame AV), graded overlays on two "
              f"and three layers, timed captions, "
              f"all 11 transition kinds, overlap and short gap, reverse-speed audio, "
              f"white balance temperature/tint, LUT3D mix/keys and invalid-file refusal, "
              f"Text/Timer preview and MP4 with keyed placement, all 12 blend modes, "
              f"asymmetric crop, rotated upper clip, half-strength simple effects, "
              f"vignette softness, "
              f"graded picture/audio filters, audible AAC and "
              f"audio-only timeline; unsupported edit refused")


if __name__ == "__main__":
    main()
