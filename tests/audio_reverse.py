#!/usr/bin/env python3
"""Native reverse playback: bounded startup/memory and continuous post-reverse effects."""
import argparse
import array
import ctypes
import json
import math
import os
import pathlib
import queue
import subprocess
import tempfile
import threading
import time
import wave

from audio_stream import pcm, wire


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in (
            "peak", "working", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]


def peak_memory(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    api.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(MemoryCounters), ctypes.c_ulong]
    api.GetProcessMemoryInfo.restype = ctypes.c_int
    handle = kernel.OpenProcess(0x410, False, pid)
    assert handle, ("cannot inspect owned worker memory", ctypes.get_last_error())
    try:
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        assert api.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb), ctypes.get_last_error()
        return counters.peak
    finally:
        kernel.CloseHandle(handle)


class Worker:
    def __init__(self, binary):
        self.messages = queue.Queue()
        self.errors = []
        self.process = subprocess.Popen([str(binary), "--serve"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
        def read_output():
            for line in self.process.stdout:
                self.messages.put(line.rstrip())
            self.messages.put(None)
        def read_errors():
            for line in self.process.stderr:
                self.errors.append(line.rstrip())
                del self.errors[:-40]
        self.readers = [threading.Thread(target=read_output, daemon=True),
                        threading.Thread(target=read_errors, daemon=True)]
        for reader in self.readers:
            reader.start()

    def command(self, line):
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 30
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("reverse worker reply exceeded its deadline")
            reply = self.messages.get(timeout=remaining)
            assert reply is not None, ("worker exited", self.errors)
            assert not reply.startswith("ERR"), (reply, self.errors)
            if reply.startswith("DONE"):
                return

    def close(self):
        self.process.stdin.close()
        try:
            code = self.process.wait(timeout=10)
            assert code == 0, (code, self.errors)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            for reader in self.readers:
                reader.join(timeout=5)
            self.process.stdout.close()
            self.process.stderr.close()


def pull(worker, source, root, length, chain="areverse", start=0.0, durations=(0.25, 1.5, 3.25)):
    began = time.perf_counter()
    client = Worker(worker)
    actual = array.array("h")
    first_ms = None
    try:
        at = 0.0
        for index, duration in enumerate(durations):
            output = root / f"pull-{index}.wav"
            frames = round(duration * 48000)
            client.command(f"PLAYWAVE {wire(output)} {frames}")
            client.command(f"AUDIOSTREAM {wire(source)} {start} {duration} 0 1 0 0 {length} {at} {chain} 1 {length-at} {frames}")
            client.command(f"WAVECLOSE {wire(output)}")
            if first_ms is None:
                first_ms = (time.perf_counter()-began)*1000
                peak = peak_memory(client.process.pid)
            actual.extend(pcm(output))
            at += duration
        assert len(actual) == round(sum(durations) * 48000) * 2
        peak = max(peak, peak_memory(client.process.pid))
        return actual, {"seconds": length, "first_pcm_ms": first_ms, "peak_worker_bytes": peak}
    finally:
        client.close()


def reverse_tail(source, end, seconds=5):
    with wave.open(str(source), "rb") as wav:
        assert wav.getframerate() == 48000 and wav.getnchannels() == 2
        wav.setpos(round((end-seconds) * 48000))
        forward = array.array("h")
        forward.frombytes(wav.readframes(round(seconds * 48000)))
    result = array.array("h")
    for at in range(len(forward)-2, -1, -2):
        result.extend(forward[at:at+2])
    return result


def whole(worker, source, output, start, duration, chain):
    commands = (f"WAVE {wire(output)} 5\nAUDIO {wire(source)} {start} {duration} 0 1 0 0 600 0 {chain}\nWAVECLOSE {wire(output)}\n")
    result = subprocess.run([str(worker), "--serve"], input=commands, text=True, encoding="utf-8",
        errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0 and "ERR" not in result.stdout, (result.returncode, result.stdout, result.stderr[-2000:])
    return pcm(output)


def compare(actual, expected, label, maximum_allowed=2, mean_allowed=0.1):
    assert len(actual) == len(expected), (label, len(actual), len(expected))
    differences = [abs(a-b) for a,b in zip(actual, expected)]
    maximum, mean = max(differences), sum(differences)/len(differences)
    assert maximum <= maximum_allowed and mean < mean_allowed, (label, maximum, mean)
    print(f"{label}: max {maximum} PCM units, mean {mean:.6f}", flush=True)


def reference(ffmpeg, source, start, duration, seconds=5):
    # Independent complete resample/reverse pass, with the worker's documented
    # signed-16 scaling. It catches a one-sample shift at a fractional native trim.
    chain = (f"atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS,"
             "aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo,"
             f"areverse,atrim=duration={seconds}")
    result = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(source),
        "-af", chain, "-f", "f32le", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr[-2000:]
    values = array.array("f")
    values.frombytes(result.stdout)
    def signed16(value):
        scaled = max(-1, min(1, value)) * 32767
        return int(math.copysign(math.floor(abs(scaled)+0.5), scaled))
    return array.array("h", (signed16(value) for value in values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--baseline-worker", type=pathlib.Path)
    parser.add_argument("--media", type=pathlib.Path, help="also check the first twelve seconds of supplied compressed media")
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("this gate measures the native Windows worker")
    worker = args.worker.resolve()
    rows = []
    with tempfile.TemporaryDirectory(prefix="genesis-audio-reverse-") as directory:
        root = pathlib.Path(directory)
        source = root / "long reverse 日本語 %20, clip.wav"
        result = subprocess.run([str(worker.parent / "ffmpeg.exe"), "-nostdin", "-y", "-v", "error",
            "-f", "lavfi", "-i", "aevalsrc=0.2*sin(2*PI*(233.7*t+0.04*t*t))|0.18*sin(2*PI*(881.3*t+0.02*t*t)):s=48000:d=600",
            "-c:a", "pcm_s16le", str(source)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr[-2000:]
        for length in (60, 600):
            actual, row = pull(worker, source, root, length)
            compare(actual, reverse_tail(source, length), f"{length}s reverse, three unequal pulls")
            rows.append(row)
            print(f"{length}s: first PCM {row['first_pcm_ms']:.2f} ms; peak worker {row['peak_worker_bytes']/1024**2:.2f} MiB", flush=True)
        assert rows[1]["peak_worker_bytes"]-rows[0]["peak_worker_bytes"] < 64 * 1024**2, "reverse memory grew with clip duration"
        assert rows[1]["first_pcm_ms"] < 2500, "reverse startup exceeded the native acceptance bound"
        for chain in ("areverse,aecho=0.8:0.9:240:0.5", "areverse,atempo=2,aecho=0.8:0.9:240:0.5"):
            actual, _ = pull(worker, source, root, 600, chain)
            expected = whole(worker, source, root / "whole.wav", 588, 12, chain)
            compare(actual, expected, chain + " retains filter history")
        resampled = root / "fractional 44100.wav"
        subprocess.run([str(worker.parent / "ffmpeg.exe"), "-nostdin", "-y", "-v", "error",
            "-i", str(source), "-t", "17", "-ar", "44100", "-c:a", "pcm_s16le", str(resampled)],
            check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        for start, length in ((0.1, 11.7), (0.1234567, 11.704208333333), (0.001234567, 11.111111)):
            actual, _ = pull(worker, resampled, root, length, start=start)
            expected = reference(worker.parent / "ffmpeg.exe", resampled, start, length)
            compare(actual, expected, f"44100 Hz native trim {start}+{length}")
        compressed = root / "compressed AAC.m4a"
        subprocess.run([str(worker.parent / "ffmpeg.exe"), "-nostdin", "-y", "-v", "error",
            "-i", str(resampled), "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(compressed)],
            check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        actual, _ = pull(worker, compressed, root, 12, durations=(0.25, 3.5, 8.25))
        expected = reference(worker.parent / "ffmpeg.exe", compressed, 0, 12, seconds=12)
        compare(actual, expected, "Complete twelve-second AAC reverse")
        if args.media:
            supplied = args.media.resolve()
            actual, _ = pull(worker, supplied, root, 12, durations=(0.25, 3.5, 8.25))
            expected = reference(worker.parent / "ffmpeg.exe", supplied, 0, 12, seconds=12)
            compare(actual, expected, "Supplied compressed media reverse")
        if args.baseline_worker:
            baseline = []
            for length in (60, 600):
                actual, row = pull(args.baseline_worker.resolve(), source, root, length)
                compare(actual, reverse_tail(source, length), f"baseline {length}s reverse")
                baseline.append(row)
                print(f"Baseline {length}s: first PCM {row['first_pcm_ms']:.2f} ms; peak worker {row['peak_worker_bytes']/1024**2:.2f} MiB", flush=True)
            rows.extend({**row, "baseline": True} for row in baseline)
    if args.report:
        args.report.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("Native long reverse audio: bounded memory/startup, exact PCM and continuous delay/rate history passed", flush=True)


if __name__ == "__main__":
    main()
