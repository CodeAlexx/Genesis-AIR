"""Ordinary spatial-transition previews agree with independently decoded native masters.

The expected monitor is sampled from FFmpeg-decoded 16-bit FFV1, rather than a
second preview render. Flat wipe sources expose the fixed 36-sequence-pixel soft
edge; detailed slide/zoom sources expose coordinate rounding before fitting.
"""

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile

from PIL import Image
from large_preview import MONITOR, SHAPES, profile_picture, run
from media_runtime import tool
from preview_fit import fitted

KINDS = ("crossfade", "dissolve", "wipe_lr", "wipe_rl", "wipe_up", "wipe_down",
         "slide_lr", "zoom", "iris", "clock", "barn_door")
BASELINE_SHA256 = "d8cad5ec8cf0b2100134eaa9c13bd1f38c2292d780c0041d2dc2df32adab829c"


def baseline_picture(binary, project, scratch, report, env):
    # Only the immutable published 32b41d5 executable has this pre-session
    # mailbox contract. Candidates must use the authoritative session report.
    run([binary, "profile-preview", report, project, "1600", "980", "1", "--file-pixels"],
        dict(env, GENESIS_SCRATCH=str(scratch)))
    mailbox = scratch / "profile"
    generation = int((mailbox / "ready.id").read_text().strip())
    assert generation >= 4
    slot = generation % 2
    assert int((mailbox / f"frame{slot}.id").read_text().strip()) == generation
    assert tuple(map(int, (mailbox / f"size{slot}.rgba").read_text().split())) == MONITOR
    raw = (mailbox / f"program{slot}.rgba").read_bytes()
    assert len(raw) == MONITOR[0]*MONITOR[1]*4 and set(raw[3::4]) == {255}
    return Image.frombytes("RGBA", MONITOR, raw).convert("RGB")


