#!/usr/bin/env python3
"""Measure real worker preview throughput and verify an exact rewind to frame zero.

Timing excludes the Windows canvas. --repeat-source reproduces the former request
pattern; it is useful for comparison, not a portable frame-rate acceptance gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from queue import Queue
from threading import Thread
from collections import deque
import statistics
import subprocess
from tempfile import TemporaryDirectory
import time


def wire(value):
    return str(value).replace("%", "%25").replace(" ", "%20")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repeat-source", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    # Read the application's authoritative neutral wire rather than maintaining
    # another collection of its 108 defaults in this diagnostic.
    source = (Path(__file__).resolve().parent.parent / "src/timeline_media.ai").read_text(encoding="utf-8")
    neutral = source.split("fn neutral()", 1)[1].split("\nfn source_path", 1)[0]
    fields = ["0"] * 108
    for index, value in re.findall(r'put\(values, (\d+), "([^"]+)"\)', neutral):
        fields[int(index)] = value
    for index in range(27, 33):
        fields[index] = "1"
    fields[0] = wire(args.source.resolve())
    with TemporaryDirectory(prefix="genesis-preview-timing-") as temporary:
        picture = Path(temporary) / "program.rgba"
        thumbnail = Path(temporary) / "source.rgba"
        process = subprocess.Popen([str(args.worker.resolve()), "--serve", "--size", "1280", "720"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)

        backends = set()
        diagnostics = deque(maxlen=8)
        replies = Queue()
        def receive():
            for line in process.stdout:
                replies.put(line)
            replies.put("")
        Thread(target=receive, daemon=True).start()
        def ask(command):
            process.stdin.write(command + "\n")
            process.stdin.flush()
            while True:
                line = replies.get(timeout=30)
                assert line and not line.startswith("ERR"), f"worker rejected {command.split()[0]}: {list(diagnostics)}"
                diagnostics.append(line.strip())
                if "OpenCL device:" in line or "Native D3D11 decode:" in line:
                    backends.add(line.strip())
                if "frame color_us" in line:
                    print(line.strip(), flush=True)
                if line.startswith("DONE"):
                    return

        elapsed = []
        try:
            first = None
            for index in range(34):
                started = time.perf_counter()
                if args.repeat_source or index == 0:
                    ask(f"THUMB {fields[0]} 0 480 270 {wire(thumbnail)}")
                fields[2] = str(index * 2)
                ask("PREVIEW " + " ".join(fields) + " " + wire(picture))
                if index == 0:
                    pixels = picture.read_bytes()
                    assert len(pixels) == 1280 * 720 * 4 and any(pixels[::4]), "empty program frame"
                    first = hashlib.sha256(pixels).hexdigest()
                if index >= 4:
                    elapsed.append(time.perf_counter() - started)
            fields[2] = "0"
            ask("PREVIEW " + " ".join(fields) + " " + wire(picture))
            assert hashlib.sha256(picture.read_bytes()).hexdigest() == first, "rewind changed or lost frame zero"
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
        report = {"samples": len(elapsed), "mean_ms": round(statistics.mean(elapsed) * 1000, 2),
                  "median_ms": round(statistics.median(elapsed) * 1000, 2),
                  "worker_frames_per_second": round(1 / statistics.mean(elapsed), 2),
                  "rewind_identical": True, "repeated_source": args.repeat_source, "backends": sorted(backends)}
        if args.report:
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
