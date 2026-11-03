"""Track pan automation (TRKPAN): sample-exact PCM against an independent SDK-curve oracle.

The AIR client (tests/audio_track_pan.ai) plans and renders 43 variants twice, through the flat
path (whole range, uneven chunks, fresh seek) and through the prepared endpoint path (whole
program, uneven pulls, fresh seek), next to a baseline of the same layout without the track pan
keys. For every output sample the expected value is
    baseline * balance(pre) * balance(track)
with balance(b): left *= 1 - max(b, 0), right *= 1 + min(b, 0) (the clip pan law), where `pre`
(a child sequence's own track pan) and `track` come from std.curve
evaluated over the COMPLETE key list (never the windowed list the worker receives), clamped to
[-1, 1]. A wrong window, a wrong Catmull neighbour, the static track pan leaking through under
the keys, or a chunk/seek/endpoint disagreement fails.

Variant 38 renders a keyed constant pan next to a static twin of the same pan on a filter-free
chain: the two must agree (memoryless equivalence).

A direct worker protocol section pins the TRKPAN wire grammar: exact PCM, token order
independence, composition with clip pan keys and track gain keys, and coded refusals that leave
the retained decoder untouched.
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


def balance(value):
    """(left, right) factors of the shared pan law."""
    return 1.0 - max(value, 0.0), 1.0 + min(value, 0.0)


def collect(paths):
    result = array("h")
    for path in paths:
        result.extend(pcm(path))
    return result


def ordered(output, prefix, kind):
    return sorted(output.glob(f"{prefix}{kind}[0-9]*.wav"),
                  key=lambda path: int(path.stem.rsplit(kind, 1)[1]))


def trimmed(values, frames, label):
    """WAV allocation rounds a range's seconds up; the surplus frame must be silence."""
    assert frames * 2 <= len(values) <= frames * 2 + 2, (label, len(values), frames)
    assert not any(values[frames * 2:]), (label, "rounded surplus frame must be silence")
    return values[:frames * 2]


def compare(actual, baseline, oracle, label, first_sample=0):
    """actual/baseline are interleaved int16; oracle is [(pre, track)] pan values from sample 0."""
    assert len(actual) == len(baseline), (label, len(actual), len(baseline))
    frames = len(actual) // 2
    assert first_sample + frames <= len(oracle), (label, first_sample, frames, len(oracle))
    largest, total, differing = 0.0, 0.0, 0.0
    for index in range(frames):
        pre, track = oracle[first_sample + index]
        factors = [a * b for a, b in zip(balance(pre), balance(track))]
        for channel in (0, 1):
            base = baseline[index * 2 + channel]
            expected = base * factors[channel]
            error = abs(actual[index * 2 + channel] - expected)
            largest, total = max(largest, error), total + error
            differing = max(differing, abs(expected - base))
    assert largest <= TOLERANCE, (label, largest, "decoded PCM times independent balance chain")
    return dict(sample_frames=frames, maximum_pcm_difference=largest,
                mean_pcm_difference=total / max(1, len(actual)), maximum_audible_effect=differing)


