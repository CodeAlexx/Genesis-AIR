"""Native P010 HDR preview: color oracle, selected readbacks, seek and fallback."""
import argparse
from array import array
import math
import os
from pathlib import Path
from queue import Queue
import re
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread

from media_runtime import tool
from preview_fit import wire
from video_transfer import neutral

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def capture(worker, source, frames, directory, gpu, width=256, height=144, hdr=False, reference_color=False):
    env = dict(os.environ, GENESIS_MEDIA_PROFILE="1", GENESIS_GPU_PREVIEW="1" if gpu else "0")
    env.pop("GENESIS_VIDEO_BACKEND", None)
    env.pop("GENESIS_SOFTWARE_DECODE", None)
    argv = [str(worker), "--serve", "--size", str(width), str(height)]
    if hdr:
        argv.append("--hdr")
    if reference_color:
        argv.append("--reference-color")
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", env=env, creationflags=FLAGS)
    replies, errors, pictures = Queue(), [], []
    def output():
        for line in process.stdout:
            replies.put(line.rstrip())
        replies.put("")
    def diagnostics():
        errors.extend(process.stderr)
    reader, logger = Thread(target=output), Thread(target=diagnostics)
    reader.start(); logger.start()
    fields = neutral(); fields[0] = wire(source)
    target = directory / "HDR pixels rôle 日本語.f32"
    try:
        for frame in frames:
            fields[2] = str(frame)
            process.stdin.write("FLOAT " + " ".join(fields) + " " + wire(target) + "\n")
            process.stdin.flush()
            reply = replies.get(timeout=30)
            assert reply == "DONE " + str(target), (frame, reply, errors[-10:])
            pixels = array("f"); pixels.frombytes(target.read_bytes())
            assert len(pixels) == width*height*4
            assert all(math.isfinite(v) and 0 <= v <= 1 for v in pixels), "invalid preview channel"
            assert all(pixels[i] == 1 for i in range(3, len(pixels), 4)), "lost opaque alpha"
            pictures.append(pixels)
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
            raise
        reader.join(timeout=2); logger.join(timeout=2)
        process.stdout.close(); process.stderr.close()
    assert process.returncode == 0, errors[-12:]
    return pictures, "".join(errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", required=True, type=Path)
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()
    worker = args.worker.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    with TemporaryDirectory(prefix="genesis-hdr-preview-") as temporary:
        root = Path(temporary)
        width, height = 512, 288
        raw = root / "PQ patches.rgb48"
        levels = (0, 8192, 16384, 24576, 32768, 40960, 49152, 65535)
        with raw.open("wb") as file:
            for frame in range(12):
                pixels = array("H")
                for y in range(height):
                    for x in range(width):
                        tile = y//36*8+x//64
                        pixels.extend((levels[tile%8], levels[tile//8], min(65535,levels[(tile+frame)%8]+frame*97)))
                file.write(pixels.tobytes())
        source = root / "PQ patches 日本語.mp4"
        done = subprocess.run([str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pixel_format", "rgb48le", "-video_size", f"{width}x{height}",
            "-framerate", "24000/1001", "-i", str(raw), "-vf",
            "zscale=pin=bt2020:tin=smpte2084:min=gbr:rin=full:p=bt2020:t=smpte2084:m=bt2020nc:r=limited,format=yuv420p10le",
            "-c:v", "libx265", "-preset", "fast", "-x265-params", "lossless=1:log-level=error",
            "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
            "-color_range", "tv", "-chroma_sample_location", "left", str(source)],
            capture_output=True, timeout=120, creationflags=FLAGS)
        assert done.returncode == 0, done.stderr.decode(errors="replace")
        frames = [0,1,2,5,10,11,3,0]
        reference, cpu_log = capture(worker, source, frames, root, False)
        actual, log = capture(worker, source, frames, root, True)
        hardware = "Native GPU HDR preview:" in log
        assert "GA_GPU_COLOR" not in log, log[-3000:]
        if args.require_gpu:
            assert hardware, "native GPU preview was not exercised"
        if hardware:
            assert log.count("gpu_color_us=") == len(frames), "selected GPU pictures were lost"
            assert "decode transfer_us=" not in log, "full source crossed GPU/CPU boundary"
            assert log.count("readback_bytes=589824") == len(frames), "readback did not match preview dimensions"
            assert actual[0] == actual[-1], "GPU rewind did not recover frame zero"
            assert len({p.tobytes() for p in actual[:6]}) == 6, "GPU selected a stale frame"
            worst = 0.0
            # Patch centers isolate color from edge resampling. Include black,
            # full white, saturated primary/gamut values and changing frame IDs.
            for expected, shown in zip(reference, actual):
                for tile in range(64):
                    at = ((tile//8*18+9)*256+tile%8*32+16)*4
                    delta = max(abs(expected[at+c]-shown[at+c])*255 for c in range(3))
                    worst = max(worst, delta)
            assert worst <= 1, ("HDR patch color changed", worst)
            print(f"GPU HDR: {len(frames)*64} color patches within {worst:.3f}/255; seek/skip/EOF/rewind and selected preview readbacks passed")
        else:
            assert actual == reference, "unsupported device changed fallback pixels"
            print("GPU HDR unavailable on this device; exact CPU fallback pixels passed")
        odd, odd_log = capture(worker, source, [0,11,0], root, True, 257, 145)
        assert odd[0] == odd[-1], "odd-canvas rewind differed"
        for image in odd:
            for y in range(145):
                at = (y*257+256)*4
                assert image[at:at+3] == array("f", [0,0,0]), "right letterbox edge changed"
            for x in range(257):
                at = (144*257+x)*4
                assert image[at:at+3] == array("f", [0,0,0]), "bottom letterbox edge changed"
        # Native-size and explicit HDR workers preserve the master color path.
        for size, hdr in (((512,288), False), ((256,144), True)):
            cpu, _ = capture(worker, source, [0,11,0], root, False, *size, hdr)
            fallback, fallback_log = capture(worker, source, [0,11,0], root, True, *size, hdr)
            assert fallback == cpu and "Native GPU HDR preview:" not in fallback_log
        print("GPU HDR: odd canvas/resize, opaque letterbox and exact native-size/HDR master fallback passed")
        reference, _ = capture(worker, source, [0,11,0], root, False)
        master, master_log = capture(worker, source, [0,11,0], root, True, reference_color=True)
        assert master == reference and "Native GPU HDR preview:" not in master_log, "downscaled SDR master used preview resampling"
        print("GPU HDR: downscaled SDR export reference overrides GPU preview setting")
        # Valid bitstreams can carry excursions outside nominal limited range.
        # In particular, PQ's asymptote used to overflow the shader and show
        # black where the reference shows limiting white.
        boundary_raw = root / "PQ range excursions.yuv"
        excursions = ((64,512,512), (940,512,512), (1023,512,512),
                      (940,64,960), (1023,0,1023), (1023,1023,0),
                      (64,0,0), (512,1023,1023))
        with boundary_raw.open("wb") as file:
            for y, u, v in excursions:
                for value, count in ((y,512*288), (u,256*144), (v,256*144)):
                    file.write((array("H", [value])*count).tobytes())
        boundary_source = root / "PQ range excursions.mp4"
        done = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-y",
            "-f", "rawvideo", "-pixel_format", "yuv420p10le", "-video_size", "512x288",
            "-framerate", "24", "-i", str(boundary_raw), "-vf",
            "setparams=range=limited:color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc",
            "-c:v", "libx265", "-preset", "fast", "-x265-params", "lossless=1:log-level=error",
            "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
            "-color_range", "tv", "-chroma_sample_location", "left", str(boundary_source)],
            capture_output=True, timeout=120, creationflags=FLAGS)
        assert done.returncode == 0, done.stderr.decode(errors="replace")
        boundary_frames = list(range(len(excursions)))
        boundary_cpu, _ = capture(worker, boundary_source, boundary_frames, root, False)
        boundary_gpu, boundary_log = capture(worker, boundary_source, boundary_frames, root, True)
        if hardware:
            assert boundary_log.count("gpu_color_us=") == len(excursions), "range excursion bypassed GPU gate"
        worst = max(abs(a-b)*255 for cpu, gpu in zip(boundary_cpu, boundary_gpu)
                    for a, b in zip(cpu, gpu))
        assert worst <= 1, ("PQ range excursion changed limiting output", worst)
        print(f"GPU HDR: all pixels of eight PQ range excursions within {worst:.3f}/255; finite limiting white passed")


if __name__ == "__main__":
    main()
