"""Saved AIR projects must preserve authored overlap sums in audition and export."""
import argparse
from array import array
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

from media_runtime import tool

SR = 48000
FRAMES = 19200
FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, env=None):
    done = subprocess.run(list(map(str, argv)), env=env, capture_output=True,
                          timeout=60, creationflags=FLAGS)
    assert done.returncode == 0, (done.returncode, done.stdout, done.stderr)
    return done


def document(paths, order):
    # The three source identities keep their own tracks and clip IDs. Only clip
    # storage order changes, as it can after project editing/serialization.
    result = dict(schema="air.editor.project", revision=2, active=2,
                  source_bounds=0, monitor_source=7, next_id=30,
                  program=dict(playing=False, frame=0, mark_in=-1, mark_out=-1,
                               rate=1, looping=False),
                  monitor=dict(playing=False, frame=0, mark_in=-1, mark_out=-1,
                               rate=1, looping=False),
                  bins=[dict(id=1, name="Media", parent=0)],
                  sequences=[dict(id=2, name="Overlap", fps=30, width=16, height=16)],
                  sources=[], tracks=[], clips=[], transitions=[], keys=[],
                  markers=[], subtitles=[], filters=[], filter_params=[],
                  filter_text_params=[], names=[])
    for n, path in enumerate(paths):
        result["sources"].append(dict(id=7+n, path=str(path), name=path.name, bin=1,
                                     frames=12, fps=30, width=0, height=0,
                                     has_video=False, has_audio=True, audio_rate=SR,
                                     audio_channels=2, online=True))
        result["tracks"].append(dict(id=3+n, owner=2, kind=1, name=f"A{n+1}",
                                    order=n, hidden=False, muted=False, locked=False,
                                    solo=False, gain=1, pan=0, height=44))
    for n in order:
        result["clips"].append(dict(id=20+n, owner=2, source=7+n, nested=0,
                                   source_in=0, length=12, start=0, track=3+n,
                                   group=0, enabled=True, selected=False,
                                   fade_in=0, fade_out=0, gain=1, pan=0,
                                   speed=1, reverse=False))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    results = []
    with tempfile.TemporaryDirectory(prefix="genesis-project-overlap-") as temporary:
        root = Path(temporary)
        paths = [root / f"source {n} 日本語.wav" for n in range(3)]
        authored = (26214, 26214, -26214)
        for path, value in zip(paths, authored):
            with wave.open(str(path), "wb") as output:
                output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
                output.writeframes(array("h", [value] * FRAMES * 2).tobytes())
        source_hashes = [sha(path) for path in paths]
        cases = [(f"order-{n}", document(paths, order), 26214/32768, FRAMES)
                 for n, order in enumerate(itertools.permutations(range(3)))]
        gain = document(paths, (0, 1, 2))
        for track in gain["tracks"]:
            track["gain"] = 0.5
        cases.append(("track-gain", gain, 13107/32768, FRAMES))
        muted = document(paths, (0, 1, 2))
        muted["tracks"][1]["muted"] = True
        cases.append(("track-mute-cancellation", muted, 0, FRAMES))
        solo = document(paths, (0, 1, 2))
        solo["tracks"][2].update(solo=True, gain=0.25)
        solo["clips"][2]["gain"] = 0.5
        cases.append(("track-solo-clip-gain", solo, -3276.75/32768, FRAMES))
        seek = document(paths, (0, 1, 2))
        seek["program"]["frame"] = 3
        cases.append(("playhead-seek", seek, 26214/32768, 14400))
        overload = document(paths, (0, 1, 2))
        overload["clips"][2]["enabled"] = False
        cases.append(("positive-overload", overload, 1, FRAMES))
        negative = document(paths, (0, 1, 2))
        negative["clips"][0].update(source=9)
        negative["clips"][1].update(source=9)
        negative["clips"][2]["enabled"] = False
        cases.append(("negative-overload", negative, -1, FRAMES))
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker),
                   GENESIS_SCRATCH=str(root / "state"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        env.pop("GENESIS_SESSION_REPORT", None)
        for name, doc, expected, count in cases:
            project = root / f"{name}.air"
            project.write_text(json.dumps(doc), encoding="utf-8")
            original = sha(project)
            audition = root / f"{name}.wav"
            run([binary, "audio", audition, project], env)
            with wave.open(str(audition), "rb") as audio:
                assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                        audio.getnframes()) == (2, 2, SR, count), name
                samples = array("h", audio.readframes(count))
            target = int(math.copysign(math.floor(abs(expected)*32767+0.5), expected))
            pcm_error = max(abs(value-target) for value in samples)
            assert pcm_error <= 1, (name, target, min(samples), max(samples), pcm_error)
            movie = root / f"{name}.mkv"
            run([binary, "export", movie, project], env)
            decoded = run([tool(worker, "ffmpeg"), "-nostdin", "-v", "error", "-i",
                           movie, "-vn", "-f", "f32le", "pipe:1"])
            floats = array("f")
            floats.frombytes(decoded.stdout)
            assert all(math.isfinite(value) for value in floats), (name, "non-finite export audio")
            # Export uses the full sequence independently of the audition playhead.
            assert len(floats) == FRAMES*2, (name, len(floats))
            maximum = max(abs(value-expected) for value in floats)
            assert maximum <= 1/8388608, (name, maximum, min(floats), max(floats))
            assert sha(project) == original, "render changed the saved project"
            results.append(dict(name=name, audition_frames=count,
                                audition_max_error_pcm=pcm_error,
                                export_frames=FRAMES, export_max_error=maximum,
                                project_unchanged=True))
        assert source_hashes == [sha(path) for path in paths]
    report = dict(schema="genesis.audio_mix_project.v1", passed=True,
                  app_sha256=sha(binary), worker_sha256=sha(worker),
                  cases=results, sources_unchanged=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Saved-project overlap: {len(results)} audition/export cases passed; "
          "six storage orders, gain, mute, solo, seek and signed overload; "
          "source and project bytes preserved", flush=True)


if __name__ == "__main__":
    main()
