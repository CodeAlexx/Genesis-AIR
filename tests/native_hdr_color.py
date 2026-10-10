"""Qualified native P010/PQ color, exact fallback and actual runtime identity.

Every output channel must be finite. Accelerated native samples retain the
existing five-u16-code limit; explicit reference/HDR/unsupported/fault paths
remain byte-exact. Existing compatibility gates keep their exact expectations.
"""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Queue
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread

from media_runtime import tool
from preview_fit import wire
from video_transfer import neutral

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            result.update(data)
    return result.hexdigest()


def capture(worker, source, frames, size, root, label, native="0", gpu="0",
            reference=False, hdr=False, fault=None, runtime=None, forced=False):
    env = dict(os.environ, GENESIS_NATIVE_COLOR_PROFILE="1", GENESIS_GPU_PREVIEW=gpu)
    for key in ("GENESIS_NATIVE_HDR_COLOR", "GENESIS_NATIVE_HDR_FAULT",
                "GENESIS_NATIVE_HDR_FORCE_CPU_FALLBACK", "GENESIS_SOFTWARE_DECODE",
                "GENESIS_VIDEO_BACKEND", "GENESIS_DEFAULT_TRANSFER"):
        env.pop(key, None)
    if native is not None:
        env["GENESIS_NATIVE_HDR_COLOR"] = native
    if fault:
        env["GENESIS_NATIVE_HDR_FAULT"] = fault
    if forced:
        env["GENESIS_NATIVE_HDR_FORCE_CPU_FALLBACK"] = "1"
    if runtime:
        env["GENESIS_FFMPEG_RUNTIME"] = str(runtime)
    argv = [str(worker), "--serve", "--size", *map(str, size)]
    if reference:
        argv.append("--reference-color")
    if hdr:
        argv.append("--hdr")
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             errors="replace", env=env, creationflags=FLAGS)
    replies, errors = Queue(), []
    reader = Thread(target=lambda: [replies.put(line.strip()) for line in child.stdout], daemon=True)
    logger = Thread(target=lambda: errors.extend(child.stderr), daemon=True)
    reader.start(); logger.start()
    fields = neutral(); fields[0] = wire(source)
    outputs = []
    try:
        for index, frame in enumerate(frames):
            output = root / f"{label}-{index}.f32"
            fields[2] = str(frame)
            child.stdin.write("FLOAT " + " ".join(fields) + " " + wire(output) + "\n")
            child.stdin.flush()
            reply = replies.get(timeout=45)
            assert reply == "DONE " + str(output), (label, frame, reply, errors[-12:])
            assert output.stat().st_size == size[0] * size[1] * 16
            outputs.append(output)
    finally:
        try:
            child.stdin.close()
        except BrokenPipeError:
            pass
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=5)
            raise
        reader.join(2); logger.join(2)
        child.stdout.close(); child.stderr.close()
        (root / (label + ".stderr.txt")).write_text("".join(errors), encoding="utf-8")
    assert child.returncode == 0, (label, errors[-12:])
    return outputs, errors


