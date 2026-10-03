"""Compare D3D11 readback pixels with FFmpeg's ordinary transfer, including seeks.

The generated clips exercise NV12/P010, padded textures, B frames and fractional
timestamps. --reference-worker also checks a prior build's frame selection.
Hardware availability is reported separately from pixel equivalence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import re
import statistics
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import time

from preview_fit import wire


def neutral():
    source = (Path(__file__).resolve().parent.parent / "src/timeline_media.ai").read_text(encoding="utf-8")
    body = source.split("fn neutral()", 1)[1].split("\nfn source_path", 1)[0]
    fields = ["0"] * 108
    for index, value in re.findall(r'put\(values, (\d+), "([^"]+)"\)', body):
        fields[int(index)] = value
    for index in range(27, 33):
        fields[index] = "1"
    return fields


def capture(worker, source, frames, root, default=False, software=False):
    env = dict(os.environ, GENESIS_MEDIA_PROFILE="1")
    for name in ("GENESIS_DEFAULT_TRANSFER", "GENESIS_SOFTWARE_DECODE"):
        env.pop(name, None)
    if default:
        env["GENESIS_DEFAULT_TRANSFER"] = "1"
    if software:
        env["GENESIS_SOFTWARE_DECODE"] = "1"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen([str(worker), "--serve", "--size", "320", "180"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", env=env, creationflags=flags)
    replies, errors = Queue(), []
    def read_output():
        for line in process.stdout:
            replies.put(line.rstrip())
        replies.put("")
    def read_errors():
        errors.extend(process.stderr)
    reader = Thread(target=read_output, daemon=True)
    diagnostics = Thread(target=read_errors, daemon=True)
    reader.start()
    diagnostics.start()
    output = root / "readback pixels 日本語 %20.bin"
    fields = neutral()
    fields[0] = wire(source)
    hashes, elapsed = [], []
    try:
        # Separate runs of RGBA then float retain real forward decoding between
        # requests, rather than seeking twice to every frame.
        for command, size in (("PREVIEWFIT 173 97", 173 * 97 * 4), ("FLOAT", 320 * 180 * 16)):
            for frame in frames:
                fields[2] = str(frame)
                request = command + " " + " ".join(fields) + " " + wire(output)
                started = time.perf_counter()
                process.stdin.write(request + "\n")
                process.stdin.flush()
                reply = replies.get(timeout=30)
                assert reply == "DONE " + str(output), (frame, reply, "".join(errors[-8:]))
                elapsed.append((time.perf_counter() - started) * 1000)
                pixels = output.read_bytes()
                assert len(pixels) == size and any(pixels), (frame, len(pixels), size)
                hashes.append((command, frame, hashlib.sha256(pixels).hexdigest()))
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        reader.join(timeout=2)
        diagnostics.join(timeout=2)
        process.stdout.close()
        process.stderr.close()
    assert process.returncode == 0, "".join(errors[-12:])
    log = "".join(errors)
    assert "GA_VIDEO_TRANSFER" not in log, log[-2000:]
    return hashes, elapsed, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--reference-worker", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--last-frame", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    worker = args.worker.resolve()
    reference = args.reference_worker.resolve() if args.reference_worker else None
    ffmpeg = worker.parent / "ffmpeg.exe"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    cases, pairs, hardware_cases = [], 0, 0
    with TemporaryDirectory(prefix="genesis-video-transfer-") as directory:
        root = Path(directory)
        fixtures = []
        hevc = ["libx265", "-crf", "16", "-preset", "fast", "-x265-params",
                "keyint=24:min-keyint=24:scenecut=0:bframes=3:log-level=error"]
        for name, dimensions, pixel_format, codec, transfer in (
                ("H264 NV12", "638x358", "yuv420p", ["libx264", "-crf", "16", "-preset", "fast", "-bf", "3", "-g", "24"], "bt709"),
                ("HEVC P010", "642x362", "yuv420p10le", hevc, "bt709"),
                ("AV1 P010", "638x358", "yuv420p10le", ["libaom-av1", "-crf", "24", "-cpu-used", "8", "-g", "24"], "bt709"),
                ("HEVC PQ P010", "642x362", "yuv420p10le", hevc, "smpte2084"),
                ("HEVC HLG P010", "638x358", "yuv420p10le", hevc, "arib-std-b67")):
            source = root / (name + " 日本語.mp4")
            primaries = "bt709" if transfer == "bt709" else "bt2020"
            matrix = "bt709" if transfer == "bt709" else "bt2020nc"
            # Set frame metadata as well as encoder options. Without setparams,
            # this FFmpeg/libx265 build drops transfer/primaries on the synthetic input.
            subprocess.run([str(ffmpeg), "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i",
                            f"testsrc2=size={dimensions}:rate=24000/1001", "-frames:v", "48",
                            "-vf", f"setparams=color_primaries={primaries}:color_trc={transfer}:colorspace={matrix}",
                            "-pix_fmt", pixel_format, "-c:v", *codec,
                            "-color_primaries", primaries, "-color_trc", transfer, "-colorspace", matrix, str(source)],
                           check=True, timeout=90, creationflags=flags)
            probed = subprocess.run([str(ffmpeg.parent / "ffprobe.exe"), "-v", "error",
                                     "-select_streams", "v:0", "-show_streams", "-of", "json", str(source)],
                                    capture_output=True, encoding="utf-8", check=True, timeout=30, creationflags=flags)
            metadata = json.loads(probed.stdout)["streams"][0]
            assert (metadata.get("color_primaries"), metadata.get("color_transfer"), metadata.get("color_space")) == \
                   (primaries, transfer, matrix), (name, "fixture lost its color metadata", metadata)
            fixtures.append((name, source, [0, 1, 2, 4, 7, 12, 23, 24, 25, 37, 46, 47, 0, 47, 2, 1, 0]))
        if args.source:
            assert args.last_frame is not None and args.last_frame > 100
            fixtures.append(("supplied source", args.source.resolve(),
                             [0, 1, 2, 4, 7, 12, 33, 100, 0, 1,
                              args.last_frame - 1, args.last_frame, args.last_frame - 7, 0]))
        for name, source, frames in fixtures:
            fast, elapsed, log = capture(worker, source, frames, root)
            ordinary, _, _ = capture(worker, source, frames, root, default=True)
            assert fast == ordinary, (name, "optimized copy differs from ordinary FFmpeg transfer")
            pairs += len(fast)
            if reference:
                previous, _, _ = capture(reference, source, frames, root)
                assert fast == previous, (name, "frame selection changed from reference worker")
                pairs += len(fast)
            rgba = fast[:len(frames)]
            assert len(set(item[2] for item in rgba)) >= 10, (name, "fixture did not advance through pictures")
            assert rgba[0][2] == rgba[-1][2], (name, "rewind lost frame zero")
            stages = len(re.findall(r"staging wait_us=", log))
            hardware = stages > 0
            if hardware:
                assert "Native D3D11 decode:" in log
                assert stages == len(fast), (name, stages, len(fast), "unused source frames were read back")
                hardware_cases += 1
            else:
                print(f"{name}: hardware unavailable; verified fallback pixels", flush=True)
            color_threads = sorted(set(map(int, re.findall(r"color graph_threads=(\d+)", log))))
            if "PQ" in name or "HLG" in name:
                assert color_threads, (name, "HDR metadata did not reach the color transform")
            software, _, software_log = capture(worker, source, frames[:8] + [0], root, software=True)
            software_default, _, _ = capture(worker, source, frames[:8] + [0], root, default=True, software=True)
            assert software == software_default, (name, "software decode changed")
            assert "staging wait_us=" not in software_log and "Native D3D11 decode:" not in software_log
            if "PQ" in name or "HLG" in name:
                assert "color graph_threads=" in software_log, (name, "software fallback lost HDR metadata")
            pairs += len(software)
            cases.append(dict(name=name, picture_pairs=len(fast), hardware=hardware,
                              selected_readbacks=stages, color_graph_threads=color_threads,
                              median_request_ms=round(statistics.median(elapsed), 3)))
            print(f"{name}: RGBA/float seek, skip, EOF and rewind pixels identical; {stages} selected GPU readbacks", flush=True)
    report = dict(pixel_pairs=pairs, hardware_cases=hardware_cases, cases=cases)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
