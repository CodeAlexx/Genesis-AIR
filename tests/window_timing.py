"""Analyze opt-in run_window timing, including the actual native presenter.

This observes application handoff/EndDraw and the native audio sample clock;
physical speaker latency and the monitor's photon timing remain outside scope.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    if not values:
        return None
    ordered = sorted(values)
    return dict(count=len(values), median=statistics.median(values),
                p95=ordered[min(len(ordered)-1, math.ceil(len(ordered)*.95)-1)],
                maximum=ordered[-1])


def analyze(path, sample_rate=48000, warmup=1.0):
    with path.open(encoding="utf-8-sig", newline="") as source:
        records = list(csv.DictReader(source, delimiter="\t"))
    assert records, "Window profile has no rows"
    rows = [{name: float(value) if name == "fps" else int(value)
             for name, value in record.items()} for record in records]
    required = ("loop_begin_ns", "loop_end_ns", "present_begin_ns", "present_end_ns",
                "present_ns", "program_shown", "source_shown", "heard_before", "heard_after",
                "samples_before", "samples_after", "queued_before", "queued_after",
                "audio_origin", "fps", "source_mode", "playing", "clock_ok", "present_ok",
                "document_revision", "media_revision", "prepared_frames")
    assert all(name in rows[0] for name in required), "Window profile schema is incomplete"
    errors = []
    active = []
    runs = []
    current = []
    previous = None
    for index, row in enumerate(rows):
        if row["loop_end_ns"] < row["loop_begin_ns"]:
            errors.append(f"row {index}: backward loop timestamp")
        if row["present_ok"]:
            if row["present_end_ns"] < row["present_begin_ns"]:
                errors.append(f"row {index}: backward presentation timestamp")
            if row["present_ns"] != row["present_end_ns"]-row["present_begin_ns"]:
                errors.append(f"row {index}: inconsistent native presentation duration")
        valid = bool(row["playing"] and row["clock_ok"] and row["present_ok"] and row["fps"] > 0)
        if not valid:
            # Poll-only loops between pictures belong to the same playing run.
            if not row["playing"]:
                if current:
                    runs.append(current)
                    current = []
                previous = None
            continue
        active.append(row)
        shown = row["source_shown"] if row["source_mode"] else row["program_shown"]
        if shown > row["heard_before"]:
            errors.append(f"row {index}: picture {shown} precedes heard frame {row['heard_before']}")
        if row["prepared_frames"] > 2:
            errors.append(f"row {index}: more than two prepared pictures")
        if row["samples_after"] < row["samples_before"]:
            errors.append(f"row {index}: device clock moved backward during presentation")
        identity = tuple(row[name] for name in ("source_mode", "audio_origin", "fps", "document_revision", "media_revision"))
        if previous is not None:
            previous_identity = tuple(previous[name] for name in ("source_mode", "audio_origin", "fps", "document_revision", "media_revision"))
            if identity != previous_identity or row["samples_before"] < previous["samples_before"]:
                runs.append(current)
                current = []
        current.append(row)
        previous = row
    if current:
        runs.append(current)
    summaries = []
    for run in runs:
        began = run[0]["present_end_ns"]
        selected = [row for row in run if row["present_end_ns"]-began >= warmup*1e9]
        if len(selected) < 2:
            continue
        changed = []
        previous_frame = None
        for row in selected:
            frame = row["source_shown"] if row["source_mode"] else row["program_shown"]
            if frame != previous_frame:
                changed.append((row["present_end_ns"], frame))
            previous_frame = frame
        first, last = selected[0], selected[-1]
        duration = (last["present_begin_ns"]-first["present_begin_ns"])/1e9
        sample_duration = (last["samples_before"]-first["samples_before"])/sample_rate
        picture_duration = (changed[-1][0]-changed[0][0])/1e9 if len(changed) > 1 else 0
        gaps = [(b[0]-a[0])/1e6 for a, b in zip(changed, changed[1:])]
        frame_jumps = [b[1]-a[1] for a, b in zip(changed, changed[1:])]
        lateness = [(row["heard_after"]-(row["source_shown"] if row["source_mode"] else row["program_shown"]))*1000/row["fps"] for row in selected]
        summaries.append(dict(duration_seconds=duration, fps=first["fps"], source_mode=first["source_mode"],
                              observations=len(selected), changed_pictures=len(changed),
                              pictures_per_second=(len(changed)-1)/picture_duration if picture_duration else 0,
                              skipped_frame_positions=sum(max(0, jump-1) for jump in frame_jumps),
                              maximum_frame_jump=max(frame_jumps, default=0),
                              picture_gap_ms=distribution(gaps), picture_lateness_after_present_ms=distribution(lateness),
                              device_interval_drift_ms=(sample_duration-duration)*1000,
                              observed_drained_queue_rows=sum(row["queued_before"] == 0 or row["queued_after"] == 0 for row in selected),
                              native_present_ms=distribution([row["present_ns"]/1e6 for row in selected]),
                              paint_ms=distribution([row["paint_ns"]/1e6 for row in selected]),
                              wait_ms=distribution([row["wait_ns"]/1e6 for row in selected]),
                              signature_ms=distribution([row["signature_ns"]/1e6 for row in selected])))
    return dict(scope="Actual native editor loop, presenter and audio device clock; physical speaker/display latency excluded",
                report=str(path.resolve()), rows=len(rows), active_presentations=len(active),
                warmup_seconds=warmup, runs=summaries, errors=errors,
                phases_ms={name: distribution([row[name]/1e6 for row in rows]) for name in
                           ("signature_ns", "paint_ns", "present_ns", "wait_ns", "diagnostic_previous_ns")},
                audio_cache_rebuilds=max((row["audio_cache_rebuilds"] for row in rows), default=0),
                strip_requests=max((row["strip_requests"] for row in rows), default=0),
                transport_packets=(dict(
                    completed=max(row["completed_packets"] for row in rows),
                    overwritten_before_consumption=max(row["overwritten_packets"] for row in rows),
                    active_future_reservation_rows=sum(
                        row["in_flight_request"] != 0 and
                        row["last_requested_frame"] >= row["heard_before"] for row in active),
                    active_late_reservation_rows=sum(
                        row["in_flight_request"] != 0 and
                        row["last_requested_frame"] < row["heard_before"] for row in active))
                    if "completed_packets" in rows[0] else None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--warmup", type=float, default=1.0)
    parser.add_argument("--require-active", action="store_true")
    parser.add_argument("--minimum-picture-rate", type=float)
    args = parser.parse_args()
    assert args.sample_rate > 0 and args.warmup >= 0
    result = analyze(args.profile, args.sample_rate, args.warmup)
    if args.require_active and not result["runs"]:
        result["errors"].append("No measurable native playing interval after warmup")
    if args.minimum_picture_rate is not None:
        if not result["runs"] or any(run["pictures_per_second"] < args.minimum_picture_rate for run in result["runs"]):
            result["errors"].append("Native picture delivery is below the requested minimum")
    encoded = json.dumps(result, indent=2)
    if args.report:
        args.report.write_text(encoded+"\n", encoding="utf-8")
    print(encoded)
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
