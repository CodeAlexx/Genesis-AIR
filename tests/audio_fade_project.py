"""Saved-project fade lengths must shape audition and encoded master audio.

Linear/hold curves below are authored independently of the planner and worker.
Constant signed PCM makes lossless samples exact; a separate sine measures AAC
amplitude on each side of a held fade-length change.
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

from audio_mix_project import document
from media_runtime import tool

SR = 48000
FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def sample(frame, fps):
    return math.floor(frame * SR / fps + .5)


def run(argv, env=None):
    done = subprocess.run(list(map(str, argv)), env=env, capture_output=True,
                          timeout=90, creationflags=FLAGS)
    assert done.returncode == 0, (done.returncode, done.stdout[-2000:], done.stderr[-2000:])
    return done.stdout


def curve(points, absolute, placement, fps, fallback):
    if not points:
        return fallback
    if absolute <= sample(placement + points[0][0], fps):
        return points[0][1]
    for (a, av, mode), (b, bv, _) in zip(points, points[1:]):
        end = sample(placement + b, fps)
        if absolute < end:
            if mode == 4:
                return av
            assert mode == 2, "Independent project oracle only authors linear/hold modes"
            begin = sample(placement + a, fps)
            return av + (bv-av) * (absolute-begin) / (end-begin)
    return points[-1][1]


def authored(source, fps=30, placement=0, start=0, curves=None):
    doc = document([source], (0,))
    doc["sequences"][0].update(fps=fps, name="Fade project")
    doc["sources"][0].update(frames=math.floor(6*fps), fps=fps)
    doc["clips"][0].update(length=90, start=placement, source_in=7,
                             gain=.8, fade_in=0, fade_out=0)
    doc["tracks"][0]["gain"] = .75
    doc["program"]["frame"] = start
    doc["names"] = ["fade_in", "fade_out", "gain"]
    curves = curves or {}
    doc["keys"] = [dict(clip=20, owner=2, param=doc["names"].index(name)+1,
                        frame=frame, value=value, interp=mode)
                   for name, points in curves.items() for frame, value, mode in points]
    return doc


def expected(doc, begin):
    fps = doc["sequences"][0]["fps"]
    clip = doc["clips"][0]
    placement, length = clip["start"], clip["length"]
    first, finish = sample(begin, fps), sample(placement+length, fps)
    clip_origin = sample(placement, fps)
    curves = {name: [(key["frame"], key["value"], key["interp"])
                     for key in doc["keys"] if doc["names"][key["param"]-1] == name]
              for name in doc["names"]}
    result = array("f")
    for absolute in range(first, finish):
        if absolute < clip_origin:
            result.extend((0., 0.))
            continue
        local = (absolute-clip_origin)/SR
        incoming = max(0., curve(curves["fade_in"], absolute, placement, fps, clip["fade_in"]))/fps
        outgoing = max(0., curve(curves["fade_out"], absolute, placement, fps, clip["fade_out"]))/fps
        envelope = min(1., max(0., local/incoming)) if incoming > 0 else 1.
        if outgoing > 0:
            envelope *= min(1., max(0., (length/fps-local)/outgoing))
        if curves["gain"]:
            gain = f32(f32(doc["tracks"][0]["gain"]) * f32(max(0., curve(curves["gain"], absolute, placement, fps, clip["gain"]))))
        else:
            gain = f32(doc["tracks"][0]["gain"] * clip["gain"])
        gain = f32(gain * f32(envelope))
        result.extend((f32(12000/32768 * gain), f32(-8000/32768 * gain)))
    return result


def decode(worker, movie):
    values = array("f")
    values.frombytes(run([tool(worker, "ffmpeg"), "-nostdin", "-v", "error", "-i",
                         movie, "-vn", "-f", "f32le", "pipe:1"]))
    assert values and all(math.isfinite(value) for value in values), "Nonfinite/empty encoded audio"
    return values


def pcm16(path):
    with wave.open(str(path), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (2, 2, SR)
        values = array("h", audio.readframes(audio.getnframes()))
    return values


def amplitude(values, begin, end, frequency=440):
    start, finish = int(begin*SR), int(end*SR)
    assert finish*2 <= len(values)
    re = sum(values[n*2]*math.cos(2*math.pi*frequency*n/SR) for n in range(start, finish))
    im = sum(values[n*2]*math.sin(2*math.pi*frequency*n/SR) for n in range(start, finish))
    return 2*math.hypot(re, im)/(finish-start)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    results = []
    with tempfile.TemporaryDirectory(prefix="genesis-fade-project-") as temporary:
        root = Path(temporary)
        source = root / "fade source 日本語.wav"
        with wave.open(str(source), "wb") as output:
            output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
            output.writeframes(array("h", [12000, -8000] * (6*SR)).tobytes())
        source_hash = sha(source)
        incoming = [(0, 90, 2), (30, 45, 2), (89, 120, 2)]
        outgoing = [(0, 120, 2), (45, 45, 2), (89, 90, 2)]
        cases = [("linear-in", authored(source, curves={"fade_in": incoming})),
                 ("linear-out", authored(source, curves={"fade_out": outgoing})),
                 ("overlap-product", authored(source, curves={"fade_in": incoming, "fade_out": outgoing})),
                 ("gain-times-fades", authored(source, curves={"fade_in": incoming, "fade_out": outgoing,
                       "gain": [(0, .2, 2), (30, 1., 2), (89, .4, 2)]})),
                 ("signed-hold-context", authored(source, curves={"fade_in": [(-20, 90, 4), (30, -5, 4), (60, 75, 4), (110, 30, 4)],
                       "fade_out": [(0, -10, 4), (45, 90, 4), (89, 30, 4)]})),
                 ("fractional-placement-seek", authored(source, 60000/1001, 11, 20,
                       {"fade_in": incoming, "fade_out": outgoing})),
                 ("fractional-future-clip-seek", authored(source, 60000/1001, 3, 1,
                       {"fade_in": incoming, "fade_out": outgoing}))]
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "state"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        env.pop("GENESIS_SESSION_REPORT", None)
        for name, doc in cases:
            project = root / f"{name}.air"
            project.write_text(json.dumps(doc), encoding="utf-8")
            original = sha(project)
            audition = root / f"{name}.wav"
            run([binary, "audio", audition, project], env)
            target = expected(doc, doc["program"]["frame"])
            actual = pcm16(audition)
            fps = doc["sequences"][0]["fps"]
            finish = doc["clips"][0]["start"]+doc["clips"][0]["length"]
            wav_frames = math.ceil((finish-doc["program"]["frame"])/fps*SR)
            assert len(actual) == wav_frames*2 and 0 <= len(actual)-len(target) <= 2, (name, "audition length", len(actual), len(target))
            # The legacy WAVE seconds command allocates ceil(duration*rate).
            # Absolute rounded endpoint ranges can leave one trailing silent
            # frame; every authored sample must still match its exact clock.
            assert not any(actual[len(target):]), (name, "non-silent WAV padding")
            maximum_pcm = max(abs(a-b*32767) for a, b in zip(actual[:len(target)], target))
            assert maximum_pcm <= 1, (name, "audition sample error", maximum_pcm)
            movie = root / f"{name}.mkv"
            run([binary, "export", movie, project], env)
            master = decode(worker, movie)
            full_target = expected(doc, 0)
            # Exact-count export ends at the independent authored audio endpoint.
            # Legacy audition WAVE allocation above retains its separate ceil rule.
            assert len(master) == len(full_target), (name, "master length", len(master), len(full_target))
            maximum_master = max(abs(a-b) for a, b in zip(master, full_target))
            assert maximum_master <= 1/8388608, (name, "master sample error", maximum_master)
            assert sha(project) == original, "Rendering changed authored project bytes"
            results.append(dict(name=name, audition_frames=len(actual)//2, audition_max_error_pcm=maximum_pcm,
                                audition_silent_padding_frames=(len(actual)-len(target))//2,
                                master_frames=len(master)//2, master_silent_padding_frames=(len(master)-len(full_target))//2,
                                master_max_error=maximum_master, project_unchanged=True))
        assert sha(source) == source_hash, "Rendering changed authored source bytes"
        tone = root / "AAC tone.wav"
        samples = array("h")
        for n in range(6*SR):
            value = round(.3*32768*math.sin(2*math.pi*440*n/SR))
            samples.extend((value, value))
        with wave.open(str(tone), "wb") as output:
            output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
            output.writeframes(samples.tobytes())
        tone_hash = sha(tone)
        base = authored(tone)
        base["clips"][0].update(length=120, source_in=0, gain=1)
        base["tracks"][0]["gain"] = 1
        keyed = copy.deepcopy(base)
        keyed["keys"] = [dict(clip=20, owner=2, param=1, frame=frame, value=value, interp=4)
                         for frame, value in ((0, 120), (60, 0), (119, 0))]
        encoded = []
        for name, doc in (("aac-base", base), ("aac-fade", keyed)):
            project = root / f"{name}.air"
            project.write_text(json.dumps(doc), encoding="utf-8")
            original = sha(project)
            movie = root / f"{name}.mp4"
            run([binary, "export", movie, project], env)
            values = decode(worker, movie)
            assert len(values) >= 4*SR*2, (name, "AAC lost program audio samples")
            assert len(values) <= (4*SR+1024)*2, (name, "AAC exceeded one codec padding frame")
            assert sha(project) == original
            encoded.append(values)
        ratios = []
        for begin, end, target in ((.5, 1., .1875), (1., 1.5, .3125), (2.5, 3., 1.)):
            ratio = amplitude(encoded[1], begin, end)/amplitude(encoded[0], begin, end)
            assert math.isfinite(ratio) and abs(ratio-target) < .02, ("AAC keyed fade amplitude", begin, ratio, target)
            ratios.append(dict(begin_seconds=begin, end_seconds=end, expected=target, actual=ratio))
        assert sha(tone) == tone_hash
    report = dict(schema="genesis.audio_fade_project.v1", passed=True, app_sha256=sha(binary),
                  worker_sha256=sha(worker), cases=results, aac_amplitude_windows=ratios, sources_unchanged=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Saved-project fades: {len(results)} exact audition/lossless-master cases and three AAC amplitude windows passed; source/project bytes preserved", flush=True)


if __name__ == "__main__":
    main()
