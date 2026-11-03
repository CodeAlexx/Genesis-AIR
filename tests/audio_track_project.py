"""Saved-project track gain automation: independently authored revision 5 projects.

Projects are JSON authored here, never by the editor; keys use only linear and hold curves
so the expected audio comes from an arithmetic oracle that shares no code with the planner or
worker. Each case runs the real `Genesis-AIR.exe audio` audition (16-bit WAV, <= 1 LSB) and
`Genesis-AIR.exe export` (float master, <= 2 ulp at unity) and checks that rendering leaves
the project and source bytes untouched. Cases cover overlapping clips on one automated
track (sum equals bus), two tracks with different curves, mute and solo precedence, embedded
audio on an automated VIDEO track, a mark-in start, and a fractional frame rate. A final
section runs tests/endpoint_park.ai (when --park-client is given) against the project.
"""
import argparse
from array import array
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from media_runtime import tool

SR = 48000
FLAGS = 0x08000000 if os.name == "nt" else 0
LINEAR, HOLD = 2, 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def sample(frame, fps):
    return math.floor(frame * SR / fps + .5)


def run(argv, env=None, timeout=120):
    done = subprocess.run(list(map(str, argv)), env=env, capture_output=True, timeout=timeout, creationflags=FLAGS)
    assert done.returncode == 0, (done.returncode, done.stdout[-2000:], done.stderr[-2000:])
    return done


def curve(points, absolute, fps):
    """points = [(timeline_frame, value, mode)] evaluated at an absolute sample."""
    if absolute <= sample(points[0][0], fps):
        return points[0][1]
    for (a, av, mode), (b, bv, _) in zip(points, points[1:]):
        end = sample(b, fps)
        if absolute < end:
            if mode == HOLD:
                return av
            begin = sample(a, fps)
            return av + (bv - av) * (absolute - begin) / (end - begin)
    return points[-1][1]


def constant(path, left, right, seconds=2):
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
        output.writeframes(array("h", [left, right] * (seconds * SR)).tobytes())


def authored(sources, tracks, clips, keys, fps=30, start=0):
    """sources: [(path, has_video)], tracks: [(id, kind, gain, muted, solo)],
    clips: [(id, source index, track, start, length)], keys: {track: [(frame, value, mode)]}."""
    names = [f"track.{track}.gain" for track in keys]
    doc = dict(schema="air.editor.project", revision=5, active=2, source_bounds=0, monitor_source=7, next_id=60,
               program=dict(playing=False, frame=start, mark_in=-1, mark_out=-1, rate=1, looping=False),
               monitor=dict(playing=False, frame=0, mark_in=-1, mark_out=-1, rate=1, looping=False),
               bins=[dict(id=1, name="Media", parent=0)],
               sequences=[dict(id=2, name="Track automation", fps=fps, width=16, height=16)],
               sources=[], tracks=[], clips=[], transitions=[], keys=[], markers=[], subtitles=[],
               filters=[], filter_params=[], filter_text_params=[], names=names)
    for n, (path, video) in enumerate(sources):
        doc["sources"].append(dict(id=7 + n, path=str(path), name=Path(path).name, bin=1, frames=math.floor(2 * fps), fps=fps,
                                   width=16 if video else 0, height=16 if video else 0, has_video=video, has_audio=True,
                                   audio_rate=SR, audio_channels=2, online=True))
    for order, (ident, kind, gain, muted, solo) in enumerate(tracks):
        doc["tracks"].append(dict(id=ident, owner=2, kind=kind, name=f"T{ident}", order=order, hidden=False, muted=muted,
                                  locked=False, solo=solo, gain=gain, pan=0, height=44))
    for ident, source, track, begin, length in clips:
        doc["clips"].append(dict(id=ident, owner=2, source=7 + source, nested=0, source_in=0, length=length, start=begin,
                                 track=track, group=0, enabled=True, selected=False, fade_in=0, fade_out=0, gain=1, pan=0,
                                 speed=1, reverse=False))
    for track, points in keys.items():
        for frame, value, mode in points:
            doc["keys"].append(dict(clip=0, owner=2, param=names.index(f"track.{track}.gain") + 1,
                                    frame=frame, value=value, interp=mode))
    return doc


