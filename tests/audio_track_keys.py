"""Track gain automation (TRKGAIN): sample-exact PCM against an independent SDK-curve oracle.

The AIR client (tests/audio_track_plan.ai) plans and renders 44 variants twice, through the
flat path (whole range, uneven chunks, fresh seek) and through the prepared endpoint path
(whole program, uneven pulls, fresh seek), next to an unkeyed baseline of the same layout.
For every output sample the expected value is
    baseline * f32(f32(clip_side) * f32(track_curve)) * fade_ramps
where clip_side and track_curve come from std.curve evaluated over the COMPLETE key list
(never the windowed list the worker receives), so a wrong window, a wrong neighbour for the
Catmull modes, a static value leaking through, or a chunk/seek/endpoint disagreement fails.
Static track gain (0.5) is authored under every keyed curve and must be ignored.

A direct worker protocol section then pins the TRKGAIN wire grammar: exact PCM, token
order independence, product with clip gain keys, and coded refusals that leave the retained
decoder untouched.
"""
import argparse
from array import array
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from audio_stream import pcm, wire

RATE = 48000
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
TOLERANCE = 2


def sample(frame, fps):
    return math.floor(frame * RATE / fps + .5)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def collect(paths):
    result = array("h")
    for path in paths:
        result.extend(pcm(path))
    return result


def ordered(output, prefix, kind):
    return sorted(output.glob(f"{prefix}{kind}[0-9]*.wav"),
                  key=lambda path: int(path.stem.rsplit(kind, 1)[1]))


def ramp(local, duration, fade_in, fade_out, fps):
    incoming, outgoing = max(0.0, fade_in) / fps, max(0.0, fade_out) / fps
    a = min(1.0, max(0.0, local / incoming)) if incoming > 0 else 1.0
    b = min(1.0, max(0.0, (duration - local) / outgoing)) if outgoing > 0 else 1.0
    return a * b


def compare(actual, baseline, oracle, row, label, first_sample=0):
    """actual/baseline are interleaved int16; oracle is [(clip_side, track)] from sample 0."""
    fps = float(row["fps"])
    length = int(row["clip_length"])
    placement = int(row["clip_start"])
    fade_in, fade_out = int(row["fade_in"]), int(row["fade_out"])
    assert len(actual) == len(baseline), (label, len(actual), len(baseline))
    frames = len(actual) // 2
    assert first_sample + frames <= len(oracle), (label, first_sample, frames, len(oracle))
    clip_origin = sample(placement, fps)
    largest, total, differing = 0.0, 0.0, 0.0
    for index in range(frames):
        pre, track = oracle[first_sample + index]
        gain = f32(f32(pre) * f32(track))
        if fade_in or fade_out:
            local = (first_sample + index - clip_origin) / RATE
            gain = f32(gain * f32(ramp(local, length / fps, fade_in, fade_out, fps)))
        for channel in (0, 1):
            base = baseline[index * 2 + channel]
            error = abs(actual[index * 2 + channel] - base * gain)
            largest, total = max(largest, error), total + error
            differing = max(differing, abs(base * gain - base))
    assert largest <= TOLERANCE, (label, largest, "decoded PCM times independent f32 gain chain")
    return dict(sample_frames=frames, maximum_pcm_difference=largest,
                mean_pcm_difference=total / max(1, len(actual)), maximum_audible_effect=differing)


def trimmed(values, frames, label):
    """WAV allocation rounds a range's seconds up; the surplus frame must be silence."""
    assert frames * 2 <= len(values) <= frames * 2 + 2, (label, len(values), frames)
    assert not any(values[frames * 2:]), (label, "rounded surplus frame must be silence")
    return values[:frames * 2]