def compare(expected, actual, exact):
    checks, worst = 0, 0.0
    for first, second in zip(expected, actual):
        raw = second.read_bytes()
        a, b = array("f"), array("f")
        a.frombytes(first.read_bytes()); b.frombytes(raw)
        assert len(a) == len(b)
        assert all(math.isfinite(value) for value in b)
        assert all(b[index] == 1 for index in range(3, len(b), 4))
        error = max(abs(x-y) for x,y in zip(a,b))
        assert error <= 5 / 65535, (first.name, error * 65535)
        if exact:
            assert first.read_bytes() == raw, (first.name, "reference bytes changed")
        worst = max(worst, error * 65535); checks += len(b)
    return checks, worst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--require-qualified", action="store_true")
    parser.add_argument("--source", type=Path, help="Optional read-only native 3840x2160 PQ source")
    parser.add_argument("--last-frame", type=int)
    args = parser.parse_args()
    worker = args.worker.resolve(); worker_hash = digest(worker)
    report = dict(passed=False, worker_sha256=worker_hash, cases=[])
    try:
        with TemporaryDirectory(prefix="genesis-native-hdr-") as temporary:
            root = args.scratch.resolve() if args.scratch else Path(temporary)
            if args.scratch:
                root.mkdir(parents=True, exist_ok=False)
            source = root / "PQ dense.mp4"; raw = root / "PQ dense.yuv"
            with raw.open("wb") as file:
                for n in range(8):
                    for width,height,stepx,stepy,stepn in ((512,288,1,13,127),(256,144,67,19,211),(256,144,11,113,71)):
                        values = array("H", ((x*stepx+y*stepy+n*stepn)%1024
                                             for y in range(height) for x in range(width)))
                        file.write(values.tobytes())
            encoded = subprocess.run([str(tool(worker,"ffmpeg")), "-nostdin", "-v", "error", "-y",
                "-f", "rawvideo", "-pixel_format", "yuv420p10le", "-video_size", "512x288",
                "-framerate", "24", "-i", str(raw), "-c:v", "libx265", "-x265-params",
                "lossless=1:log-level=error:keyint=4:bframes=2:colorprim=9:transfer=16:colormatrix=9:range=limited:chromaloc=0",
                "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
                "-color_range", "tv", "-chroma_sample_location", "left", str(source)],
                capture_output=True, timeout=90, creationflags=FLAGS)
            assert encoded.returncode == 0, encoded.stderr
            source_hash = digest(source); frames = [0,1,2,7,0]
            references = {}
            def case(name, size=(512,288), native="0", gpu="0", exact=True,
                     reference=False, hdr=False, fault=None, runtime=None, forced=False):
                key=(size,hdr)
                if key not in references:
                    references[key],_ = capture(worker,source,frames,size,root,"cpu-"+str(len(references)),hdr=hdr)
                actual,logs = capture(worker,source,frames,size,root,name,native,gpu,reference,hdr,fault,runtime,forced)
                checks,worst = compare(references[key],actual,exact)
                entries = sum(line.startswith("NATIVEHDR ") for line in logs)
                guards = [line.strip() for line in logs if line.startswith("NATIVEHDR_GUARD ")]
                if not exact:
                    if args.require_qualified:
                        assert entries == len(frames), (name, entries, guards)
                    if entries:
                        assert entries == len(frames) and len(guards)==1 and "qualified=1" in guards[0]
                elif fault:
                    qualified = any("qualified=1" in line for line in guards)
                    if args.require_qualified or qualified:
                        assert len(guards)==1 and "qualified=1" in guards[0], (name, "fault did not reach qualified path", guards)
                        assert any("reference fallback" in line for line in logs), (name, "injected fault was ignored", entries)
                        assert entries == (1 if fault=="map" else 0), (name, entries)
                        assert any("NATIVEHDR_CLOSE external_bytes=0" in line for line in logs), (name, "fault leaked resource reservation")
                    else:
                        assert entries == 0, (name, "unqualified shader entry", entries)
                else:
                    assert entries == 0, (name,entries)
                if runtime:
                    assert len(guards)==1 and "qualified=0" in guards[0] and "held_files=0" in guards[0]
                if name in ("default-GPU-disabled","native-disabled","reference-override","HDR-master","fitted-fallback","forced-CPU"):
                    assert not guards, (name,"unnecessary runtime hash")
                report["cases"].append(dict(name=name,channel_checks=checks,max_codes=worst,exact=exact,shader_entries=entries,guards=guards))
            case("default-qualified",native=None,gpu="1",exact=False)
            case("explicit-qualified",native="1",exact=False)
            case("default-GPU-disabled",native=None)
            case("native-disabled",gpu="1")
            case("reference-override",native="1",reference=True)
            case("HDR-master",native="1",hdr=True)
            case("fitted-fallback",native="1",size=(256,144))
            case("forced-CPU",native="1",forced=True)
            for fault in ("reserve","resources","map"):
                case("fault-"+fault,native="1",fault=fault)
            config = worker.parent / "genesis-media-runtime.txt"
            runtime = Path(os.environ.get("GENESIS_FFMPEG_RUNTIME") or config.read_text(encoding="utf-8").splitlines()[0]).resolve()
            unknown = root / "unknown-runtime"; unknown.mkdir()
            for name in ("avutil-61.dll","avfilter-12.dll","swscale-10.dll","avcodec-63.dll","avformat-63.dll","swresample-7.dll"):
                original = runtime / name
                if name=="avfilter-12.dll":
                    shutil.copyfile(original,unknown/name)
                    with (unknown/name).open("ab") as file:
                        file.write(b"private runtime identity rejection fixture")
                else:
                    # A qualified live worker holds the original file object
                    # against deletion; hardlink aliases would inherit that
                    # restriction and strand this owned temporary fixture.
                    shutil.copyfile(original,unknown/name)
            case("unknown-loaded-runtime",native="1",runtime=unknown)
            assert digest(source)==source_hash
            report["generated_source_sha256"]=source_hash
            if args.source:
                supplied=args.source.resolve();before=digest(supplied)
                assert args.last_frame and args.last_frame>1000
                selected=[0,1,2,100,500,1000,args.last_frame,0]
                baseline,_=capture(worker,supplied,selected,(3840,2160),root,"supplied-reference")
                actual,logs=capture(worker,supplied,selected,(3840,2160),root,"supplied-native",native=None,gpu="1")
                checks,worst=compare(baseline,actual,False)
                entries=sum(line.startswith("NATIVEHDR ") for line in logs)
                if args.require_qualified:
                    assert entries==len(selected)
                assert digest(supplied)==before
                report["cases"].append(dict(name="supplied-native4K",frames=selected,channel_checks=checks,max_codes=worst,shader_entries=entries,source_sha256=before,source_unchanged=True))
            assert digest(worker)==worker_hash
            report["passed"]=True
    except Exception as error:
        report["failure"]=repr(error)
        raise
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=True,cases=len(report["cases"]),worker_sha256=worker_hash)))


if __name__ == "__main__":
    main()