def expected(doc, constants, begin_frame=0):
    """Float master oracle: per clip x * f32(curve), accumulated in f32, from sample(begin)."""
    fps = doc["sequences"][0]["fps"]
    end = max(clip["start"] + clip["length"] for clip in doc["clips"])
    first, finish = sample(begin_frame, fps), sample(end, fps)
    solo = any(track["solo"] for track in doc["tracks"])
    audible = {track["id"]: not track["muted"] and (not solo or track["solo"]) for track in doc["tracks"]}
    curves = {}
    for key in doc["keys"]:
        name = doc["names"][key["param"] - 1]
        curves.setdefault(int(name.split(".")[1]), []).append((key["frame"], key["value"], key["interp"]))
    result = array("f")
    for absolute in range(first, finish):
        left = right = 0.0
        for clip in doc["clips"]:
            if not audible[clip["track"]]:
                continue
            if not sample(clip["start"], fps) <= absolute < sample(clip["start"] + clip["length"], fps):
                continue
            gain = f32(f32(curve(curves[clip["track"]], absolute, fps)) if clip["track"] in curves
                       else f32(next(t["gain"] for t in doc["tracks"] if t["id"] == clip["track"])))
            value = constants[clip["source"] - 7]
            left = f32(left + f32(f32(value[0] / 32768) * gain))
            right = f32(right + f32(f32(value[1] / 32768) * gain))
        result.extend((left, right))
    return result


