"""Long native audio graph continuity at fractional timeline buffer boundaries.

Compare 181 seconds of audible, resampled stereo PCM and sample gain automation
with an uninterrupted native filter pass. This is a processing check; the separate
playback_timing gate measures the real device cursor without speaker output.
"""
import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

from audio_stream import pcm, wire
from media_runtime import tool

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
RATE = 48000
FPS = 60000/1001
CHAIN = "acompressor=threshold=0.08:ratio=4:attack=20:release=350,aecho=0.8:0.9:240:0.35"


def execute(worker, commands):
    done = subprocess.run([str(worker), "--serve"], input="\n".join(commands)+"\n",
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120, creationflags=FLAGS)
    assert done.returncode == 0 and "ERR" not in done.stdout, (done.returncode, done.stdout[-2000:], done.stderr[-3000:])


def sample(frame):
    return math.floor(frame*RATE/FPS+0.5)


def envelope(start):
    points = ((0, 0.15), (sample(301), 0.8), (sample(701), 0.25),
              (sample(4801), 0.65), (sample(9500), 0.4))
    return "GAINKEYS:"+str(start)+":"+"/".join(f"{at},{frame},{gain},2" for (at, gain), frame in
                                               zip(points, (0, 301, 701, 4801, 9500)))


def commands_for(source, output, start, count, length, streaming=False, clip=1):
    duration = count/RATE
    command = "AUDIOSTREAM" if streaming else "AUDIO"
    fields = [command, wire(source), repr(start/RATE), repr(duration), "0", "0.45", "0.25", "0.4",
              repr(length/RATE), repr(start/RATE), CHAIN]
    if streaming:
        fields.extend((str(clip), repr((length-start)/RATE), str(count)))
    fields.append(envelope(start))
    return [f"PLAYWAVE {wire(output)} {count}" if streaming else f"WAVE {wire(output)} {duration}",
            " ".join(fields), f"WAVECLOSE {wire(output)}"]


