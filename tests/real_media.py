#!/usr/bin/env python3
"""Bounded preview/export integration test against a source-built gcompose worker."""
import argparse
from array import array
import json
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
        red, blue = root / "red clip.mp4", root / "blue clip.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=red:s=320x180:r=30",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", "-c:a", "aac", red])
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=30",
             "-t", "0.4", "-c:v", "libx264", "-preset", "ultrafast",
             "-pix_fmt", "yuv420p", blue])
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

        media = run(["ffprobe", "-v", "error", "-show_entries",
                     "stream=codec_type,nb_frames,width,height", "-of", "json",
                     movie])
        streams = json.loads(media.stdout)["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        assert (video["width"], video["height"], int(video["nb_frames"])) == (1920, 1080, 12)
        assert any(s["codec_type"] == "audio" for s in streams), streams
        assert audio_peak(movie) > 0.01, "exported audio is silent"

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
        audio_bad["filters"] = [dict(id=12, clip=base_id, kind="phaser",
                                     order=0, enabled=True)]
        audio_bad["filter_params"] = []
        audio_bad["next_id"] = 13
        bad_audio_project = root / "bad-audio.air"
        bad_audio_project.write_text(json.dumps(audio_bad))
        bad_audio = subprocess.run([str(args.binary), "export", str(root / "bad-audio.mp4"),
                                    str(bad_audio_project)], env=env, capture_output=True,
                                   text=True, timeout=30)
        assert bad_audio.returncode != 0 and "unsupported audio filter" in bad_audio.stdout
        assert not (root / "bad-audio.mp4").exists()
        print(f"real media: purple preview {seen}, encoded {encoded}; "
              f"12 frames, crossfade, mixed picture/audio filters, audible AAC and "
              f"audio-only timeline; unsupported edit refused")


if __name__ == "__main__":
    main()