def pcm16(path):
    with wave.open(str(path), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (2, 2, SR)
        return array("h", audio.readframes(audio.getnframes()))


def decode(worker, movie):
    done = run([tool(worker, "ffmpeg"), "-nostdin", "-v", "error", "-i", movie, "-vn", "-f", "f32le", "pipe:1"])
    values = array("f")
    values.frombytes(done.stdout)
    assert values and all(math.isfinite(value) for value in values), "empty/nonfinite master"
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--park-client", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    results = []
    with tempfile.TemporaryDirectory(prefix="genesis-track-project-") as temporary:
        root = Path(temporary)
        sources = [root / f"constant {n} 日本語.wav" for n in range(3)]
        constants = [(12000, -8000), (6000, 3000), (-9000, 7000)]
        for path, (left, right) in zip(sources, constants):
            constant(path, left, right)
        movie_source = root / "embedded video 日本語.mkv"
        run([tool(worker, "ffmpeg"), "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=16x16:r=30:d=2",
             "-i", str(sources[2]), "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-c:a", "pcm_s16le", "-t", "2", movie_source])
        source_hashes = [sha(path) for path in sources] + [sha(movie_source)]
        plain = [(path, False) for path in sources]
        saw = [(0, .2, LINEAR), (20, 1.0, LINEAR), (40, .4, HOLD), (55, .9, LINEAR), (80, .1, LINEAR)]
        saw_b = [(0, 1.0, LINEAR), (30, .25, LINEAR), (59, .75, LINEAR)]
        overlap_clips = [(20, 0, 3, 0, 30), (21, 1, 3, 10, 30)]
        cases = [
            ("overlap-sum", authored(plain, [(3, 1, .5, False, False)], overlap_clips, {3: saw}), 0),
            ("two-tracks", authored(plain, [(3, 1, .5, False, False), (4, 1, 1, False, False)],
                                    [(20, 0, 3, 0, 30), (21, 1, 4, 0, 30)], {3: saw, 4: saw_b}), 0),
            ("muted-keyed-track", authored(plain, [(3, 1, .5, True, False), (4, 1, 1, False, False)],
                                           [(20, 0, 3, 0, 30), (21, 1, 4, 0, 30)], {3: saw, 4: saw_b}), 0),
            ("solo-excludes-keyed-track", authored(plain, [(3, 1, .5, False, False), (4, 1, 1, False, True)],
                                                   [(20, 0, 3, 0, 30), (21, 1, 4, 0, 30)], {3: saw, 4: saw_b}), 0),
            ("mark-in-start", authored(plain, [(3, 1, .5, False, False)], overlap_clips, {3: saw}, start=12), 12),
            ("fractional-rate", authored(plain, [(3, 1, .5, False, False)], [(20, 0, 3, 3, 60), (21, 1, 3, 31, 30)],
                                         {3: [(0, .3, LINEAR), (17, 1.0, LINEAR), (44, .2, HOLD), (61, .8, LINEAR),
                                              (95, .4, LINEAR)]}, fps=60000 / 1001, start=1), 1),
        ]
        video = authored(plain + [(movie_source, True)], [(3, 0, .5, False, False)], [(20, 3, 3, 0, 30)], {3: saw})
        cases.append(("embedded-audio-on-video-track", video, 0))
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "state"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        env.pop("GENESIS_SESSION_REPORT", None)
        all_constants = constants + [constants[2]]
        for name, doc, begin in cases:
            project = root / f"{name}.air"
            project.write_text(json.dumps(doc), encoding="utf-8")
            original = sha(project)
            fps = doc["sequences"][0]["fps"]
            end = max(clip["start"] + clip["length"] for clip in doc["clips"])
            target = expected(doc, all_constants, begin)
            audition = root / f"{name}.wav"
            run([binary, "audio", audition, project], env)
            actual = pcm16(audition)
            wav_frames = math.ceil((end - begin) / fps * SR)
            assert len(actual) == wav_frames * 2 and 0 <= len(actual) - len(target) <= 2, (name, "audition length", len(actual), len(target))
            # The legacy WAVE allocation rounds seconds up, so a fractional rate can leave one
            # trailing frame that holds the final authored sample (also true without automation).
            pad = actual[len(target):]
            assert all(abs(pad[n] - actual[len(target) - 2 + n % 2]) <= 1 for n in range(len(pad))), (name, "WAV padding is not the final authored frame")
            # The legacy WAVE audition places a clip from seconds (round(offset * rate)), which at a
            # fractional rate can sit one sample off the rounded absolute boundary the planner uses
            # (true without automation too). Only samples within one frame of a clip edge are exempt.
            edges = set()
            for clip in doc["clips"]:
                for edge in (clip["start"], clip["start"] + clip["length"]):
                    centre = sample(edge, fps) - sample(begin, fps)
                    edges.update(range(centre - 1, centre + 2))
            maximum_pcm = max(abs(a - math.copysign(math.floor(abs(b) * 32767 + .5), b))
                              for n, (a, b) in enumerate(zip(actual, target)) if n // 2 not in edges)
            assert maximum_pcm <= 1, (name, "audition sample error", maximum_pcm)
            assert max(abs(value) for value in target) > .05, (name, "oracle is silent")
            master = project.with_suffix(".mkv")
            run([binary, "export", master, project], env, 240)
            decoded = decode(worker, master)
            full = expected(doc, all_constants, 0)
            assert len(decoded) == len(full), (name, "master length", len(decoded), len(full))
            maximum_master = max(abs(a - b) for a, b in zip(decoded, full))
            assert maximum_master <= 2 / 8388608, (name, "master sample error", maximum_master)
            assert sha(project) == original, "rendering changed the saved project"
            results.append(dict(name=name, audition_frames=len(actual) // 2, audition_max_error_pcm=maximum_pcm,
                                master_frames=len(decoded) // 2, master_max_error=maximum_master, project_unchanged=True))
            print(f"Track project: {name} audition + lossless master passed", flush=True)
        assert source_hashes == [sha(path) for path in sources] + [sha(movie_source)], "rendering changed sources"
        park = None
        if args.park_client:
            # The park fixture is the same two-clip layout WITHOUT automation: its static track
            # gain is what the original edit step halves, and the new step adds track keys itself.
            static = authored(plain, [(3, 1, .5, False, False)], overlap_clips, {})
            static["revision"] = 2
            park_project = root / "park-static.air"
            park_project.write_text(json.dumps(static), encoding="utf-8")
            workdir = root / "park"
            done = run([args.park_client.resolve(), worker, park_project, workdir], env, 600)
            park = done.stdout.decode("utf-8", "replace").strip()
            assert "track gain window" in park, park
    report = dict(schema="genesis.audio_track_project.v1", passed=True, app_sha256=sha(binary), worker_sha256=sha(worker),
                  cases=results, endpoint_park=park, sources_unchanged=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Track gain projects: {len(results)} revision 5 audition/export cases passed"
          + ("; endpoint park window edits passed" if park else "") + "; project and source bytes preserved", flush=True)


if __name__ == "__main__":
    main()
