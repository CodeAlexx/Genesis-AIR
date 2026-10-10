"""Native RGBA64 upload must retain the accepted FP32 picture contract.

Compare every output channel against the same worker's forced FP32 path,
software decode and an optional accepted reference worker. Check real fast-path
entry, native/fitted/odd qualification, HDR output, seek/EOF/rewind identity and
unchanged source/binary bytes. This is a correctness gate, not a timing test.
"""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Queue
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread

from media_runtime import tool
from preview_fit import wire
from video_transfer import neutral

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
FRAMES = (0, 1, 2, 8, 11, 0, 11, 5, 0)
SOURCES = (
    ("rgb16", 64, 36, "gbrp16le", "ffv1", "bt709"),
    ("nv12", 64, 36, "yuv420p", "libx264", "bt709"),
    ("pq", 64, 36, "yuv420p10le", "libx265", "smpte2084"),
    ("hlg", 64, 36, "yuv420p10le", "libx265", "arib-std-b67"),
    # A tiny odd AV1 canvas can fail unchanged driver initialization. This
    # complete visible-size fixture exercises the existing supported fallback.
    ("odd-pq", 513, 289, "yuv420p10le", "libaom-av1", "smpte2084"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(worker, source, size, root, label, hdr=False, disabled=False,
            software=False):
    trace = root / (label + ".tsv")
    output = root / (label + ".f32")
    env = dict(os.environ, GENESIS_GPU_PREVIEW="0",
               GENESIS_GPU_PHASE_LOG=str(trace))
    for name in ("GENESIS_DEFAULT_TRANSFER", "GENESIS_VIDEO_BACKEND",
                 "GENESIS_NATIVE_U16_UPLOAD", "GENESIS_SOFTWARE_DECODE"):
        env.pop(name, None)
    if disabled:
        env["GENESIS_NATIVE_U16_UPLOAD"] = "0"
    if software:
        env["GENESIS_SOFTWARE_DECODE"] = "1"
    args = [str(worker), "--serve", "--size", str(size[0]), str(size[1])]
    if hdr:
        args.append("--hdr")
    child = subprocess.Popen(args, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", errors="replace",
                             env=env, creationflags=FLAGS)
    replies, errors = Queue(), []
    reader = Thread(target=lambda: [replies.put(line.strip())
                                   for line in child.stdout], daemon=True)
    diagnostic = Thread(target=lambda: errors.extend(child.stderr), daemon=True)
    reader.start()
    diagnostic.start()
    fields = neutral()
    fields[0] = wire(source)
    pictures = []
    try:
        for frame in FRAMES:
            fields[2] = str(frame)
            child.stdin.write("FLOAT " + " ".join(fields) + " " + wire(output) + "\n")
            child.stdin.flush()
            reply = replies.get(timeout=30)
            assert reply == "DONE " + str(output), (label, frame, reply, errors[-8:])
            raw = output.read_bytes()
            values = array("f")
            values.frombytes(raw)
            assert len(values) == size[0] * size[1] * 4, (label, frame, len(values))
            assert all(math.isfinite(value) for value in values), (label, frame, "nonfinite")
            pictures.append(raw)
    finally:
        try:
            child.stdin.close()
        except BrokenPipeError:
            pass
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Only the exact worker process created by this capture is killed.
            child.kill()
            child.wait(timeout=5)
            raise
        reader.join(timeout=2)
        diagnostic.join(timeout=2)
        child.stdout.close()
        child.stderr.close()
        (root / (label + ".stderr.txt")).write_text("".join(errors), encoding="utf-8")
    assert child.returncode == 0, (label, child.returncode, errors[-8:])
    assert pictures[0] == pictures[-1] and pictures[0] != pictures[1], (label, "frame identity")
    entries = trace.read_text(encoding="utf-8").splitlines() if trace.exists() else []
    count = sum(line.startswith("NATIVE16\t") for line in entries)
    return pictures, count


def encode(ffmpeg, root, name, width, height, pixel_format, codec, transfer):
    source = root / (name + (".mkv" if codec == "ffv1" else ".mp4"))
    hdr = transfer != "bt709"
    metadata = ["-color_primaries", "bt2020" if hdr else "bt709",
                "-color_trc", transfer, "-colorspace", "bt2020nc" if hdr else "bt709"]
    if codec == "libx265":
        extra = ["-x265-params", "log-level=error:keyint=6:bframes=2"]
    elif codec == "libaom-av1":
        extra = ["-cpu-used", "8", "-crf", "18", "-g", "6"]
    else:
        extra = []
    result = subprocess.run(
        [str(ffmpeg), "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
         f"testsrc=size={width}x{height}:rate=24", "-frames:v", "12",
         "-pix_fmt", pixel_format, "-c:v", codec, *extra, *metadata, str(source)],
        capture_output=True, timeout=90, creationflags=FLAGS)
    assert result.returncode == 0, (name, result.stderr.decode(errors="replace"))
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", required=True, type=Path)
    parser.add_argument("--reference-worker", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--scratch", type=Path, help="New caller-owned directory; retain diagnostic files")
    args = parser.parse_args()
    worker = args.worker.resolve()
    reference = args.reference_worker.resolve() if args.reference_worker else None
    before = {str(path): digest(path) for path in (worker, reference) if path}
    report = dict(passed=False, cases=[], channel_checks=0,
                  worker_sha256=before[str(worker)], binary_hashes_before=before)
    try:
        with TemporaryDirectory(prefix="genesis-native-u16-") as temporary:
            root = args.scratch.resolve() if args.scratch else Path(temporary)
            if args.scratch:
                root.mkdir(parents=True, exist_ok=False)
            ffmpeg = tool(worker, "ffmpeg")
            for spec in SOURCES:
                name, width, height, pixel_format, codec, transfer = spec
                source = encode(ffmpeg, root, *spec)
                source_before = digest(source)
                for size, hdr in (((width, height), False),
                                  ((width, height), True), ((80, 48), False)):
                    label = f"{name}-{size[0]}x{size[1]}-hdr{hdr}"
                    fast, entries = capture(worker, source, size, root, label + "-native", hdr)
                    scalar, disabled_entries = capture(worker, source, size, root,
                                                       label + "-fp32", hdr, disabled=True)
                    software, software_entries = capture(worker, source, size, root,
                                                         label + "-software", hdr, software=True)
                    assert fast == scalar == software, (label, "FP32 pixel contract changed")
                    if reference:
                        accepted, _ = capture(reference, source, size, root, label + "-reference", hdr)
                        assert fast == accepted, (label, "accepted worker pixels changed")
                    native = size == (width, height) and width % 2 == 0 and height % 2 == 0
                    expected = len(FRAMES) if native else 0
                    assert entries == software_entries == expected, (label, entries, software_entries, expected)
                    assert disabled_entries == 0, (label, "forced FP32 still entered native-u16")
                    assert digest(source) == source_before, (label, "source bytes changed")
                    report["channel_checks"] += len(FRAMES) * size[0] * size[1] * 4
                    report["cases"].append(dict(name=label, frames=len(FRAMES), bit_exact=True,
                                                native16_entries=entries, source_sha256=source_before))
                    print(label + ": bit-exact; native-u16 entries=" + str(entries), flush=True)
            report["source_bytes_unchanged"] = True
        after = {str(path): digest(path) for path in (worker, reference) if path}
        assert after == before, "worker binary changed during acceptance"
        report["binary_hashes_after"] = after
        report["passed"] = True
    except Exception as error:
        report["failure"] = repr(error)
        raise
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "cases": len(report["cases"]),
                      "channel_checks": report["channel_checks"]}), flush=True)


if __name__ == "__main__":
    main()
