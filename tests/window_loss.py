"""Attribute native picture omissions using the optional 39-column profile.

Request IDs are mapped to their recorded frame positions, never inferred from
numeric gaps. Strip requests use a separate lane and are not part of this map.
This diagnoses application handoff; it does not measure display photon timing.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import unittest


REQUIRED = (
    "loop_begin_ns", "present_end_ns", "program_shown", "source_shown",
    "playing", "clock_ok", "present_ok", "fps", "source_mode", "audio_origin",
    "document_revision", "media_revision", "samples_before", "prepared_frames",
    "prepared_first_frame", "prepared_last_frame", "last_requested_frame",
    "in_flight_request", "received_request", "completed_packets", "overwritten_packets",
)
IDENTITY = ("source_mode", "audio_origin", "fps", "document_revision", "media_revision")


def shown(row):
    return row["source_shown"] if row["source_mode"] else row["program_shown"]


def stored(row):
    return tuple(row[name] for name in ("prepared_first_frame", "prepared_last_frame")
                 if row[name] >= 0)


def analyze_rows(rows, warmup=1.0):
    if not rows or not all(name in rows[0] for name in REQUIRED):
        raise ValueError("Loss attribution requires the optional 39-column native profile")
    requests = {}
    receipts = defaultdict(list)
    mapping_errors = []
    for index, row in enumerate(rows):
        request = row["in_flight_request"]
        if request:
            frame = row["last_requested_frame"]
            if request not in requests:
                requests[request] = dict(frame=frame, row=index,
                                         source_mode=row["source_mode"])
            elif requests[request]["frame"] != frame:
                mapping_errors.append(f"row {index}: request {request} changed frame position")
        receipt = row["received_request"]
        if receipt and (index == 0 or receipt != rows[index-1]["received_request"]):
            if receipt not in requests:
                mapping_errors.append(f"row {index}: receipt {receipt} has no recorded request")
            else:
                receipts[receipt].append(index)

    # Use the timing reader's playing/clock/presentation epoch boundaries.
    runs, current, previous = [], [], None
    for index, row in enumerate(rows):
        if not row["playing"]:
            if current:
                runs.append(current)
            current, previous = [], None
            continue
        if not (row["clock_ok"] and row["present_ok"] and row["fps"] > 0):
            continue
        if previous is not None and (
            any(row[key] != previous[key] for key in IDENTITY)
            or row["samples_before"] < previous["samples_before"]
            or shown(row) < shown(previous)
        ):
            runs.append(current)
            current = []
        current.append(index)
        previous = row
    if current:
        runs.append(current)

    reports = []
    for run in runs:
        began = rows[run[0]]["present_end_ns"]
        selected = [i for i in run if rows[i]["present_end_ns"]-began >= warmup*1e9]
        if len(selected) < 2:
            continue
        first, last = selected[0], selected[-1]
        visible = {shown(rows[i]) for i in selected}
        low, high = min(visible), max(visible)
        by_frame = defaultdict(list)
        delivered = defaultdict(list)
        # Map requests across the full playing epoch, including preparation
        # before the warm boundary. A paused preceding request is relevant only
        # if its completion falls inside this epoch and its frame is measured.
        for request, value in requests.items():
            positions = receipts[request]
            if not (run[0] <= value["row"] <= run[-1]
                    or any(run[0] <= i <= run[-1] for i in positions)):
                continue
            if value["source_mode"] != rows[first]["source_mode"]:
                continue
            by_frame[value["frame"]].append(request)
            for index in positions:
                if run[0] <= index <= run[-1]:
                    delivered[value["frame"]].append((request, index))

        stored_positions = {frame for i in range(run[0], run[-1]+1)
                            for frame in stored(rows[i])}
        classes, omissions = Counter(), []
        for frame in range(low, high+1):
            if frame in visible:
                continue
            candidates = delivered[frame]
            if not candidates:
                category = "requested_not_delivered" if by_frame[frame] else "never_requested"
            else:
                # Native main receives before take_due. A full previous queue
                # refuses this future frame even if due pictures are released
                # later in the same iteration, changing the recorded slots.
                capacity = any(
                    i > 0 and rows[i-1]["prepared_frames"] == 2
                    and frame not in stored(rows[i]) and shown(rows[i]) < frame
                    for _, i in candidates)
                was_stored = frame in stored_positions
                if was_stored:
                    category = "stored_then_not_presented"
                elif capacity:
                    category = "full_before_receive_not_stored"
                else:
                    category = "delivered_due_superseded_or_unstored"
            classes[category] += 1
            omissions.append(dict(frame=frame, category=category,
                                  request_ids=by_frame[frame],
                                  receipt_rows=[i for _, i in candidates]))

        completed = rows[last]["completed_packets"]-rows[first]["completed_packets"]
        overwritten = rows[last]["overwritten_packets"]-rows[first]["overwritten_packets"]
        observed = sum(first < i <= last for positions in receipts.values() for i in positions)
        residual = completed-observed-overwritten
        reports.append(dict(
            first_row=first, last_row=last, source_mode=rows[first]["source_mode"],
            first_frame=low, last_frame=high, presentations=len(selected),
            unique_pictures=len(visible), skipped_frame_positions=len(omissions),
            loss_classes=dict(classes), omissions=omissions,
            counter_conservation=dict(completed=completed, observed_receipts=observed,
                                      overwritten=overwritten, other_unreceived=residual),
            full_queue_with_outstanding_rows=sum(
                rows[i]["prepared_frames"] == 2 and rows[i]["in_flight_request"] != 0
                for i in range(first, last+1)),
        ))
    return dict(scope="Native request/receipt/prepared-picture omission attribution; no physical display timing",
                warmup_seconds=warmup, rows=len(rows), runs=reports,
                mapping_errors=mapping_errors,
                limitations=["Request-to-receipt loop stamps cannot isolate decoder cost.",
                             "Requested but undelivered frames may include command coalescing or packet overwrite; consult counters.",
                             "Receipt rows are zero-based data-row indices, excluding the TSV header.",
                             "A nonzero conservation residual needs epoch/error diagnostics before attribution."])


def analyze(path, warmup=1.0):
    raw = path.read_bytes()
    rows = [{name: float(value) if name == "fps" else int(value)
             for name, value in row.items()}
            for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter="\t")]
    result = analyze_rows(rows, warmup)
    result["profile_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


class LossReaderTests(unittest.TestCase):
    def fixture(self):
        def row(index, frame, present=0, first=-1, last=-1, request=0,
                requested=-1, receipt=0, completed=0):
            value = {key: 0 for key in REQUIRED}
            value.update(loop_begin_ns=index*1_000_000, present_end_ns=index*1_000_000,
                         program_shown=frame, source_shown=frame+100,
                         playing=1, clock_ok=present, present_ok=present, fps=60.0,
                         samples_before=index*800, prepared_first_frame=first,
                         prepared_last_frame=last, prepared_frames=int(first >= 0)+int(last >= 0),
                         in_flight_request=request, last_requested_frame=requested,
                         received_request=receipt, completed_packets=completed)
            return value
        return [row(0, 0, 1, request=100, requested=3),
                row(1, 0, first=2, last=4, request=101, requested=5),
                row(2, 0, first=2, last=4, receipt=101, completed=1),
                row(3, 2, 1, first=4, request=102, requested=7, receipt=101, completed=1),
                row(4, 2, first=4, last=7, receipt=102, completed=2),
                row(5, 4, 1, first=7, receipt=102, completed=2),
                row(6, 6, 1, first=7, last=8, receipt=102, completed=2),
                row(7, 8, 1, receipt=102, completed=2)]

    def test_exact_categories_without_id_gap_inference(self):
        result = analyze_rows(self.fixture(), 0)
        self.assertEqual(result["mapping_errors"], [])
        run = result["runs"][0]
        self.assertEqual(run["skipped_frame_positions"], 4)
        self.assertEqual(run["loss_classes"], dict(never_requested=1,
            requested_not_delivered=1, full_before_receive_not_stored=1,
            stored_then_not_presented=1))
        self.assertEqual(run["counter_conservation"], dict(completed=2,
            observed_receipts=2, overwritten=0, other_unreceived=0))

    def test_overwrite_conservation_and_source_positions(self):
        rows = self.fixture()
        for row in rows:
            row["source_mode"] = 1
            for key in ("prepared_first_frame", "prepared_last_frame", "last_requested_frame"):
                if row[key] >= 0:
                    row[key] += 100
            if row["completed_packets"]:
                row["completed_packets"] += 1
                row["overwritten_packets"] = 1
        run = analyze_rows(rows, 0)["runs"][0]
        self.assertEqual([value["frame"] for value in run["omissions"]], [101, 103, 105, 107])
        self.assertEqual(run["counter_conservation"], dict(completed=3,
            observed_receipts=2, overwritten=1, other_unreceived=0))

    def test_capacity_refusal_precedes_due_release_in_same_loop(self):
        rows = self.fixture()
        rows[2].update(program_shown=2, clock_ok=1, present_ok=1,
                       prepared_first_frame=4, prepared_last_frame=-1, prepared_frames=1)
        run = analyze_rows(rows, 0)["runs"][0]
        self.assertEqual(run["loss_classes"]["full_before_receive_not_stored"], 1)

    def test_missing_schema_and_unmapped_receipt_are_not_silent(self):
        with self.assertRaises(ValueError):
            analyze_rows([{}], 0)
        rows = self.fixture()
        rows[2]["received_request"] = 999
        self.assertTrue(analyze_rows(rows, 0)["mapping_errors"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, nargs="?")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--warmup", type=float, default=1.0)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return int(not unittest.TextTestRunner().run(
            unittest.defaultTestLoader.loadTestsFromTestCase(LossReaderTests)).wasSuccessful())
    if args.profile is None or args.warmup < 0:
        parser.error("a profile and a nonnegative warmup are required")
    result = analyze(args.profile, args.warmup)
    encoded = json.dumps(result, indent=2)
    if args.report:
        args.report.write_text(encoded+"\n", encoding="utf-8")
    print(encoded)
    return int(bool(result["mapping_errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