def variant(output, row, flat_root, endpoint_root):
    v = int(row["variant"])
    fps, end, seek = float(row["fps"]), int(row["end"]), int(row["seek"])
    prefix = f"tg-{v}"
    total = sample(end, fps)
    raw = (flat_root / f"{prefix}-oracle.f64").read_bytes()
    assert len(raw) == total * 16, (v, len(raw), total)
    oracle = list(struct.iter_unpack("<dd", raw))
    entry = dict(variant=v, mode=int(row["mode"]), fps=fps)

    base = trimmed(pcm(flat_root / f"{prefix}-base.wav"), total, (v, "flat baseline"))
    whole = trimmed(pcm(flat_root / f"{prefix}-whole.wav"), total, (v, "whole"))
    entry["flat_whole"] = compare(whole, base, oracle, row, (v, "flat whole"))
    chunks = collect(ordered(flat_root, prefix, "-chunk"))
    entry["flat_chunks"] = compare(chunks, base, oracle, row, (v, "flat uneven chunks"))
    seek_base = pcm(flat_root / f"{prefix}-seek-base.wav")
    seek_frames = total - sample(seek, fps)
    seek_base = trimmed(seek_base, seek_frames, (v, "seek baseline"))
    seeks = collect(ordered(flat_root, prefix, "-seek"))
    entry["flat_seek"] = compare(seeks, seek_base, oracle, row, (v, "flat fresh seek"), sample(seek, fps))
    assert entry["flat_whole"]["maximum_audible_effect"] > 500, (v, "automation had no audible effect")

    ep_base = pcm(endpoint_root / f"{prefix}-ep-base.wav")
    ep_whole = pcm(endpoint_root / f"{prefix}-ep-whole.wav")
    assert len(ep_base) == len(ep_whole) == total * 2, (v, "endpoint length", len(ep_base), len(ep_whole), total)
    entry["endpoint_whole"] = compare(ep_whole, ep_base, oracle, row, (v, "endpoint whole"))
    pieces = collect(sorted(endpoint_root.glob(f"{prefix}-ep-chunk[0-9]*.wav"),
                            key=lambda path: int(path.stem.rsplit("-ep-chunk", 1)[1])))
    assert pieces == ep_whole, (v, "endpoint uneven pulls differ from the whole pull")
    ep_seek = pcm(endpoint_root / f"{prefix}-ep-seek.wav")
    assert ep_seek == ep_whole[sample(seek, fps) * 2:], (v, "endpoint fresh seek differs from the whole pull")
    entry["endpoint_equals_chunks_and_seek"] = True
    # Flat and endpoint planners feed one worker evaluator: they agree to PCM rounding.
    spread = max(abs(a - b) for a, b in zip(ep_whole, whole))
    assert spread <= TOLERANCE + 1, (v, "flat and endpoint renders disagree", spread)
    entry["flat_vs_endpoint_maximum_pcm_difference"] = spread
    return entry


# ---------------------------------------------------------------------------
# Direct worker protocol

