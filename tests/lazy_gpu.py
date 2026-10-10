"""One retained worker dispatcher: audio before OpenCL, pictures once, failure RAII.

The optional Windows fault proxy belongs only to a copied temporary worker;
its exports forward to the original loader except controlled init/read failures.
No application media, installed runtime, or private codec bundle is modified.
"""
import argparse
from array import array
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import statistics
import subprocess
import tempfile
import threading
import time

from audio_stream import wire, pcm
from nested_waveforms import float_wav
from video_transfer import neutral
from media_runtime import tool
from audio_nested import run

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Worker:
    def __init__(self, path, env=None):
        self.started = time.perf_counter()
        self.process = subprocess.Popen([str(path), "--serve", "--size", "64", "64"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env, creationflags=FLAGS)
        self.lines = queue.Queue()
        self.trace = []
        def read():
            for line in self.process.stdout:
                self.trace.append(line.strip())
                self.lines.put(line.strip())
            self.lines.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def command(self, line, error=False, code=None):
        self.process.stdin.write(line+"\n")
        self.process.stdin.flush()
        deadline = time.monotonic()+30
        seen = []
        while True:
            reply = self.lines.get(timeout=max(.01, deadline-time.monotonic()))
            assert reply is not None, ("Worker exited before reply", seen)
            seen.append(reply)
            if reply == "ERR" or reply.startswith("DONE"):
                assert (reply == "ERR") == error, (line[:100], seen)
                if code:
                    assert any("["+code+"]" in item for item in seen), (code, seen)
                return seen

    def close(self, status=0):
        try:
            self.process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            raise
        self.reader.join(timeout=2)
        assert not self.reader.is_alive()
        assert self.process.returncode == status, (status, self.process.returncode, self.trace[-15:])
        return time.perf_counter()-self.started

    def init_count(self):
        return sum(line == "[gpu] init..." for line in self.trace)


def tree(worker, cache, source, frames):
    cache.mkdir()
    duration = frames/48000
    worker.command(f"NESTBEGIN {wire(cache)}")
    worker.command(f"NESTLEAF bus.leaf bus 0 {frames} {wire(source)} 0 {duration:.17g} 1 0 0 {duration:.17g} -")
    worker.command(f"NESTBUS bus - 0 {frames} 0 {frames} 1 0 0 {duration:.17g} -")
    worker.command("NESTCOMMIT")
    output = cache/"peaks.f32"
    worker.command(f"NESTENV bus 8 {wire(output)}")
    values = array("f", output.read_bytes())
    assert values == array("f", [.75]*8), list(values)
    assert len(list(cache.glob("*.rf64"))) >= 3
    return output


def no_cache(cache):
    assert not list(cache.glob("*.rf64")), "Worker-owned cache survived normal unwinding"


def audio_only(root, worker, source, video):
    p = Worker(worker)
    cache = root/"audio-cache"
    try:
        # Every CPU branch receives a malformed request, then valid audio recovers.
        commands = ("NESTBEGIN", "NESTLEAF", "NESTBUS", "NESTCOMMIT", "NESTMIX", "NESTENV",
                    "AUDIO", "AUDIOSTREAM", "GAINENV", "WAVE", "PLAYWAVE", "WAVECLOSE",
                    "MEAS", "LEVELS", "SPECTRUM", "SAMPLES", "CLOSE", "THUMB", "NFRAMES", "ENV", "CLIPAUD")
        for command in commands:
            p.command(command, error=True)
        assert p.command(f"NFRAMES {wire(video)}")[-1] == "DONE 2"
        thumbnail = root/"thumbnail.rgba"
        p.command(f"THUMB {wire(video)} 1 64 64 {wire(thumbnail)}")
        image = thumbnail.read_bytes()
        assert len(image) == 64*64*4
        assert max(abs(image[n*4+c]-(64,128,192,255)[c]) for n in range(4096) for c in range(4)) <= 1
        output = tree(p, cache, source, 256)
        published = sha(output)
        wav = root/"audio.wav"
        p.command(f"PLAYWAVE {wire(wav)} 256")
        p.command(f"AUDIOSTREAM {wire(source)} 0 {256/48000:.17g} 0 .5 0 0 {256/48000:.17g} 0 - 1 {256/48000:.17g} 256")
        p.command(f"WAVECLOSE {wire(wav)}")
        assert pcm(wav) == array("h", [4096, -12288]*256)
    finally:
        elapsed = p.close()
    assert p.init_count() == 0, p.trace
    no_cache(cache)
    assert sha(output) == published, "Caller-owned envelope disappeared"
    return dict(malformed_commands=len(commands), exact_pcm_channels=512, zero_opencl_init=True,
                real_video_frames=2, thumbnail_verified_channels=len(image),
                real_nested_cache_join_cleanup=True, closed_request_seconds=elapsed)


def picture_and_history(root, worker):
    source = root/"history.wav"
    values = array("f", (v for n in range(24000) for v in
        ((.5 if n%7 else -.375), (.125 if n%11 else -.25))))
    float_wav(source, values)
    raster = root/"raster.f32"
    rgba = array("f", [.25, .5, .75, 1]*4096)
    raster.write_bytes(rgba.tobytes())
    fields = neutral()
    fields[0] = "FLOATDIM:64:64:"+wire(raster)
    p = Worker(worker)
    chain = "aecho=0.8:0.9:100:0.5"
    try:
        whole = root/"whole.wav"
        p.command(f"WAVE {wire(whole)} .5")
        p.command(f"AUDIO {wire(source)} 0 .5 0 1 0 0 .5 0 {chain}")
        p.command(f"WAVECLOSE {wire(whole)}")
        assert p.init_count() == 0
        chunks = []
        for at in (0, .25):
            chunk = root/f"chunk-{at}.wav"
            chunks.append(chunk)
            p.command(f"PLAYWAVE {wire(chunk)} 12000")
            p.command(f"AUDIOSTREAM {wire(source)} {at} .25 0 1 0 0 .5 {at} {chain} 2 {.5-at} 12000")
            p.command(f"WAVECLOSE {wire(chunk)}")
            if at == 0:
                p.command("PICBEGIN 17")
                p.command("CANVAS 32 64 1")
                p.command("FLOAT "+" ".join(fields)+" GPU:17:1")
                # A CPU refusal still releases active picture references/restores root.
                p.command("AUDIO", error=True)
                p.command("PICBEGIN 18")
                p.command("FLOAT "+" ".join(fields)+" GPU:18:1")
                p.command("PICDROP 18 1")
                p.command("PICABORT 18")
                image = root/"picture.f32"
                p.command("FLOAT "+" ".join(fields)+" "+wire(image))
                actual = array("f", image.read_bytes())
                assert actual == rgba
                scope = root/"scope.rgba"
                p.command(f"SCOPE 0 {wire(scope)}")
                saved = scope.read_bytes()
                p.command("MEAS .01")
                p.command(f"LEVELS {wire(root/'levels.f32')}")
                second = root/"scope2.rgba"
                p.command(f"SCOPE 0 {wire(second)}")
                assert second.read_bytes() == saved, "CPU measurements overwrote final picture"
                movie = root/"encoder.mkv"
                p.command(f"OPEN {wire(movie)} 64 64 30 1 0 0 ffv1 0 0 - 128000 pcm_s16le 30")
                p.command("ENC "+" ".join(fields))
                p.command("CLOSE")
                assert movie.stat().st_size > 0
        actual = pcm(chunks[0])+pcm(chunks[1])
        expected = pcm(whole)
        assert len(actual) == len(expected) == 48000
        error = max(abs(a-b) for a,b in zip(actual, expected))
        assert error <= 2, error
    finally:
        p.close()
    assert p.init_count() == 1, p.trace
    return dict(init_count=1, exact_float_picture_channels=len(rgba),
                retained_audio_channels=len(actual), maximum_pcm_error=error,
                scopes_survive_cpu_commands=True, snapshot_error_recovery=True, encoder_root_restored=True)


def fault_case(root, worker, proxy, source, video, kind):
    private = root/("fault-"+kind)
    private.mkdir()
    copied = private/worker.name
    shutil.copy2(worker, copied)
    for name in ("genesis-media-runtime.txt",):
        shutil.copy2(worker.parent/name, private/name)
    shutil.copy2(worker.parent/"OpenCL.dll", private/"OpenCL_real.dll")
    shutil.copy2(proxy, private/"OpenCL.dll")
    trace = private/"native.trace"
    p = Worker(copied, dict(os.environ, GENESIS_TEST_OPENCL_FAILURE=kind,
                           GENESIS_TEST_OPENCL_TRACE=str(trace)))
    cache = private/"cache"
    try:
        envelope = tree(p, cache, source, 256)
        assert p.command(f"NFRAMES {wire(video)}")[-1] == "DONE 2"
        thumbnail = private/"cpu-thumbnail.rgba"
        p.command(f"THUMB {wire(video)} 1 64 64 {wire(thumbnail)}")
        image = thumbnail.read_bytes()
        assert len(image) == 64*64*4
        assert max(abs(image[n*4+c]-(64,128,192,255)[c]) for n in range(4096) for c in range(4)) <= 1
        assert not trace.exists(), "Audio-only nested processing touched OpenCL"
        assert p.init_count() == 0
        digest = sha(envelope)
        movie = private/"must-not-create.mkv"
        code = "GA_COMPOSE_GPU_INIT" if kind == "init" else "GA_COMPOSE_GPU_CHECK"
        p.command(f"OPEN {wire(movie)} 64 64 30 1 0 0 ffv1 0 0 - 128000 pcm_s16le 30",
                  error=True, code=code)
    finally:
        p.close(4 if kind == "init" else 5)
    no_cache(cache)
    assert sha(envelope) == digest and not movie.exists()
    events = trace.read_text().splitlines()
    expected = 3 if kind == "init" else 1
    assert events.count("platform") == expected and p.init_count() == expected, events
    if kind == "read":
        assert events.count("read") >= 1
    return dict(fault=kind, exit_code=p.process.returncode, coded_error=code,
                init_attempts=expected, prior_audio_zero_init=True,
                valid_thumb_nframes_zero_native_opencl_calls=True,
                owned_cache_removed=True, no_encoder_output=True, published_envelope_retained=True)


def timing(root, old, new, source):
    rows = []
    for block in range(4):
        for label, worker in (("old", old), ("new", new), ("new", new), ("old", old)):
            cache = root/f"timing-{len(rows)}"
            p = Worker(worker)
            try:
                tree(p, cache, source, 256)
            finally:
                elapsed = p.close()
            no_cache(cache)
            assert p.init_count() == (1 if label == "old" else 0)
            rows.append(dict(block=block, worker=label, closed_request_seconds=elapsed,
                             opencl_init_count=p.init_count()))
    means = {label:statistics.mean(row["closed_request_seconds"] for row in rows if row["worker"]==label)
             for label in ("old", "new")}
    return dict(order="ABBA x 4", requests=rows, means_seconds=means,
                scope="Cold isolated process through actual NESTENV and closed cache cleanup; no physical audio-device timing")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--fault-shim", type=Path)
    parser.add_argument("--reference-worker", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    worker = args.worker.resolve()
    report = dict(passed=False, worker_sha256=sha(worker), cases=[],
                  optional_sections={
                      "fault_cleanup": "pending" if args.fault_shim else "skipped",
                      "startup_timing": "pending" if args.reference_worker else "skipped"})
    if args.reference_worker:
        args.reference_worker = args.reference_worker.resolve()
        report["reference_sha256"] = sha(args.reference_worker)
    try:
        with tempfile.TemporaryDirectory(prefix="genesis-lazy-gpu-") as temp:
            root = Path(temp)
            source = root/"authored stereo 日本語 %20.wav"
            float_wav(source, array("f", [.25, -.75]*256))
            video = root/"authored two-frame video 日本語.mkv"
            run([tool(worker,"ffmpeg"),"-nostdin","-v","error","-f","rawvideo","-pix_fmt","rgb24",
                 "-s","64x64","-r","30","-i","pipe:0","-frames:v","2","-c:v","ffv1",
                 "-pix_fmt","gbrp","-color_range","pc",video],
                data=bytes((192,64,128))*4096+bytes((64,128,192))*4096)
            original = sha(source)
            report["audio_only"] = audio_only(root, worker, source, video)
            report["picture_history"] = picture_and_history(root, worker)
            if args.fault_shim:
                assert os.name == "nt"
                report["faults"] = [fault_case(root, worker, args.fault_shim.resolve(), source, video, kind)
                                    for kind in ("init", "read")]
                report["optional_sections"]["fault_cleanup"] = "passed"
            if args.reference_worker:
                report["timing"] = timing(root, args.reference_worker, worker, source)
                report["optional_sections"]["startup_timing"] = "passed"
            assert sha(source) == original and sha(worker) == report["worker_sha256"]
            report.update(passed=True, original_source_worker_immutable=True)
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    proofs = ["audio-only zero-init", "retained picture/audio history"]
    if args.fault_shim:
        proofs.append("failure cleanup")
    if args.reference_worker:
        proofs.append("ABBA startup timing")
    print("Lazy OpenCL: " + ", ".join(proofs) + " passed")


if __name__ == "__main__":
    main()

