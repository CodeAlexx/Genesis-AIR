"""Independent synthetic clock/presentation cases for the native timing reader."""
import csv
from pathlib import Path
import tempfile
import unittest

from window_timing import analyze


def fixture():
    result = []
    for frame in range(360):
        start = 1_000_000_000+round(frame*1e9/60)
        row = dict(loop_begin_ns=start, present_begin_ns=start+1_000_000,
                   present_end_ns=start+5_000_000, loop_end_ns=start+5_200_000,
                   signature_ns=20_000, paint_ns=500_000, present_ns=4_000_000,
                   wait_ns=200_000, program_shown=frame, source_shown=0,
                   heard_before=frame, heard_after=frame, samples_before=frame*800,
                   samples_after=frame*800+192, queued_before=2, queued_after=2,
                   audio_origin=0, fps=60, source_mode=0, playing=1,
                   clock_ok=1, present_ok=1, document_revision=1, media_revision=0,
                   width=1600, height=980, prepared_frames=2, snapshot_generation=frame+1,
                   audio_cache_rebuilds=1, strip_requests=1, input_events=0,
                   diagnostic_previous_ns=10_000)
        result.append(row)
    return result


class WindowTimingTests(unittest.TestCase):
    def report(self, rows):
        with tempfile.TemporaryDirectory(prefix="genesis-window-reader-") as temporary:
            path = Path(temporary)/"native.tsv"
            with path.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys(), delimiter="\t")
                writer.writeheader()
                writer.writerows(rows)
            return analyze(path)

    def test_poll_loops_do_not_split_real_playback(self):
        rows = []
        for row in fixture():
            rows.append(row)
            poll = dict(row, present_ok=0, clock_ok=0, present_begin_ns=0,
                        present_end_ns=0, present_ns=0)
            rows.append(poll)
        report = self.report(rows)
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["runs"]), 1)
        measured = report["runs"][0]
        self.assertAlmostEqual(measured["pictures_per_second"], 60, places=5)
        self.assertLess(abs(measured["device_interval_drift_ms"]), .001)
        self.assertEqual(measured["skipped_frame_positions"], 0)
        self.assertEqual(measured["native_present_ms"]["median"], 4)

    def test_missing_pictures_are_not_counted_as_sixty_fps(self):
        rows = fixture()
        for row in rows:
            if row["program_shown"] % 3 == 1:
                row["program_shown"] -= 1
        report = self.report(rows)
        self.assertEqual(report["errors"], [])
        measured = report["runs"][0]
        self.assertGreater(measured["skipped_frame_positions"], 90)
        self.assertLess(measured["pictures_per_second"], 41)
        self.assertEqual(measured["maximum_frame_jump"], 2)

    def test_future_picture_and_invalid_presentation_are_reported(self):
        rows = fixture()
        rows[80]["program_shown"] += 1
        rows[90]["present_ns"] += 1
        rows[100]["samples_after"] = rows[100]["samples_before"]-1
        report = self.report(rows)
        self.assertEqual(len(report["errors"]), 3)


if __name__ == "__main__":
    unittest.main()