def protocol(worker, root):
    source = root / "constant stereo.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(array("h", [8192, -4096] * 2000).tobytes())
    count = 800
    line = lambda *tokens, ident=333: (
        f"AUDIOSTREAM {wire(source)} 0 {count / RATE:.17f} 0 1 0 0 1 0 - {ident} {2000 / RATE:.17f} {count} "
        + " ".join(tokens))
    good = "TRKGAIN:0:0,0,0.25,2/800,800,1,2"
    clip = "GAINKEYS:0:0,0,0.5,2"
    bad = [("TRKGAIN:0:0,0,-0.1,2", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:0,0,nan,2", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:0,0,3.5e38,2", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:0,0,1,38", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:0,0,1,2/0,1,2,2", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:0,0,1,2/800,-1,2,2", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:0,0,1", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:0:", "GA_AUDIO_TRACK_GAIN_KEYS"),
           ("TRKGAIN:-1:0,0,1,2", "GA_AUDIO_TRACK_GAIN_KEYS"),
           (good + " " + good, "GA_AUDIO_FADE_KEYS"),
           (clip + " TRKGAIN:5:0,0,1,2", "GA_AUDIO_FADE_KEYS"),
           ("TRKPAN:0:0,0,0.5,2", "GA_AUDIO_FADE_KEYS"),
           ("TRKGAIN:0:0,0,1,2 UNKNOWN:0", "GA_AUDIO_FADE_KEYS")]
    ok = root / "ok.wav"
    only = root / "only.wav"
    both = root / "both.wav"
    reverse = root / "reverse.wav"
    commands = [f"PLAYWAVE {wire(ok)} {count}"]
    commands += [line(token) for token, code in bad]
    commands += [line(good), f"WAVECLOSE {wire(ok)}",
                 f"PLAYWAVE {wire(only)} {count}", line(good, ident=334), f"WAVECLOSE {wire(only)}",
                 f"PLAYWAVE {wire(both)} {count}", line(clip, good, ident=335), f"WAVECLOSE {wire(both)}",
                 f"PLAYWAVE {wire(reverse)} {count}", line(good, clip, ident=336), f"WAVECLOSE {wire(reverse)}"]
    done = subprocess.run([str(worker), "--serve"], input="\n".join(commands) + "\n", capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=FLAGS)
    assert done.returncode == 0 and done.stdout.splitlines().count("ERR") == len(bad), (done.stdout, done.stderr)
    for code in ("GA_AUDIO_TRACK_GAIN_KEYS", "GA_AUDIO_FADE_KEYS"):
        wanted = sum(expected == code for token, expected in bad)
        assert done.stderr.count("[" + code + "]") == wanted, (code, wanted, done.stderr)
    recovered, alone = pcm(ok), pcm(only)
    assert recovered == alone and len(recovered) == count * 2, "refused requests changed the retained decoder"
    largest = 0.0
    for n in range(count):
        gain = 0.25 + (1 - 0.25) * n / 800
        for channel, value in enumerate((8192, -4096)):
            largest = max(largest, abs(recovered[n * 2 + channel] - value / 32768 * 32767 * gain))
    assert largest <= 1, largest
    product, swapped = pcm(both), pcm(reverse)
    assert product == swapped, "token order changed the render"
    product_error = 0.0
    # One clip key holds 0.5 for the whole span; the track curve ramps 0.25 -> 1 over 800 frames.
    for n in range(count):
        for channel, value in enumerate((8192, -4096)):
            expected = value / 32768 * 32767 * 0.5 * (0.25 + 0.75 * n / 800)
            product_error = max(product_error, abs(product[n * 2 + channel] - expected))
    assert product_error <= 1, product_error
    return dict(coded_refusals=len(bad), recovery_maximum_pcm_difference=largest,
                clip_times_track_maximum_pcm_difference=product_error, token_orders_equal=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    worker, client = args.worker.resolve(), args.client.resolve()
    report = dict(schema="genesis.audio_track_keys.v1", worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
                  client_sha256=hashlib.sha256(client.read_bytes()).hexdigest(), cases=[],
                  scope="sample processing and planning; no sound-device timing claim")
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-track-keys-") as temporary:
        root = Path(temporary)
        source = root / "authored 日本語 %20.wav"
        values = array("h", (value for n in range(12 * RATE) for value in
                             (int(6500 * math.sin(2 * math.pi * 431.3 * n / RATE) + 400),
                              int(-4200 * math.cos(2 * math.pi * 211.7 * n / RATE) - 300))))
        with wave.open(str(source), "wb") as audio:
            audio.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
            audio.writeframes(values.tobytes())
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        output = root / "out"
        done = subprocess.run([str(client), str(worker), str(source), str(output)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=900, creationflags=FLAGS)
        try:
            assert done.returncode == 0, (done.returncode, done.stdout[-3000:], done.stderr[-3000:])
            rows = list(csv.DictReader((output / "track-cases.tsv").open(encoding="utf-8", newline=""), delimiter="\t"))
            assert len(rows) == 44, len(rows)
            plan_report = json.loads((output / "audio-track-plan-tests.json").read_text(encoding="utf-8"))["payload"]
            assert plan_report["status"] == "pass", plan_report
            report["planning_checks"] = plan_report["checks"]
            for row in rows:
                entry = variant(output, row, output / "flat", output / "endpoint")
                report["cases"].append(entry)
                print(f"Track gain: variant {entry['variant']} (mode {entry['mode']}) flat+endpoint PCM passed", flush=True)
            assert original == hashlib.sha256(source.read_bytes()).hexdigest(), "source modified"
            report["protocol"] = protocol(worker, root)
            report.update(passed=True, case_count=len(rows),
                          sample_frames=sum(case["flat_whole"]["sample_frames"] + case["endpoint_whole"]["sample_frames"]
                                            for case in report["cases"]),
                          worst_pcm_difference=max(max(case[kind]["maximum_pcm_difference"] for kind in
                                                       ("flat_whole", "flat_chunks", "flat_seek", "endpoint_whole"))
                                                   for case in report["cases"]))
        except Exception as problem:
            report.update(passed=False, execution_error=str(problem), client_stdout=done.stdout[-4000:],
                          client_stderr=done.stderr[-4000:])
            args.report.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise
    args.report.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Track gain keys: {report['planning_checks']} planning checks, {report['case_count']} variants, "
          f"{report['sample_frames']} sample frames, worst PCM difference {report['worst_pcm_difference']}, "
          f"{report['protocol']['coded_refusals']} refusal/recovery cases passed")


if __name__ == "__main__":
    main()
