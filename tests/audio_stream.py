#!/usr/bin/env python3
"""Headless continuous audio: chunk boundaries must match one complete filter pass."""
import argparse
import array
import math
import pathlib
import subprocess
import tempfile
import wave


def wire(value):
    return str(value).replace("%", "%25").replace(" ", "%20").replace("\t", "%09").replace("\n", "%0A").replace("\r", "%0D")


def pcm(path):
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 2 and wav.getframerate() == 48000 and wav.getsampwidth() == 2
        result = array.array("h")
        result.frombytes(wav.readframes(wav.getnframes()))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--client", type=pathlib.Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="genesis-audio-stream-") as directory:
        root = pathlib.Path(directory)
        source = root / "continuous 日本語 %20, clip.wav"
        samples = array.array("h")
        for n in range(12 * 48000):
            t = n / 48000
            envelope = 0.8 if 4.8 < t < 5.1 or 9.8 < t < 10.1 else 0.1
            samples.extend((int(28000 * envelope * math.sin(t * 2 * math.pi * 881.3)),
                            int(16000 * envelope * math.sin(t * 2 * math.pi * 233.7))))
        with wave.open(str(source), "wb") as wav:
            wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(samples.tobytes())
        chains = {"echo": "aecho=0.8:0.9:240:0.5", "compressor": "acompressor=threshold=0.05:ratio=6:attack=20:release=400", "modulation": "aphaser=decay=0.5:speed=0.8", "plain": "-"}
        for index, (name, chain) in enumerate(chains.items()):
            whole = root / (name + "-whole.wav")
            commands = [f"WAVE {wire(whole)} 12", f"AUDIO {wire(source)} 0 12 0 1 0 0 12 0 {chain}", f"WAVECLOSE {wire(whole)}"]
            chunks = []
            for at, duration in ((0, 5), (5, 5), (10, 2)):
                chunk = root / (name + f"-{at}.wav")
                chunks.append(chunk)
                commands.extend([f"PLAYWAVE {wire(chunk)} {duration * 48000}",
                    f"AUDIOSTREAM {wire(source)} {at} {duration} 0 1 0 0 12 {at} {chain} {index + 1} {12-at} {duration * 48000}", f"WAVECLOSE {wire(chunk)}"])
            completed = subprocess.run([str(args.worker.resolve()), "--serve"], input="\n".join(commands) + "\n", text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            assert completed.returncode == 0 and "ERR" not in completed.stdout, (completed.returncode, completed.stdout[-4000:])
            expected = pcm(whole)
            actual = array.array("h")
            for chunk in chunks:
                actual.extend(pcm(chunk))
            assert len(expected) == len(actual) == 12 * 48000 * 2
            differences = [abs(a-b) for a,b in zip(actual, expected)]
            mean = sum(differences) / len(differences)
            assert max(differences) <= 2 and mean < 0.1, (name, max(differences), mean)
            print(f"{name}: 12 seconds in three pulls, max {max(differences)} PCM units, mean {mean:.6f}", flush=True)
        if args.client:
            output = root / "editor audio 日本語"
            completed = subprocess.run([str(args.client.resolve()), str(args.worker.resolve()), str(source), str(output)],
                text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            assert completed.returncode == 0, (completed.returncode, completed.stdout[-4000:])
            for variant in range(17):
                whole = pcm(output / f"case-{variant}-whole.wav")
                actual = array.array("h")
                chunks = sorted(output.glob(f"case-{variant}-[0-9]*.wav"))
                assert len(chunks) >= 2
                for chunk in chunks:
                    actual.extend(pcm(chunk))
                assert abs(len(actual)-len(whole)) <= 2, (variant,len(actual),len(whole))
                differences = [abs(a-b) for a,b in zip(actual,whole)]
                mean = sum(differences)/len(differences)
                assert max(differences) <= 2 and mean < 0.1, (variant,max(differences),mean)
                print(f"editor case {variant}: {len(chunks)} chunks, max {max(differences)} PCM units, mean {mean:.6f}", flush=True)
            recovered = pcm(output / "recovered.wav")
            expected = pcm(output / "case-3-whole.wav")[:5 * 48000 * 2]
            assert recovered == expected, "failed filter graph contaminated the next playback session"
            print(completed.stdout.strip(), flush=True)
        print("Continuous native audio graphs: Unicode paths, exact chunk lengths and cross-boundary filter history passed")


if __name__ == "__main__":
    main()
