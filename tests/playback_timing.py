"""Real native audio clock, async pictures and fractional-rate long-run identity.

The generated fixture covers the requested duration. Native presentation and
physical speaker latency are excluded; queued-buffer polling can only establish
that no underrun was observed, rather than detecting every sub-poll event.
"""

from media_runtime import tool as _media_tool
import argparse
import csv
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import tempfile

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run(argv, env=None, timeout=120):
    done = subprocess.run(list(map(str, argv)), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, creationflags=FLAGS)
    assert done.returncode == 0, (done.returncode, done.stdout[-4000:], done.stderr[-4000:])
    return done


def percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values)-1, math.floor((len(values)-1)*fraction))]


def fixture_color(frame):
    # Base-24 digits provide 13,824 distinct RGB identities, with eight code
    # values between identities so the two-value decode tolerance cannot alias.
    assert 0 <= frame < 24**3
    return tuple(32+((frame//divisor) % 24)*8 for divisor in (1, 24, 24**2))


def measure(binary, worker, project, root, seconds, legacy, identity, sleep_poll=False):
    label = ("legacy" if legacy else "prepared") + ("-poll" if sleep_poll else "")
    report = root / f"{label}.tsv"
    env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / label))
    env.pop("GENESIS_FAKE_PROVIDER", None)
    run([binary, "profile-playback", report, project, seconds] + (["--legacy"] if legacy else []) + (["--poll"] if sleep_poll else []),
        env, seconds+90)
    with report.open(encoding="utf-8", newline="") as file:
        rows = [{key: int(value) for key, value in row.items()} for row in csv.DictReader(file, delimiter="\t")]
    document = json.loads(project.read_text(encoding="utf-8"))
    fps = next(s["fps"] for s in document["sequences"] if s["id"] == document["active"])
    assert len(rows) > seconds*15, (label, "too few observations", len(rows))
    assert rows[-1]["samples"] >= (seconds-0.15)*48000, rows[-1]
    assert all(b["samples"] >= a["samples"] for a, b in zip(rows, rows[1:])), "audio clock reversed"
    assert all(b["shown_frame"] >= a["shown_frame"] for a, b in zip(rows, rows[1:])), "picture reversed without a seek"
    assert all(row["shown_frame"] == row["timeline_frame"] for row in rows), "timeline cursor drifted from displayed picture"
    assert all(row["shown_frame"] <= row["heard_frame"] for row in rows), "future picture presented early"
    assert all(row["heard_frame"] == math.floor(row["samples"]*fps/48000) for row in rows), "audio/frame conversion differed"
    assert all(row["prepared"] <= 2 for row in rows), "picture queue exceeded its bound"
    assert not any(row["queued"] == 0 for row in rows if row["samples"] > 4800), "audio ran out during measurement"
    changed = [row for n, row in enumerate(rows) if n == 0 or row["shown_frame"] != rows[n-1]["shown_frame"]]
    assert len(changed) > seconds*8, (label, "picture froze", len(changed))
    if identity:
        source = document["sources"][0]
        clip = document["clips"][0]
        for row in rows:
            source_frame = math.floor((clip["source_in"] + row["shown_frame"])*source["fps"]/fps)
            expected = fixture_color(source_frame)
            actual = tuple(row[channel] for channel in ("r", "g", "b"))
            assert max(abs(a-b) for a, b in zip(actual, expected)) <= 2, (row, source_frame, expected)
    # Ignore the initial half-second of cold prefetch when describing steady timing.
    steady = [row for row in rows if row["samples"] >= 24000]
    lag = [(row["samples"]/48000-row["shown_frame"]/fps)*1000 for row in steady]
    # Compare independent monotonic elapsed time with the real device cursor.
    # The initial offset includes driver startup and is not drift.
    timed = [row for row in rows if row["samples"] >= 48000]
    first, last = timed[0], timed[-1]
    elapsed = (last["wall_ns"] - first["wall_ns"])/1e9
    drift_ms = ((last["samples"]-first["samples"])/48000-elapsed)*1000
    phases_ms = [(row["samples"]-first["samples"])/48
                 -(row["wall_ns"]-first["wall_ns"])/1e6 for row in timed]
    assert abs(drift_ms) < 75, (label, "device cursor diverged from monotonic time", drift_ms)
    assert max(phases_ms)-min(phases_ms) < 75, (label, "device clock phase discontinuity", min(phases_ms), max(phases_ms))
    picture_gaps_ms = [(b["wall_ns"]-a["wall_ns"])/1e6 for a, b in zip(changed, changed[1:])
                       if a["samples"] >= 48000]
    if identity:
        # A global average could hide a frozen interval in a long measurement.
        assert max(picture_gaps_ms) < 250, (label, "lossless fixture picture froze", max(picture_gaps_ms))
        assert max(lag) < 250, (label, "lossless fixture picture fell behind", max(lag))
    # Production audio pulls floor(fps*5) timeline frames, not exactly 5 seconds
    # at a fractional sequence rate. Check all observed crossings of that span.
    audio_span = math.floor(fps*5)
    boundaries = [round(frame*48000/fps) for frame in range(audio_span, math.floor(seconds*fps), audio_span)]
    crossed = sum(rows[0]["samples"] < boundary <= rows[-1]["samples"] for boundary in boundaries)
    assert crossed == len(boundaries), (label, "audio buffer boundaries were not reached", crossed, len(boundaries))
    phases = {name: [] for name in ("snapshot_ns", "source_ns", "plan_ns", "program_ns", "publish_ns", "coalesce_ns")}
    seen = set()
    for row in steady:
        if row["ready_id"] not in seen:
            seen.add(row["ready_id"])
            for name in phases:
                phases[name].append(row[name]/1000000)
    paints = [row["paint_ns"]/1000000 for row in steady if row["paint_ns"]]
    waits = [row["wait_ns"]/1000000 for row in steady]
    provider = root / label / "playback-profile" / "provider-profile.tsv"
    provider_phases = None
    if provider.exists():
        with provider.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            assert reader.fieldnames == ["call", "exchange_ns", "input_ns", "read_ns", "copy_ns"], reader.fieldnames
            calls = [{key: int(value) for key, value in row.items()} for row in reader]
        assert len(calls) > 3 and all(value >= 0 for row in calls for value in row.values())
        assert all(b["call"] > a["call"] for a, b in zip(calls, calls[1:])), "provider call identity reversed"
        provider_phases = {name: {"median": statistics.median(row[name]/1000000 for row in calls[3:]),
                                  "p95": percentile([row[name]/1000000 for row in calls[3:]], .95)}
                           for name in reader.fieldnames[1:]}
    return {"mode": label, "wait": "sleep_poll" if sleep_poll else "channel_event", "seconds": seconds, "fps": fps, "observations": len(rows),
            "presented_pictures": len(changed), "lag_ms": {
                "median": statistics.median(lag), "p90": percentile(lag, .9),
                "p95": percentile(lag, .95), "maximum": max(lag)},
            "peak_prepared": max(row["prepared"] for row in rows),
            "audio_underruns": 0, "early_pictures": 0, "pixel_checks": len(rows) if identity else 0,
            "device_clock": {"interval_seconds": elapsed, "interval_drift_ms": drift_ms,
                             "phase_range_ms": max(phases_ms)-min(phases_ms)},
            "audio_buffer_boundaries": crossed,
            "maximum_picture_gap_ms": max(picture_gaps_ms),
            "phase_ms": {name: {"median": statistics.median(values), "p95": percentile(values, .95)} for name, values in phases.items()},
            "paint_ms": {"median": statistics.median(paints), "p95": percentile(paints, .95)},
            "wait_ms": {"median": statistics.median(waits), "p95": percentile(waits, .95)},
            "timer_period_ms": rows[-1]["timer_period_ms"],
            "provider_ms": provider_phases,
            "raw_report": str(report)}


def fixture(binary, worker, root, seconds=8):
    ffmpeg = _media_tool(worker, "ffmpeg")
    # Upscale uniform one-pixel lossless frames, avoiding gigabytes of raw video.
    # Unlike a repeated short clip, each frame throughout three minutes has its
    # own identity, so an old picture cannot alias one from a later loop.
    duration = max(12.012, seconds+2.012)
    frames = b"".join(bytes(fixture_color(frame)) for frame in range(math.ceil(duration*24000/1001)))
    raw = root / "identity.rgb"
    raw.write_bytes(frames)
    video = root / "frames 日本語 %20.mp4"
    run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", "1x1", "-framerate", "24000/1001", "-i", raw,
         "-f", "lavfi", "-i", "sine=frequency=431:sample_rate=48000",
         "-map", "0:v", "-map", "1:a", "-t", str(duration), "-vf", "scale=320:180:flags=neighbor",
         "-c:v", "libx264rgb", "-crf", "0", "-preset", "fast", "-bf", "3", "-g", "24", "-c:a", "aac", video])
    # Every full-size frame is uniform. Cropping a single source pixel avoids a
    # multi-gigabyte raw-video capture while independently checking the entire
    # sequence and its decoded frame order.
    decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(video),
                              "-an", "-vf", "crop=1:1:0:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                             capture_output=True, timeout=120, creationflags=FLAGS)
    count = len(decoded.stdout)//3
    expected = b"".join(bytes(fixture_color(frame)) for frame in range(count))
    assert decoded.returncode == 0 and count > (seconds+1)*24000/1001 and decoded.stdout == expected, "independent lossless decode differed"
    project = root / "fractional.air"
    env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "probe"))
    env.pop("GENESIS_FAKE_PROVIDER", None)
    run([binary, "probe", video, root / "probe.png", project], env)
    document = json.loads(project.read_text(encoding="utf-8"))
    sequence = document["sequences"][0]
    sequence.update(fps=30000/1001, width=320, height=180)
    document["clips"][0]["length"] = math.floor((seconds+1)*30000/1001) if seconds > 8 else 360
    project.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return project


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--seconds", type=int, default=8)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument("--poll", action="store_true", help="reproduce the earlier sleep/poll diagnostic")
    args = parser.parse_args()
    assert 1 <= args.pairs <= 5
    assert 2 <= args.seconds <= 180, "measurement duration must be 2..180 seconds"
    binary, worker = args.binary.resolve(), args.worker.resolve()
    report = args.report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    # Keep raw timing evidence alongside the summary; generated media stays temporary.
    evidence = report.parent / (report.stem + "-raw")
    evidence.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="genesis-playback-") as temporary:
        project = args.project.resolve() if args.project else fixture(binary, worker, Path(temporary), args.seconds)
        for n in range(args.pairs):
            modes = [True, False] if args.compare else [False]
            if n % 2:
                modes.reverse()
            for legacy in modes:
                root = evidence / f"pair-{n}"
                root.mkdir(exist_ok=True)
                try:
                    result = measure(binary, worker, project, root, args.seconds, legacy, not args.project, args.poll)
                except Exception as error:
                    # Raw evidence already lives outside the temporary fixture.
                    # Collect the small coded failure markers before media cleanup.
                    diagnostics = {}
                    for item in root.rglob("*"):
                        if item.is_file() and item.name in {"errors.jsonl", "error.txt", "request.id", "ready.id"}:
                            diagnostics[str(item.relative_to(root))] = item.read_text(encoding="utf-8", errors="replace")[-65536:]
                    failed = dict(schema="genesis.playback-timing-failure", error=str(error),
                                  raw_evidence=str(root), seconds=args.seconds, diagnostics=diagnostics)
                    report.with_suffix(".failed.json").write_text(json.dumps(failed, indent=2), encoding="utf-8")
                    print(json.dumps(failed), flush=True)
                    raise
                results.append(result)
                print(json.dumps(result), flush=True)
    report.write_text(json.dumps({"schema": "genesis.playback-timing", "revision": 2,
                                 "scope": "silent native device + asynchronous decode/mix + ordinary 480x270 monitors + 1600x980 retained paint; native display and speaker latency excluded",
                                 "measurements": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