def compare(actual, expected, label):
    assert len(actual) == len(expected), (label, len(actual), len(expected))
    peak = total = 0
    for left, right in zip(actual, expected):
        difference = abs(left-right)
        peak = max(peak, difference)
        total += difference
    mean = total/len(actual)
    assert peak <= 2 and mean < 0.1, (label, peak, mean)
    assert max(abs(value) for value in actual) > 500, (label, "inaudible PCM")
    return {"samples_per_channel": len(actual)//2, "maximum_pcm_difference": peak,
            "mean_pcm_difference": mean, "pcm_sha256": hashlib.sha256(actual.tobytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    worker = args.worker.resolve()
    with tempfile.TemporaryDirectory(prefix="genesis-long-audio-") as temporary:
        root = Path(temporary)
        source = root / "181 seconds 44.1k 日本語 %20.wav"
        generated = subprocess.run([str(tool(worker, "ffmpeg")), "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i",
            "aevalsrc=0.18*sin(2*PI*431.3*t)+0.06*sin(2*PI*71.7*t)|0.14*cos(2*PI*233.7*t):s=44100:d=181",
            "-c:a", "pcm_s16le", str(source)], capture_output=True, timeout=60, creationflags=FLAGS)
        assert generated.returncode == 0, generated.stderr[-2000:]
        length = 181*RATE
        whole = root / "uninterrupted.wav"
        commands = commands_for(source, whole, 0, length, length)
        at = index = 0
        outputs = []
        boundaries = []
        # Exactly the production floor(fps*5) timeline-frame spans; their rounded
        # absolute sample differences alternate at this fractional rate.
        while at < length:
            end = min(length, sample((index+1)*math.floor(FPS*5)))
            output = root / f"chunk-{index}.wav"
            outputs.append((output, end-at))
            commands.extend(commands_for(source, output, at, end-at, length, True))
            if end < length:
                boundaries.append(end)
            at, index = end, index+1
        execute(worker, commands)
        expected = pcm(whole)
        actual = array.array("h")
        for output, count in outputs:
            block = pcm(output)
            assert len(block) == count*2, (output.name, len(block), count)
            actual.extend(block)
        continuous = compare(actual, expected, "181-second continuous PCM")
        continuous_chunks = len(outputs)
        assert len(actual) == 181*48000*2
        boundary_checks = 0
        for boundary in boundaries:
            for n in range(boundary*2-32, boundary*2+32):
                assert abs(actual[n]-expected[n]) <= 2, (boundary, n, actual[n], expected[n])
                boundary_checks += 1
        print(f"181-second continuous PCM: {len(outputs)} chunks, {len(boundaries)} boundaries, "
              f"max {continuous['maximum_pcm_difference']}, mean {continuous['mean_pcm_difference']:.6f}", flush=True)
        # A seek has a fresh decoder/filter history; compare a fresh uninterrupted
        # pass from that source position, rather than retaining pre-seek history.
        start = sample(7313)
        seek_count = sample(551)
        whole_seek = root / "fresh seek.wav"
        # Keep the same remaining source range for both graphs. Ending the
        # resampler at the requested device pull can alter its final few samples;
        # a seeked playback graph still has the rest of the clip available.
        commands = commands_for(source, whole_seek, start, length-start, length)
        commands[0] = f"WAVE {wire(whole_seek)} {seek_count/RATE}"
        seek_outputs = []
        seek_at = 0
        for n, size in enumerate((sample(19), sample(137), seek_count-sample(156))):
            output = root / f"seek-{n}.wav"
            commands.extend(commands_for(source, output, start+seek_at, size, length, True, 2))
            seek_outputs.append(output)
            seek_at += size
        assert seek_at == seek_count
        execute(worker, commands)
        resumed = array.array("h")
        for output in seek_outputs:
            resumed.extend(pcm(output))
        seek = compare(resumed, pcm(whole_seek), "fresh resumed seek")
        # Both fractional start and very short duration used to be serialized as
        # scientific notation, which atrim's duration parser rejects. Preserve
        # exact audible source samples, including a one-sample seeked range.
        short = root / "tiny sample seeks.wav"
        tiny_expected = array.array("h", (value for n in range(2048)
                                         for value in (6000+n%37, -4000-n%29)))
        with wave.open(str(short), "wb") as wav:
            wav.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(tiny_expected.tobytes())
        tiny_commands, tiny_cases = [], []
        for offset in (1, 2, 31):
            for count in (1, 2, 17):
                whole = root / f"tiny-{offset}-{count}.wav"
                pulled = root / f"tiny-{offset}-{count}-pull.wav"
                duration = (count-.25)/RATE
                tiny_commands.extend((f"WAVE {wire(whole)} {duration}",
                    f"AUDIO {wire(short)} {offset/RATE} {duration} 0 1 0 0 1 0 -", f"WAVECLOSE {wire(whole)}",
                    f"PLAYWAVE {wire(pulled)} {count}",
                    f"AUDIOSTREAM {wire(short)} {offset/RATE} {count/RATE} 0 1 0 0 1 0 - {100+offset*100+count} {(2048-offset)/RATE} {count}",
                    f"WAVECLOSE {wire(pulled)}"))
                tiny_cases.append((whole, pulled, offset, count))
        execute(worker, tiny_commands)
        for whole, pulled, offset, count in tiny_cases:
            wanted = tiny_expected[offset*2:(offset+count)*2]
            assert pcm(whole) == wanted == pcm(pulled), (offset, count, "tiny source seek shifted or lost samples")
        retimed = []
        for clip, speed in ((201, 0.5), (202, 2.0)):
            output_count = round(12/speed*RATE)
            whole = root / f"rate-{speed}-whole.wav"
            chain = f"atempo={speed},aecho=0.8:0.9:240:0.35"
            commands = [f"WAVE {wire(whole)} {output_count/RATE}",
                        f"AUDIO {wire(source)} 0 12 0 1 0 0 {output_count/RATE} 0 {chain}", f"WAVECLOSE {wire(whole)}"]
            outputs = []
            at = 0
            while at < output_count:
                count = min(output_count-at, RATE*5)
                output = root / f"rate-{speed}-{at}.wav"
                commands.extend((f"PLAYWAVE {wire(output)} {count}",
                    f"AUDIOSTREAM {wire(source)} {at/RATE*speed} {count/RATE*speed} 0 1 0 0 {output_count/RATE} {at/RATE} {chain} {clip} {12-at/RATE*speed} {count}",
                    f"WAVECLOSE {wire(output)}"))
                outputs.append(output)
                at += count
            execute(worker, commands)
            actual = array.array("h")
            for output in outputs:
                actual.extend(pcm(output))
            result = compare(actual, pcm(whole), f"{speed}x source rate")
            # A too-small post-filter buffer previously silenced the latter half
            # of slow audio. Require real content throughout the output range.
            for at in range(0, output_count, RATE):
                assert max(abs(value) for value in actual[at*2:min(output_count, at+RATE)*2]) > 500
            retimed.append(dict(speed=speed, **result))
        report = {"schema": "genesis.audio-continuity", "revision": 1,
                  "scope": "native worker PCM processing; real device/picture timing is measured separately",
                  "source_rate": 44100, "output_rate": RATE, "sequence_fps": FPS,
                  "duration_seconds": 181, "chunk_count": continuous_chunks, "buffer_boundaries": len(boundaries),
                  "boundary_sample_checks": boundary_checks, "continuous": continuous, "fresh_seek": seek,
                  "exact_tiny_seek_cases": len(tiny_cases),
                  "retimed": retimed,
                  "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest()}
        if args.report:
            args.report.resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
