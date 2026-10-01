#!/usr/bin/env python3
"""Headless continuous audio: chunk boundaries must match one complete filter pass."""
import argparse
import array
import ctypes
import math
import os
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


def assert_process_exited(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        assert ctypes.get_last_error() == 87, ("cannot verify stalled child exit", pid, ctypes.get_last_error())
        return
    try:
        assert kernel.WaitForSingleObject(handle, 0) == 0, ("cancelled audio child survived", pid)
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--client", type=pathlib.Path)
    parser.add_argument("--cancel-client", type=pathlib.Path)
    parser.add_argument("--wrapper", type=pathlib.Path)
    args = parser.parse_args()
    if args.cancel_client and (not args.wrapper or os.name != "nt"):
        parser.error("--cancel-client requires --wrapper on native Windows")
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
        if args.cancel_client:
            for action in ("seek", "stop", "control"):
                for phase in ("reply", "write"):
                    output = root / f"cancel {action} {phase} 日本語"
                    output.mkdir()
                    env = dict(os.environ, GENESIS_TEST_WORKER=str(args.worker.resolve()),
                        GENESIS_TEST_STARTS=str(output / "starts.log"),
                        GENESIS_TEST_AUDIO_BLOCK=str(output / "blocked.pid"),
                        GENESIS_TEST_AUDIO_PARTIAL=str(output / "cancelled.wav"))
                    env.pop("GENESIS_TEST_CRASH", None)
                    env.pop("GENESIS_TEST_AUDIO_BLOCK_WRITE", None)
                    if phase == "write": env["GENESIS_TEST_AUDIO_BLOCK_WRITE"] = "1"
                    completed = subprocess.run([str(args.cancel_client.resolve()), str(args.wrapper.resolve()),
                        str(source), str(output), action, phase, str(args.worker.resolve())], env=env, text=True, encoding="utf-8",
                        errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                    assert completed.returncode == 0, (action, phase, completed.returncode, completed.stdout[-4000:])
                    assert not (output / "cancelled.wav").exists(), "partial audio survived cancellation"
                    assert_process_exited(int((output / "blocked.pid").read_text()))
                    starts = (output / "starts.log").read_text().splitlines()
                    assert len(starts) == (1 if action == "stop" else 2), starts
                    if action != "stop":
                        assert pcm(output / "recovered.wav") == pcm(output / "reference.wav")[:5 * 48000 * 2], "stale audio reached recovery output"
                    print(f"active {action} during blocked {phase}: {completed.stdout.strip()}", flush=True)
        print("Continuous native audio graphs: Unicode paths, exact chunk lengths and cross-boundary filter history passed")


if __name__ == "__main__":
    main()
