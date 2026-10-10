"""Keyed audio fades: SDK sample curves, decoded PCM and independent ramps.

Unkeyed PCM isolates decoding/resampling/rate/reverse from the envelope under
test. The expected fade product comes from SDK f64 values at destination samples
and independently applied in/out ramps; no keyed worker render is the oracle.
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
MAX_SAMPLE = 9007199254740991
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def sample(frame, fps):
    return math.floor(frame * RATE / fps + .5)


def collect(paths):
    result = array("h")
    for path in paths:
        result.extend(pcm(path))
    return result


def ramp_product(local, duration, fade_in_frames, fade_out_frames, fps):
    incoming, outgoing = max(0.0, fade_in_frames) / fps, max(0.0, fade_out_frames) / fps
    a = min(1.0, max(0.0, local / incoming)) if incoming > 0 else 1.0
    b = min(1.0, max(0.0, (duration-local) / outgoing)) if outgoing > 0 else 1.0
    return a * b


def compare(actual, baseline, oracle, fps, origin, placement, length, label):
    assert len(actual) == len(baseline) == len(oracle)*2, (label, len(actual), len(baseline), len(oracle))
    largest, total = 0.0, 0.0
    for index, (fade_in, fade_out, gain) in enumerate(oracle):
        assert all(math.isfinite(value) for value in (fade_in, fade_out, gain)), (label, index, "nonfinite SDK oracle")
        local = (origin + index - sample(placement, fps)) / RATE
        product = max(0.0, gain) * ramp_product(local, length/fps, fade_in, fade_out, fps)
        for channel in (0, 1):
            error = abs(actual[index*2+channel] - baseline[index*2+channel] * product)
            largest, total = max(largest, error), total+error
    assert largest <= 2, (label, largest, "decoded PCM times independent gain and two ramps")
    return dict(sample_frames=len(oracle), maximum_pcm_difference=largest, mean_pcm_difference=total/len(actual))


def protocol(worker, root):
    source = root / "constant stereo.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(array("h", [8192, -4096]*2000).tobytes())
    fade = "FADEKEYS:0:0:60:0,0,12,2/19200,24,4,2:-"
    gain = "GAINKEYS:0:0,0,0.5,2"
    bad = [("FADEKEYS:0:0:60:-:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:1e-320:0,0,1,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:nan:0,0,1,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:60:0,0,nan,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:60:0,0,3.5e38,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:60:0,0,-3.5e38,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:60:0,0,1,38:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:60:0,0,1,2/0,1,2,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("FADEKEYS:0:0:60:0,0,1,2/800,-1,2,2:-", "GA_AUDIO_FADE_KEYS", 800),
           (fade+" "+fade, "GA_AUDIO_FADE_KEYS", 800),
           (gain+" "+gain, "GA_AUDIO_FADE_KEYS", 800),
           ("UNKNOWN:0", "GA_AUDIO_FADE_KEYS", 800),
           (gain+" FADEKEYS:1:0:60:0,0,12,2:-", "GA_AUDIO_FADE_KEYS", 800),
           ("GAINKEYS:0:0,0,nan,2 "+fade, "GA_AUDIO_GAIN_KEYS", 800),
           (fade, "GA_AUDIO_FADE_KEYS", 0),
           (f"FADEKEYS:{MAX_SAMPLE-799}:0:60:0,0,12,2:-", "GA_AUDIO_FADE_KEYS", 801)]
    target = root / "recovered.wav"
    commands = [f"PLAYWAVE {wire(target)} 800"]
    line = lambda token, count=800: f"AUDIOSTREAM {wire(source)} 0 {800/RATE:.17f} 0 1 0 0 1 0 - 333 {2000/RATE:.17f} {count} {token}"
    commands += [line(token, count) for token, code, count in bad]
    commands += [line(fade+" "+gain), f"WAVECLOSE {wire(target)}"]
    reverse_order = root / "reverse token order.wav"
    commands += [f"PLAYWAVE {wire(reverse_order)} 800", line(gain+" "+fade).replace(" 333 ", " 334 "), f"WAVECLOSE {wire(reverse_order)}"]
    boundary = root / "exact final sample boundary.wav"
    commands += [f"PLAYWAVE {wire(boundary)} 800", line(f"FADEKEYS:{MAX_SAMPLE-799}:0:60:0,0,12,2:-").replace(" 333 ", " 335 "), f"WAVECLOSE {wire(boundary)}"]
    varying = root / "varying retained stereo.wav"
    authored = array("h", (value for n in range(2000) for value in
                         (1200+(n % 101)*7, -900-(n % 83)*5)))
    with wave.open(str(varying), "wb") as audio:
        audio.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(authored.tobytes())
    def retained(token, ident, begin=0, count=512):
        return (f"AUDIOSTREAM {wire(varying)} {begin/RATE:.17f} {512/RATE:.17f} 0 1 0 0 1 {begin/RATE:.17f} - "
                f"{ident} {(2000-begin)/RATE:.17f} {count} {token}")
    unchanged = "FADEKEYS:0:0:60:0,0,0,2:-"
    continuation = "FADEKEYS:512:0:60:0,0,0,2:-"
    outputs = []
    for ident, inject in ((555, True), (556, False)):
        primer = root / f"retained-{ident}-primer.wav"
        following = root / f"retained-{ident}-continuation.wav"
        commands += [f"PLAYWAVE {wire(primer)} 512", retained(unchanged, ident), f"WAVECLOSE {wire(primer)}",
                     f"PLAYWAVE {wire(following)} 512"]
        if inject:
            commands += [retained(token, ident, 512, count) for token, code, count in bad]
        commands += [retained(continuation, ident, 512), f"WAVECLOSE {wire(following)}"]
        outputs.append(following)
    fresh = root / "retained-fresh-recovery.wav"
    commands += [f"PLAYWAVE {wire(fresh)} 512", retained(continuation, 557, 512), f"WAVECLOSE {wire(fresh)}"]
    done = subprocess.run([str(worker), "--serve"], input="\n".join(commands)+"\n", capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=FLAGS)
    assert done.returncode == 0 and done.stdout.splitlines().count("ERR") == len(bad)*2, (done.stdout, done.stderr)
    for code in ("GA_AUDIO_FADE_KEYS", "GA_AUDIO_GAIN_KEYS"):
        assert done.stderr.count("["+code+"]") == 2*sum(expected == code for token, expected, count in bad), done.stderr
    recovered, swapped = pcm(target), pcm(reverse_order)
    assert recovered == swapped and len(recovered) == 1600, "envelope order or failed requests changed decoder history"
    largest = 0.0
    for n in range(800):
        fade_length = 12 + (4-12)*n/19200
        envelope = (n/RATE)/(fade_length/60)
        for channel, value in enumerate((8192, -4096)):
            expected = value/32768*32767*.5*envelope
            largest = max(largest, abs(recovered[n*2+channel]-expected))
    assert largest <= 1, largest
    accepted = pcm(boundary)
    assert len(accepted) == 1600 and all(abs(value-wanted) <= 1 for value, wanted in zip(accepted, [8192, -4096]*800)), "exact last sample was refused or shifted"
    poisoned, reference, restarted = (pcm(path) for path in (*outputs, fresh))
    assert poisoned == reference == restarted and len(poisoned) == 1024, "malformed continuation mutated retained decoder state"
    retained_error = max(abs(value-wanted/32768*32767) for value, wanted in zip(poisoned, authored[1024:2048]))
    assert retained_error <= 1, (retained_error, "retained continuation independent authored PCM")
    return dict(coded_refusals=len(bad)*2, recovery_maximum_pcm_difference=largest,
                token_orders_equal=True, exact_last_sample=MAX_SAMPLE, zero_frame_refused=True,
                primed_retained_continuation_unchanged=True, fresh_recovery_equal=True,
                retained_continuation_authored_maximum_pcm_difference=retained_error,
                decoder_mutation_refused_before_continuation=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    worker, client = args.worker.resolve(), args.client.resolve()
    report = dict(schema="genesis.audio_fade_keys.v1", worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
                  client_sha256=hashlib.sha256(client.read_bytes()).hexdigest(), cases=[], scope="sample processing and editor planning; no sound-device timing claim")
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-fade-keys-") as temporary:
        root = Path(temporary)
        source = root / "authored44100 日本語 %20.wav"
        values = array("h", (value for n in range(8*44100) for value in
            (int(6000+1800*math.sin(2*math.pi*431.3*n/44100)), int(-4000+1100*math.cos(2*math.pi*211.7*n/44100)))))
        with wave.open(str(source), "wb") as audio:
            audio.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
            audio.writeframes(values.tobytes())
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        output = root / "editor fades"
        done = subprocess.run([str(client), str(worker), str(source), str(output)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180, creationflags=FLAGS)
        try:
            assert done.returncode == 0, (done.returncode, done.stdout[-3000:], done.stderr[-3000:])
            rows = list(csv.DictReader((output / "fade-cases.tsv").open(encoding="utf-8", newline=""), delimiter="\t"))
            assert len(rows) == 49, len(rows)
            for row in rows:
                variant = int(row["variant"])
                fps, start, placement, length = float(row["fps"]), int(row["start"]), int(row["placement"]), int(row["length"])
                prefix = f"fade-{variant}"
                baseline = pcm(output / (prefix+"-base.wav"))
                raw = (output / (prefix+"-oracle.f64")).read_bytes()
                assert len(raw) == len(baseline)//2*24
                oracle = list(struct.iter_unpack("<ddd", raw))
                expected_frames = sample(placement+length, fps)-sample(start, fps)
                assert len(baseline) == expected_frames*2, (variant, len(baseline), expected_frames)
                whole = pcm(output / (prefix+"-whole.wav"))
                # Whole-WAVE allocation uses ceil(range seconds); chunk lengths
                # use differences of absolute rounded endpoints. Check both.
                whole_frames = math.ceil((placement+length-start)/fps*RATE)
                assert len(whole) == whole_frames*2, (variant, len(whole), whole_frames)
                assert abs(whole_frames-expected_frames) <= 1
                if whole_frames > expected_frames:
                    assert not any(whole[-2:]), "rounded extra frame must be silence"
                whole = whole[:expected_frames*2]
                def ordered(suffix):
                    return sorted(output.glob(prefix+suffix+"[0-9]*.wav"), key=lambda path: int(path.stem.rsplit(suffix, 1)[1]))
                chunks = collect(ordered("-chunk"))
                entry = dict(variant=variant, mode=int(row["mode"]), fps=fps, range_start=start, placement=placement,
                             saved_open_and_signature_checked=True, integer_editor_curve_checks=int(row["integer_checks"]))
                entry["whole"] = compare(whole, baseline, oracle, fps, sample(start, fps), placement, length, (variant, "whole"))
                entry["chunks"] = compare(chunks, baseline, oracle, fps, sample(start, fps), placement, length, (variant, "uneven chunks"))
                seek_base = pcm(output / (prefix+"-seek-base.wav"))
                seeks = collect(ordered("-seek"))
                seek_start = placement+9
                offset = sample(seek_start, fps)-sample(start, fps)
                seek_frames = sample(placement+length, fps)-sample(seek_start, fps)
                seek_allocation = math.ceil((placement+length-seek_start)/fps*RATE)
                assert len(seek_base) == seek_allocation*2 and abs(seek_allocation-seek_frames) <= 1
                if seek_allocation > seek_frames:
                    assert not any(seek_base[-2:]), "fresh seek rounded extra frame must be silence"
                seek_base = seek_base[:seek_frames*2]
                entry["fresh_seek"] = compare(seeks, seek_base, oracle[offset:], fps, sample(seek_start, fps), placement, length, (variant, "fresh seek"))
                report["cases"].append(entry)
                print(f"Fade keys: {variant}, SDK sample curve × gain × in/out ramps passed", flush=True)
            assert original == hashlib.sha256(source.read_bytes()).hexdigest(), "source modified"
            report["protocol"] = protocol(worker, root)
            report.update(passed=True, case_count=len(rows), sdk_sample_values=sum(case["whole"]["sample_frames"]*3 for case in report["cases"]),
                          integer_editor_checks=sum(case["integer_editor_curve_checks"] for case in report["cases"]))
        except Exception as problem:
            report.update(passed=False, execution_error=str(problem), client_stdout=done.stdout[-4000:], client_stderr=done.stderr[-4000:])
            if output.exists():
                report["diagnostics"] = {str(path.relative_to(output)):path.read_text(encoding="utf-8",errors="replace")[-5000:]
                                         for path in output.rglob("*") if path.is_file() and path.suffix in (".jsonl", ".tsv", ".id", ".log") and path.stat().st_size < 65536}
            args.report.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise
    args.report.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Fade keys: {report['case_count']} cases, {report['sdk_sample_values']} SDK values, {report['integer_editor_checks']} integer editor checks, {report['protocol']['coded_refusals']} refusal/recovery cases passed")


if __name__ == "__main__":
    main()