def fixture(width, height, incoming, detailed):
    if not detailed:
        return Image.new("RGB", (width, height), (31, 47, 219) if incoming else (231, 39, 53))
    # Native periods and asymmetrical edges expose resampling/rounding of the
    # incoming picture at a different canvas scale. No compressed-video noise.
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            if incoming:
                row.extend((30 + (x // 37 % 2) * 150,
                            35 + (y // 53 % 2) * 140,
                            45 + (x // 83 % 3) * 60))
            else:
                row.extend((225, 40, 55))
        rows.append(row)
    return Image.frombytes("RGB", (width, height), b"".join(rows))


def diagnostics(scratch):
    result = {}
    if scratch.exists():
        for path in scratch.rglob("*"):
            if path.is_file() and path.suffix in (".txt", ".id", ".json", ".jsonl", ".air", ".log") and path.stat().st_size <= 65536:
                result[str(path.relative_to(scratch))] = path.read_text(encoding="utf-8", errors="replace")
    return result


def persistent_seam(root, shape, size, base, sources, binary, worker, client, wrapper, ffmpeg, env):
    width, height = size
    document = copy.deepcopy(base)
    first = document["clips"][0]
    document.update(filters=[], filter_params=[], filter_text_params=[], keys=[])
    document["sources"][0].update(path=str(sources[False, False]), has_audio=False)
    document["sources"].append(dict(document["sources"][0], id=90, path=str(sources[False, True])))
    # A single-frame pair is enough to exercise the seam. Empty surrounding
    # frames remain within the timeline because a last clip ends at frame7.
    document["clips"] = [dict(first, start=2, length=1, source_in=0),
                         dict(first, id=91, source=90, start=3, length=1, source_in=0),
                         dict(first, id=94, start=6, length=1, source_in=0)]
    document["names"].append("wipe_lr")
    document["transitions"] = [dict(id=92, owner=first["owner"], track=first["track"],
                                    center=3, duration=2, kind=len(document["names"]))]
    document["next_id"] = 95
    project = root / f"{shape}-stream.air"
    project.write_text(json.dumps(document), encoding="utf-8")
    scratch, trace = root / f"{shape}-stream", root / f"{shape}-worker-sizes.txt"
    current = dict(env, GENESIS_TEST_WORKER=str(worker), GENESIS_TEST_STARTS=str(root / f"{shape}-worker-starts.txt"),
                   GENESIS_TEST_CANVAS_TRACE=str(trace), PATH=str(ffmpeg.parent)+os.pathsep+env.get("PATH", ""))
    run([client, scratch, wrapper, project, "spatial-seam"], current)
    sizes = [tuple(map(int, line.split())) for line in trace.read_text(encoding="utf-16-le").splitlines()]
    fitted_size = (480, 270) if shape == "landscape" else (144, 256)
    assert sizes == [fitted_size, size, fitted_size, size, fitted_size], sizes
    receipts = list(csv.DictReader((scratch / "canvas.tsv").open(encoding="utf-8", newline=""), delimiter="\t"))
    frames = (1, 3, 4, 2, 3, 5, 1)
    assert len(receipts) == len(frames)
    master = root / f"{shape}-stream-master.mkv"
    run([binary, "export", master, project], dict(env, GENESIS_SCRATCH=str(root / f"{shape}-stream-export")))
    maximum = 0
    for index, (frame, receipt) in enumerate(zip(frames, receipts)):
        assert (int(receipt["generation"]), int(receipt["frame"]), int(receipt["snapshot"])) == (index+1, frame, 1), receipt
        expected_size = size if frame in (2, 3) else fitted_size
        assert (int(receipt["canvas_width"]), int(receipt["canvas_height"])) == expected_size, receipt
        raw = run([ffmpeg, "-nostdin", "-v", "error", "-i", master,
                   "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1"])
        assert len(raw) == width*height*4
        expected = fitted(raw, width, height, *MONITOR)
        shown = (scratch / f"picture-{index}.rgba").read_bytes()
        assert len(shown) == len(expected)
        # FFV1's gbrp16 master has no alpha plane. Compare every displayed RGB
        # channel, as in the independent static oracle; empty preview frames
        # may use transparent black while the encoded master is opaque black.
        assert set(shown[3::4]) <= {0, 255}
        delta = max(abs(a-b) for at, (a, b) in enumerate(zip(shown, expected)) if at % 4 != 3)
        maximum = max(maximum, delta)
        assert delta <= 2, (shape, frame, "persistent seam pixels", delta)
    return dict(shape=shape, frames=frames, snapshot=1, worker_sizes=sizes,
                native_master_comparisons=len(frames), maximum=maximum, passed=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--shape", choices=SHAPES)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--duration", type=int, choices=(2, 3, 5))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true", help="Only immutable 32b41d5 mailbox compatibility")
    parser.add_argument("--stream-client", type=Path)
    parser.add_argument("--wrapper", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg, ffprobe = tool(worker, "ffmpeg"), tool(worker, "ffprobe")
    report = dict(schema="genesis.spatial_transitions", monitor=MONITOR,
                  inputs={name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for name, path in (("binary", binary), ("worker", worker))},
                  results=[], failures=[])
    if args.baseline:
        assert report["inputs"]["binary"] == BASELINE_SHA256, "Baseline mailbox requires the immutable published binary"
    elif args.stream_client is None or args.wrapper is None:
        parser.error("Candidate acceptance requires --stream-client and --wrapper for persistent seam proof")
    picture = baseline_picture if args.baseline else profile_picture

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="genesis-spatial-transitions-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        for shape, (width, height) in SHAPES.items():
            if args.shape and shape != args.shape:
                continue
            sources = {}
            for detailed in (False, True):
                for incoming in (False, True):
                    png = root / f"{shape}-{int(detailed)}-{int(incoming)}.png"
                    media = png.with_suffix(".mkv")
                    fixture(width, height, incoming, detailed).save(png)
                    run([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", png,
                         "-frames:v", "1", "-c:v", "ffv1", "-pix_fmt", "gbrp", media])
                    sources[detailed, incoming] = media
                    png.unlink()
            project = root / f"{shape}.air"
            run([binary, "probe", sources[False, False], root / "ui.png", project],
                dict(env, GENESIS_SCRATCH=str(root / "probe")))
            base = json.loads(project.read_text(encoding="utf-8"))
            base["sequences"][0].update(width=width, height=height, fps=30)
            first = base["clips"][0]
            cases = [(kind, duration) for kind in KINDS
                     for duration in ((2, 3, 5) if kind in ("iris", "clock", "barn_door") else (2,))]
            for kind, duration in cases:
                if args.kind and kind != args.kind:
                    continue
                if args.duration and duration != args.duration:
                    continue
                detailed = kind in ("slide_lr", "zoom")
                document = copy.deepcopy(base)
                document.update(filters=[], filter_params=[], filter_text_params=[], keys=[])
                document["sources"][0].update(path=str(sources[detailed, False]), has_audio=False)
                document["sources"].append(dict(document["sources"][0], id=90, path=str(sources[detailed, True])))
                document["clips"] = [dict(first, length=1, source_in=0),
                                     dict(first, id=91, source=90, start=1, length=1, source_in=0)]
                document["names"].append(kind)
                document["transitions"] = [dict(id=92, owner=first["owner"], track=first["track"],
                                                center=1, duration=duration, kind=len(document["names"]))]
                document["next_id"] = 93
                project.write_text(json.dumps(document), encoding="utf-8")
                scratch = root / f"{shape}-{kind}-{duration}"
                entry = dict(shape=shape, kind=kind, native_size=[width, height], frame=1,
                             progress=(duration//2)/duration, duration=duration)
                try:
                    shown = picture(binary, project, scratch, root / "profile.json", env)
                    master = root / f"{shape}-{kind}-{duration}.mkv"
                    run([binary, "export", master, project], dict(env, GENESIS_SCRATCH=str(scratch / "export")))
                    streams = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-of", "json", master]))
                    video = next(stream for stream in streams["streams"] if stream["codec_type"] == "video")
                    assert (video["width"], video["height"], video["codec_name"], video["pix_fmt"]) == (width, height, "ffv1", "gbrp16le"), video
                    raw = run([ffmpeg, "-nostdin", "-v", "error", "-i", master,
                               "-vf", "select=eq(n\\,1)", "-frames:v", "1", "-f", "rawvideo",
                               "-pix_fmt", "rgba", "pipe:1"])
                    assert len(raw) == width * height * 4
                    expected = Image.frombytes("RGBA", MONITOR, fitted(raw, width, height, *MONITOR)).convert("RGB")
                    entry.update(actual_aspect_box=shown.getbbox(), expected_aspect_box=expected.getbbox(),
                                 comparison="all monitor pixels")
                    delta = [abs(a-b) for a, b in zip(shown.tobytes(), expected.tobytes())]
                    entry.update(maximum=max(delta), mean=sum(delta)/len(delta),
                                 mismatched_channels=sum(value > 2 for value in delta))
                    # Native composition followed by the same documented monitor
                    # sampling permits final FFV1 conversion rounding, not changes
                    # to edge width, source geometry or transition masks.
                    entry["passed"] = entry["maximum"] <= 2 and entry["mean"] < .6
                    if not entry["passed"]:
                        report["failures"].append(dict(entry))
                    master.unlink()
                except Exception as problem:
                    entry.update(passed=False, execution_error=str(problem), scratch_diagnostics=diagnostics(scratch))
                    report["failures"].append(dict(entry))
                    report["results"].append(entry)
                    save()
                    raise
                report["results"].append(entry)
                save()
                print(f"Spatial transition: {shape} {kind} progress={entry['progress']:.4f}, max={entry['maximum']}, mean={entry['mean']:.4f}, passed={entry['passed']}", flush=True)
            if not args.baseline:
                try:
                    entry = persistent_seam(root, shape, (width, height), base, sources, binary, worker,
                                            args.stream_client.resolve(), args.wrapper.resolve(), ffmpeg, env)
                    report.setdefault("persistent_streams", []).append(entry)
                    save()
                    print(f"Persistent spatial seam: {shape}, seven native master pictures, five exact worker canvases, snapshot1 passed", flush=True)
                except Exception as problem:
                    failure = dict(shape=shape, kind="persistent stream", execution_error=str(problem),
                                   scratch_diagnostics=diagnostics(root / f"{shape}-stream"))
                    report["failures"].append(failure)
                    save()
                    raise
    assert not report["failures"], f"{len(report['failures'])} spatial transition preview/master mismatches; see report"
    print(f"Spatial transitions: {len(report['results'])} ordinary-preview/native-16-bit-master comparisons passed")


if __name__ == "__main__":
    main()
