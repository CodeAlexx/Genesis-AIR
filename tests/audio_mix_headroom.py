"""Independent authored-stereo oracle for final-output audio mix headroom.

The reference sums signed source samples in double precision, then bounds the
completed mix. It never uses a second worker render as its expected signal.
Whole playback, uneven retained pulls, fresh seek, lossless encoder, meters,
oscilloscope and selected direct-DFT bins must agree with that same signal.
"""

import argparse
from array import array
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import wave

from PIL import Image
from media_runtime import tool
from audio_stream import wire

RATE = 48000
FRAMES = 24013
FFT_SIZE = 4096
SCOPE_POINTS = 257
DFT_BINS = (0, 1, 2, 31, 32, 33, 95, 96, 97, 159, 160, 161)
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def author(path, values):
    """IEEE f32 stereo WAV; no codec/rematrix/normalizer creates the fixture."""
    payload = array("f", values).tobytes()
    fmt = struct.pack("<HHIIHH", 3, 2, RATE, RATE * 8, 8, 32)
    path.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(payload)) + b"WAVEfmt " +
                     struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(payload)) + payload)
    # Read back authored float values for the reference, including their exact
    # representable source rounding; this does not decode or render the mix.
    return struct.unpack("<" + "f" * (len(payload) // 4), payload)


def final_signal(terms, sources):
    return [max(-1.0, min(1.0, sum(sources[name][at] * gain * pan[at % 2]
                                  for name, gain, pan in terms)))
            for at in range(FRAMES * 2)]


def pcm16(values):
    # Playback WAV uses symmetric PCM16 full scale. Exact endpoints and signed
    # quantization remain checked; two codes permit ordinary float rounding.
    return [int(math.copysign(math.floor(abs(value) * 32767 + .5), value)) for value in values]


def read_pcm(path, count):
    with wave.open(str(path), "rb") as audio:
        assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth(), audio.getnframes()) == (2, RATE, 2, count)
        values = array("h", audio.readframes(count))
    return values


def floats(path, count):
    raw = path.read_bytes()
    assert len(raw) == count * 4, (path.name, len(raw), count)
    values = struct.unpack("<" + "f" * count, raw)
    assert all(math.isfinite(value) for value in values)
    return values


def decibels(value):
    return max(-90.0, 20 * math.log10(value)) if value > 0 else -90.0


def levels(values):
    channels = [values[side::2] for side in (0, 1)]
    return [decibels(max(abs(value) for value in channel)) for channel in channels] + [
        decibels(math.sqrt(sum(value * value for value in channel) / len(channel))) for channel in channels]


def dft(values):
    # Selected exact FFT bins calculated by the defining Fourier sum, independent
    # of the worker's radix-two FFT or bar grouping implementation.
    windowed = [sum(values[2*n:2*n+2]) / 2 * (.5 - .5 * math.cos(2 * math.pi * n / (FFT_SIZE - 1)))
                for n in range(FFT_SIZE)]
    return [abs(sum(value * complex(math.cos(-2 * math.pi * k * n / FFT_SIZE),
                                   math.sin(-2 * math.pi * k * n / FFT_SIZE))
                    for n, value in enumerate(windowed))) for k in DFT_BINS]


def execute(worker, commands):
    child = subprocess.run([str(worker), "--serve", "--size", "16", "16"],
                           input="\n".join(commands) + "\n", text=True, encoding="utf-8", errors="replace",
                           capture_output=True, timeout=90, creationflags=FLAGS)
    assert child.returncode == 0 and "ERR" not in child.stdout, (child.returncode, child.stdout[-3000:], child.stderr[-3000:])
    assert sum(line.startswith("DONE") for line in child.stdout.splitlines()) == len(commands), child.stdout[-3000:]


def audio_lines(terms, paths, start=0, count=FRAMES, streaming=False, identity=0):
    result = []
    for at, (name, gain, pan) in enumerate(terms):
        chain = "-" if pan == (1, 1) else f"pan=stereo|c0={pan[0]}*c0|c1={pan[1]}*c1"
        fields = ["AUDIOSTREAM" if streaming else "AUDIO", wire(paths[name]),
                  f"{start/RATE:.17f}", f"{count/RATE:.17f}", "0", str(gain), "0", "0",
                  f"{FRAMES/RATE:.17f}", f"{start/RATE:.17f}", chain]
        if streaming:
            fields += [str(identity + at), f"{(FRAMES-start)/RATE:.17f}", str(count)]
        result.append(" ".join(fields))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    worker = args.worker.resolve()
    ffmpeg, ffprobe = tool(worker, "ffmpeg"), tool(worker, "ffprobe")
    report = dict(schema="genesis.audio_mix_headroom.v1", worker_sha256=sha(worker),
                  scope="native mix processing and scopes; no sound device or UI performance claim",
                  source_format="independently authored IEEE f32 stereo 48000Hz", frames=FRAMES,
                  thresholds=dict(maximum_pcm16_codes=2, maximum_pcm24_amplitude=2e-6,
                                  maximum_levels_db=.002, maximum_scope_amplitude=2e-6,
                                  maximum_selected_dft_magnitude=.02), cases=[], failures=[])
    checks = 0

    def check(entry, name, actual, expected, tolerance):
        nonlocal checks
        checks += 1
        assert len(actual) == len(expected), (name, len(actual), len(expected))
        assert all(math.isfinite(value) for value in actual), (name, "non-finite output")
        error = max(abs(a-b) for a, b in zip(actual, expected))
        result = dict(name=name, value_count=len(actual), maximum_difference=error, tolerance=tolerance, passed=error <= tolerance)
        entry.setdefault("checks", []).append(result)
        if not result["passed"]:
            report["failures"].append(dict(case=entry["name"], **result))

    with tempfile.TemporaryDirectory(prefix="genesis-audio-headroom-") as temporary:
        root = Path(temporary)
        paths, sources = {}, {}
        definitions = {"plus_a": lambda n: (.8, .8), "plus_b": lambda n: (.8, .8),
                       "minus": lambda n: (-.8, -.8), "asym_a": lambda n: (.7, -.7),
                       "asym_b": lambda n: (.65, -.65),
                       "tone_a": lambda n: (.8 * math.sin(2 * math.pi * 32 * n / FFT_SIZE),) * 2,
                       "tone_b": lambda n: (.8 * math.sin(2 * math.pi * 32 * n / FFT_SIZE),) * 2}
        for name, generate in definitions.items():
            paths[name] = root / (name + " 日本語 %20.wav")
            sources[name] = author(paths[name], (value for n in range(FRAMES) for value in generate(n)))
        report["source_sha256"] = {name: sha(path) for name, path in paths.items()}
        unit = lambda name: (name, 1, (1, 1))
        cases = [("single_" + name, [unit(name)]) for name in ("plus_a", "plus_b", "minus")]
        cases += [("order_" + str(index), [unit(name) for name in order])
                  for index, order in enumerate(itertools.permutations(("plus_a", "plus_b", "minus")))]
        cases += [("positive_overload", [unit("plus_a"), unit("plus_b")]),
                  ("negative_overload", [unit("minus"), unit("minus")]),
                  ("gain_pan", [("plus_a", 1.25, (1, 1)), ("plus_b", .75, (.5, 0)), ("minus", 1.2, (1, 1))]),
                  ("asymmetric_overload", [unit("asym_a"), unit("asym_b")]),
                  ("clipped_sine", [unit("tone_a"), unit("tone_b")])]
        picture = root / "picture.png"
        Image.new("RGB", (16, 16), (43, 81, 139)).save(picture)
        # Reuse only neutral VIDEO-wire defaults to give the lossless container
        # a real picture. No audio expectation is derived from application code.
        text = (Path(__file__).resolve().parent.parent / "src/timeline_media.ai").read_text(encoding="utf-8")
        neutral = text.split("fn neutral()", 1)[1].split("\nfn source_path", 1)[0]
        fields = ["0"] * 108
        for index, value in re.findall(r'put\(values, (\d+), "([^"]+)"\)', neutral):
            fields[int(index)] = value
        fields[27:33] = ["1"] * 6
        fields[0] = wire(picture)
        commands, outputs = [], []
        duration = (FRAMES - .25) / RATE
        for index, (name, terms) in enumerate(cases):
            prefix = root / name
            whole = prefix.with_suffix(".wav")
            encodings = (("pcm_s24le", prefix.with_suffix(".mkv")),
                         ("pcm_f32le", root / f"{name}-float.mkv"))
            commands += [f"WAVE {wire(whole)} {duration:.17f}", *audio_lines(terms, paths), f"WAVECLOSE {wire(whole)}"]
            chunk_paths, at = [], 0
            for block, count in enumerate((1001, 11999, FRAMES - 13000)):
                output = root / f"{name}-chunk{block}.wav"
                commands += [f"PLAYWAVE {wire(output)} {count}", *audio_lines(terms, paths, at, count, True, index * 100 + 1), f"WAVECLOSE {wire(output)}"]
                chunk_paths.append((output, count))
                at += count
            seek_paths, at = [], 137
            for block, count in enumerate((613, 5000)):
                output = root / f"{name}-seek{block}.wav"
                commands += [f"PLAYWAVE {wire(output)} {count}", *audio_lines(terms, paths, at, count, True, index * 100 + 51), f"WAVECLOSE {wire(output)}"]
                seek_paths.append((output, count))
                at += count
            for codec, encoded in encodings:
                commands += [f"OPEN {wire(encoded)} 16 16 30 1 0 0 ffv1 {duration:.17f} 0 - 320000 {codec} 30",
                             "ENC " + " ".join(fields), *audio_lines(terms, paths), "CLOSE"]
            for verb, count in (("LEVELS", ""), ("SAMPLES", str(SCOPE_POINTS) + " "), ("SPECTRUM", "2048 ")):
                output = root / f"{name}-{verb}.f32"
                commands += [f"MEAS {duration:.17f}", *audio_lines(terms, paths), f"{verb} {count}{wire(output)}"]
            outputs.append((name, terms, whole, encodings, chunk_paths, seek_paths))
        report["command_count"] = len(commands)
        execute(worker, commands)
        for name, terms, whole, encodings, chunks, seeks in outputs:
            expected = final_signal(terms, sources)
            wanted_pcm = pcm16(expected)
            entry = dict(name=name, terms=terms)
            check(entry, "whole_playback_pcm", read_pcm(whole, FRAMES), wanted_pcm, 2)
            check(entry, "uneven_retained_chunks", [value for output, count in chunks for value in read_pcm(output, count)], wanted_pcm, 2)
            check(entry, "fresh_seek_and_retained_followup", [value for output, count in seeks for value in read_pcm(output, count)], wanted_pcm[137*2:(137+5613)*2], 2)
            for codec, encoded in encodings:
                info = subprocess.run([str(ffprobe), "-v", "error", "-show_streams", "-of", "json", str(encoded)], capture_output=True, timeout=30, creationflags=FLAGS)
                assert info.returncode == 0, info.stderr
                stream = next(value for value in json.loads(info.stdout)["streams"] if value["codec_type"] == "audio")
                assert (stream["codec_name"], stream["sample_rate"], stream["channels"]) == (codec, "48000", 2), stream
                decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(encoded), "-vn", "-f", "f32le", "pipe:1"], capture_output=True, timeout=30, creationflags=FLAGS)
                assert decoded.returncode == 0 and len(decoded.stdout) == FRAMES * 8, (decoded.stderr, len(decoded.stdout))
                actual = struct.unpack("<" + "f" * (FRAMES*2), decoded.stdout)
                # Floating PCM preserves excursions; integer conversion cannot
                # accidentally supply the missing final-output limiter here.
                name_of_check = "lossless_encoder_pcm" if codec == "pcm_s24le" else "lossless_encoder_float_pcm"
                check(entry, name_of_check, actual, expected, 2e-6)
            check(entry, "output_peak_rms_dbfs", floats(root / f"{name}-LEVELS.f32", 4), levels(expected), .002)
            check(entry, "output_oscilloscope", floats(root / f"{name}-SAMPLES.f32", SCOPE_POINTS),
                  [expected[(point * FFT_SIZE // SCOPE_POINTS) * 2] for point in range(SCOPE_POINTS)], 2e-6)
            spectrum = floats(root / f"{name}-SPECTRUM.f32", 2048)
            check(entry, "final_output_direct_dft", [spectrum[index] for index in DFT_BINS], dft(expected), .02)
            entry["passed"] = all(result["passed"] for result in entry["checks"])
            report["cases"].append(entry)
            print(f"Audio headroom: {name}, eight independent output checks, passed={entry['passed']}", flush=True)
        assert report["source_sha256"] == {name: sha(path) for name, path in paths.items()}, "worker changed authored sources"
    report.update(case_count=len(cases), check_count=checks, compared_pcm16_values=sum(result["value_count"] for case in report["cases"] for result in case["checks"] if result["name"] in ("whole_playback_pcm", "uneven_retained_chunks", "fresh_seek_and_retained_followup")), passed=not report["failures"])
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert report["passed"], f"{len(report['failures'])} independent audio headroom checks failed; see {args.report}"
    print(f"Audio headroom: {len(cases)} cases, {checks} checks passed", flush=True)


if __name__ == "__main__":
    main()
