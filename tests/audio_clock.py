"""Measure the real Windows audio clock across uneven silent PCM buffers and a gap.

No window is opened and the PCM is silent. This checks device timing, not the
end-to-end picture presentation or the physical speaker's latency.
"""
import argparse
import ctypes
import hashlib
import json
import pathlib
import statistics
import tempfile
import time
import wave


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=pathlib.Path, required=True)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    assert 5 <= args.seconds <= 600, "measurement duration must be 5..600 seconds"
    library = args.library.resolve()
    driver = ctypes.CDLL(str(library))
    request = driver.air_genesis_audio
    request.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    request.restype = ctypes.c_char_p
    def ask(operation, path=""):
        reply = request(operation.encode(), str(path).encode("utf-8")).decode("utf-8")
        assert not reply.startswith("[GA_"), reply
        return reply
    def position():
        started = time.perf_counter()
        value = tuple(map(int, ask("clock").split()))
        ended = time.perf_counter()
        assert len(value) == 2
        return (started + ended) / 2, value[0], value[1]
    observations, gap = [], []
    submitted = completions = stalls = 0
    try:
        with tempfile.TemporaryDirectory(prefix="genesis-native-clock-") as directory:
            root = pathlib.Path(directory)
            counts = (71003, 13007, 47011, 9601, 53003)
            waves = []
            for index, frames in enumerate(counts):
                path = root / f"clock {index} 日本語 %20.wav"
                with wave.open(str(path), "wb") as out:
                    out.setnchannels(2)
                    out.setsampwidth(2)
                    out.setframerate(48000)
                    out.writeframes(b"\0" * (frames * 4))
                waves.append(path)
            ask("start")
            def queue(index):
                nonlocal submitted
                ask("queue", waves[index % len(waves)])
                submitted += counts[index % len(counts)]
            for index in range(3):
                queue(index)
            index, previous, previous_pending = 3, 0, 3
            begin = time.perf_counter()
            deadline, progress = begin + args.seconds, begin + 10
            while time.perf_counter() < deadline:
                now, samples, pending = position()
                assert previous <= samples <= submitted, (previous, samples, submitted)
                assert 0 < pending <= 3, (samples, pending, "continuous queue drained")
                completions += max(0, previous_pending - pending)
                while pending < 3:
                    queue(index)
                    index += 1
                    pending += 1
                if observations and samples == previous:
                    stalls += 1
                observations.append((now - begin, samples, pending))
                previous, previous_pending = samples, pending
                if now >= progress:
                    print(f"Native clock: {now - begin:.0f}s, {completions} completed buffers, {samples} samples", flush=True)
                    progress += 10
                time.sleep(0.008)
            # Quantization/driver startup are excluded from the interval slope.
            steady = [sample for sample in observations if sample[0] >= 1]
            first, last = steady[0], steady[-1]
            interval = last[0] - first[0]
            drift_ms = ((last[1] - first[1]) / 48000 - interval) * 1000
            assert abs(drift_ms) < 75, (drift_ms, "hardware clock diverged from monotonic elapsed time")
            phases = [(samples - first[1]) / 48 - (now - first[0]) * 1000 for now, samples, _ in steady]
            assert max(phases) - min(phases) < 75, (min(phases), max(phases))
            # Stop replenishing, then check every sample has completed exactly.
            end = time.perf_counter() + 7
            while True:
                _, samples, pending = position()
                assert previous <= samples <= submitted
                previous = samples
                if pending == 0:
                    # TIME_MS drivers resolve 48 kHz positions to whole milliseconds.
                    assert submitted - samples < 48, (samples, submitted, "final device cursor missed PCM")
                    drained_shortfall = submitted - samples
                    break
                assert time.perf_counter() < end, "queued audio did not drain"
                time.sleep(0.008)
            for _ in range(20):
                _, samples, pending = position()
                gap.append((samples, pending))
                assert samples == previous and pending == 0, "empty queue advanced the media cursor"
                assert ask("levels") == "0.000000 0.000000", "silent drained queue retained meter output"
                time.sleep(0.01)
            queue(0)
            resume_begin = previous
            end = time.perf_counter() + 3
            while True:
                _, samples, pending = position()
                assert resume_begin <= samples <= submitted
                if pending == 0:
                    assert submitted - samples < 48
                    resumed_shortfall = submitted - samples
                    break
                assert time.perf_counter() < end
                time.sleep(0.008)
            ask("stop")
            assert request(b"clock", b"").decode().startswith("[GA_AUDIO_CLOSED]")
            ask("start")
            assert position()[1:] == (0, 0), "new transport retained old sample epochs"
            ask("stop")
    finally:
        request(b"stop", b"")
    report = dict(library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                  duration_seconds=round(interval, 3), poll_count=len(observations),
                  completed_buffers=completions, queued_sample_frames=submitted,
                  interval_drift_ms=round(drift_ms, 3),
                  phase_range_ms=round(max(phases) - min(phases), 3),
                  median_phase_ms=round(statistics.median(phases), 3),
                  unchanged_clock_polls=stalls, empty_queue_samples=gap[0][0],
                  drained_shortfall_samples=drained_shortfall,
                  resumed_shortfall_samples=resumed_shortfall,
                  resumed_within_one_ms=True, restart_zero=True)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