def variant(row, flat_root, endpoint_root):
    v = int(row["variant"])
    fps, end, seek = float(row["fps"]), int(row["end"]), int(row["seek"])
    prefix = f"tp-{v}"
    total = sample(end, fps)
    raw = (flat_root / f"{prefix}-oracle.f64").read_bytes()
    assert len(raw) == total * 16, (v, len(raw), total)
    oracle = list(struct.iter_unpack("<dd", raw))
    entry = dict(variant=v, mode=int(row["mode"]), fps=fps)

    base = trimmed(pcm(flat_root / f"{prefix}-base.wav"), total, (v, "flat baseline"))
    whole = trimmed(pcm(flat_root / f"{prefix}-whole.wav"), total, (v, "whole"))
    entry["flat_whole"] = compare(whole, base, oracle, (v, "flat whole"))
    chunks = collect(ordered(flat_root, prefix, "-chunk"))
    entry["flat_chunks"] = compare(chunks, base, oracle, (v, "flat uneven chunks"))
    seek_base = trimmed(pcm(flat_root / f"{prefix}-seek-base.wav"), total - sample(seek, fps), (v, "seek baseline"))
    seeks = collect(ordered(flat_root, prefix, "-seek"))
    entry["flat_seek"] = compare(seeks, seek_base, oracle, (v, "flat fresh seek"), sample(seek, fps))
    assert entry["flat_whole"]["maximum_audible_effect"] > 500, (v, "automation had no audible effect")

    ep_base = pcm(endpoint_root / f"{prefix}-ep-base.wav")
    ep_whole = pcm(endpoint_root / f"{prefix}-ep-whole.wav")
    assert len(ep_base) == len(ep_whole) == total * 2, (v, "endpoint length", len(ep_base), len(ep_whole), total)
    entry["endpoint_whole"] = compare(ep_whole, ep_base, oracle, (v, "endpoint whole"))
    pieces = collect(sorted(endpoint_root.glob(f"{prefix}-ep-chunk[0-9]*.wav"),
                            key=lambda path: int(path.stem.rsplit("-ep-chunk", 1)[1])))
    assert pieces == ep_whole, (v, "endpoint uneven pulls differ from the whole pull")
    ep_seek = pcm(endpoint_root / f"{prefix}-ep-seek.wav")
    assert ep_seek == ep_whole[sample(seek, fps) * 2:], (v, "endpoint fresh seek differs from the whole pull")
    entry["endpoint_equals_chunks_and_seek"] = True
    spread = max(abs(a - b) for a, b in zip(ep_whole, whole))
    assert spread <= TOLERANCE + 1, (v, "flat and endpoint renders disagree", spread)
    entry["flat_vs_endpoint_maximum_pcm_difference"] = spread
    if v == 38:
        static = trimmed(pcm(flat_root / f"{prefix}-static.wav"), total, (v, "static twin"))
        difference = max(abs(a - b) for a, b in zip(static, whole))
        assert difference <= TOLERANCE, (v, "keyed constant pan differs from the static track pan", difference)
        entry["static_twin_maximum_pcm_difference"] = difference
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
    good = "TRKPAN:0:0,0,-0.5,2/800,800,0.5,2"
    clip = "PANKEYS:0:0,0,0.5,2"
    gain = "TRKGAIN:0:0,0,0.5,2"
    code = "GA_AUDIO_TRACK_PAN_KEYS"
    bad = [("TRKPAN:0:0,0,1.5,2", code), ("TRKPAN:0:0,0,-1.0000001,2", code), ("TRKPAN:0:0,0,nan,2", code),
           ("TRKPAN:0:0,0,0.5,38", code), ("TRKPAN:0:0,0,0.5,2/0,1,0.2,2", code),
           ("TRKPAN:0:0,0,0.5,2/800,-1,0.2,2", code), ("TRKPAN:0:0,0,0.5", code), ("TRKPAN:0:", code),
           ("TRKPAN:-1:0,0,0.5,2", code),
           (good + " " + good, "GA_AUDIO_FADE_KEYS"),
           (clip + " TRKPAN:5:0,0,0.5,2", "GA_AUDIO_FADE_KEYS"),
           (gain + " TRKPAN:5:0,0,0.5,2", "GA_AUDIO_FADE_KEYS"),
           ("TRKPAN:0:0,0,0.5,2 UNKNOWN:0", "GA_AUDIO_FADE_KEYS")]
    names = {key: root / f"{key}.wav" for key in ("ok", "only", "clip", "reverse", "gain", "edge")}
    commands = [f"PLAYWAVE {wire(names['ok'])} {count}"]
    commands += [line(token) for token, _ in bad]
    commands += [line(good), f"WAVECLOSE {wire(names['ok'])}",
                 f"PLAYWAVE {wire(names['only'])} {count}", line(good, ident=334), f"WAVECLOSE {wire(names['only'])}",
                 f"PLAYWAVE {wire(names['clip'])} {count}", line(clip, good, ident=335), f"WAVECLOSE {wire(names['clip'])}",
                 f"PLAYWAVE {wire(names['reverse'])} {count}", line(good, clip, ident=336), f"WAVECLOSE {wire(names['reverse'])}",
                 f"PLAYWAVE {wire(names['gain'])} {count}", line(gain, good, ident=337), f"WAVECLOSE {wire(names['gain'])}",
                 f"PLAYWAVE {wire(names['edge'])} {count}", line("TRKPAN:0:0,0,1,4", ident=338), f"WAVECLOSE {wire(names['edge'])}"]
    done = subprocess.run([str(worker), "--serve"], input="\n".join(commands) + "\n", capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=FLAGS)
    assert done.returncode == 0 and done.stdout.splitlines().count("ERR") == len(bad), (done.stdout, done.stderr)
    for expected_code in (code, "GA_AUDIO_FADE_KEYS"):
        wanted = sum(expected == expected_code for _, expected in bad)
        assert done.stderr.count("[" + expected_code + "]") == wanted, (expected_code, wanted, done.stderr)
    recovered, alone = pcm(names["ok"]), pcm(names["only"])
    assert recovered == alone and len(recovered) == count * 2, "refused requests changed the retained decoder"
    source_pcm = (8192, -4096)

    def check(values, curve_value, extra=(1.0, 1.0), label=""):
        largest = 0.0
        for n in range(count):
            left, right = balance(curve_value(n))
            for channel, (factor, value) in enumerate(zip((left * extra[0], right * extra[1]), source_pcm)):
                largest = max(largest, abs(values[n * 2 + channel] - value / 32768 * 32767 * factor))
        assert largest <= 1, (label, largest)
        return largest

    ramp = lambda n: -0.5 + (0.5 + 0.5) * n / 800
    only_error = check(recovered, ramp, label="track pan ramp")
    clip_after = pcm(names["clip"])
    assert clip_after == pcm(names["reverse"]), "token order changed the render"
    # Clip pan 0.5 then track pan: left *= 0.5 (clip) * (1 - max(b,0)), right *= (1 + min(b,0)).
    product_error = check(clip_after, ramp, extra=balance(0.5), label="clip pan then track pan")
    gain_values = pcm(names["gain"])
    gain_error = check(gain_values, ramp, extra=(0.5, 0.5), label="track gain with track pan")
    edge_error = check(pcm(names["edge"]), lambda n: 1.0, label="full right pan")
    return dict(coded_refusals=len(bad), recovery_maximum_pcm_difference=only_error,
                clip_then_track_maximum_pcm_difference=product_error,
                track_gain_and_pan_maximum_pcm_difference=gain_error,
                full_pan_maximum_pcm_difference=edge_error, token_orders_equal=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    worker, client = args.worker.resolve(), args.client.resolve()
    report = dict(schema="genesis.audio_track_pan.v1", worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
                  client_sha256=hashlib.sha256(client.read_bytes()).hexdigest(), cases=[],
                  scope="sample processing and planning; no sound-device timing claim")
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-track-pan-") as temporary:
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
            rows = list(csv.DictReader((output / "pan-cases.tsv").open(encoding="utf-8", newline=""), delimiter="\t"))
            assert len(rows) == 43, len(rows)
            for row in rows:
                entry = variant(row, output / "flat", output / "endpoint")
                report["cases"].append(entry)
                print(f"Track pan: variant {entry['variant']} (mode {entry['mode']}) flat+endpoint PCM passed", flush=True)
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
    print(f"Track pan keys: {report['case_count']} variants, {report['sample_frames']} sample frames, "
          f"worst PCM difference {report['worst_pcm_difference']}, "
          f"{report['protocol']['coded_refusals']} refusal/recovery cases passed")


if __name__ == "__main__":
    main()
