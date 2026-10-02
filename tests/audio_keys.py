#!/usr/bin/env python3
"""Clip gain automation: native PCM, SDK curve oracle, chunk history and seeks."""
import argparse
import array
import math
import pathlib
import subprocess
import tempfile
import wave
from audio_stream import pcm, wire


def sample(frame, fps):
    return math.floor(frame * 48000 / fps + 0.5)


def linear_gain(absolute, placement, fps):
    points = [(sample(placement + f, fps), v) for f, v in
              zip((0, 13, 37, 61, 82), (0, 0.9, 0.15, 0.8, 0.2))]
    if absolute <= points[0][0]:
        return points[0][1]
    for (a, av), (b, bv) in zip(points, points[1:]):
        if absolute < b:
            return av + (bv - av) * (absolute - a) / (b - a)
    return points[-1][1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--client", type=pathlib.Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="genesis-audio-keys-") as directory:
        root = pathlib.Path(directory)
        source = root / "gain curve 日本語 %20.wav"
        data = array.array("h")
        for n in range(12 * 48000):
            t = n / 48000
            data.extend((int(6000 + 2000 * math.sin(2 * math.pi * 431.3 * t)),
                         int(-4000 + 1000 * math.cos(2 * math.pi * 211.7 * t))))
        with wave.open(str(source), "wb") as wav:
            wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(data.tobytes())
        output = root / "editor gain curves 日本語"
        done = subprocess.run([str(args.client.resolve()), str(args.worker.resolve()), str(source),
                               str(output), "gain-keys"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        assert done.returncode == 0, (done.returncode, done.stdout[-4000:], done.stderr[-4000:])
        metadata = {}
        curves = {}
        for row in (output / "gain-oracle.tsv").read_text(encoding="utf-8").splitlines():
            variant, fps, start, placement, frame, value = row.split("\t")
            variant, start, placement, frame = map(int, (variant, start, placement, frame))
            metadata[variant] = (float(fps), start, placement)
            curves.setdefault(variant, []).append((frame, float(value)))
        assert len(metadata) == 45
        oracle_checks = 0
        for variant, (fps, start, placement) in metadata.items():
            expected = pcm(output / f"gain-{variant}-whole.wav")
            base = pcm(output / f"gain-{variant}-base.wav")
            actual = array.array("h")
            chunks = sorted(output.glob(f"gain-{variant}-[0-9]*.wav"),
                            key=lambda p: int(p.stem.rsplit("-", 1)[1]))
            assert len(chunks) >= 4, (variant, len(chunks))
            for chunk in chunks:
                actual.extend(pcm(chunk))
            assert abs(len(actual) - len(expected)) <= 2, (variant, len(actual), len(expected))
            errors = [abs(a-b) for a, b in zip(actual, expected)]
            assert max(errors) <= 2 and sum(errors)/len(errors) < 0.1, (variant, max(errors), sum(errors)/len(errors))
            assert len(base) == len(expected), (variant, len(base), len(expected))
            for frame, gain in curves[variant]:
                at = sample(frame, fps) - sample(start, fps)
                if at * 2 + 1 >= len(base):
                    continue
                for ch in range(2):
                    difference = abs(expected[at*2+ch] - base[at*2+ch]*gain)
                    assert difference <= 2, (variant, frame, ch, gain, difference)
                    oracle_checks += 1
            if variant == 2 or variant >= 38:
                largest = max(abs(value - base[n]*linear_gain(sample(start, fps)+n//2, placement, fps))
                              for n, value in enumerate(expected))
                assert largest <= 2, ("independent sample-level linear gain", variant, largest)
            if variant == 4:
                points = [(sample(f, fps), v) for f, v in
                          zip((0,13,37,61,82), (0,0.9,0.15,0.8,0.2))]
                for boundary, value in points[1:]:
                    for offset, gain in ((-1, points[points.index((boundary,value))-1][1]), (0,value)):
                        at = boundary + offset
                        assert abs(expected[at*2] - base[at*2]*gain) <= 2, ("hold boundary", boundary, offset)
            if variant == 43:
                assert not any(expected) and not any(actual), "muted automated clip reached the output"
            else:
                assert max(abs(n) for n in expected) > 400, (variant, "automation produced silence")
        # Invalid automation is rejected before it opens or changes a decoder.
        invalid = ("GAINKEYS:0:0,0,nan,2", "GAINKEYS:0:0,0,-1,2", "GAINKEYS:0:0,0,1,38",
                   "GAINKEYS:0:0,0,1,2/0,1,0,2", "GAINKEYS:0:0,1,1,2/1600,0,0,2",
                   "GAINKEYS:0:", "GAINKEYS:9223372036854775807:0,0,1,2")
        target = root / "recovered.wav"
        commands = [f"WAVE {wire(target)} 1"]
        commands += [f"AUDIO {wire(source)} 0 1 0 1 0 0 1 0 - {token}" for token in invalid]
        commands += [f"AUDIO {wire(source)} 0 1 0 1 0 0 1 0 - GAINKEYS:0:0,0,0.5,2",
                     f"WAVECLOSE {wire(target)}"]
        recovery = subprocess.run([str(args.worker.resolve()), "--serve"], input="\n".join(commands)+"\n",
                                  capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert recovery.returncode == 0 and recovery.stdout.splitlines().count("ERR") == len(invalid), recovery.stdout
        assert recovery.stderr.count("[GA_AUDIO_GAIN_KEYS]") == len(invalid), recovery.stderr
        assert max(abs(a-b*0.5) for a,b in zip(pcm(target),data)) <= 1, "invalid envelope contaminated recovery"
        print(done.stdout.strip())
        print(f"Independent PCM: {oracle_checks} SDK curve samples, full-sample linear/hold checks, "
              "45 chunk/export comparisons, save/open and seven coded refusal/recovery cases passed")


if __name__ == "__main__":
    main()
