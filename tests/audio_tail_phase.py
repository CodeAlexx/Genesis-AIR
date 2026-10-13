"""Independent native-count/full-DSP EOF versus retained AUDIOPHASE caches.

Native input selection rounds frames to microseconds, then native samples.
The reference resamples that complete selected input before ordered DSP, drains
actual EOF, and only then applies the original-owner absolute 48 kHz crop.
Authored endpoints and actual cache EOF are checked separately; NESTENV zeros
are coverage of an authored bucket, never extra samples in the accepted cache.
"""
import argparse
from array import array
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import traceback
import uuid
import wave

import numpy as np
from nested_waveforms import Worker, buckets, data_offset
from audio_stream import wire
from media_runtime import tool

FLAGS = 0x08000000 if os.name == "nt" else 0
SR = 48000
FPS = [Fraction(24), Fraction(30), Fraction(60), Fraction(24000, 1001),
       Fraction(30000, 1001), Fraction(60000, 1001)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nearest(value):
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def sample(frame, fps):
    return nearest(Fraction(frame * SR) / fps)


def native(frame, rate, fps):
    return nearest(Fraction(nearest(Fraction(frame * 1000000) / fps) * rate, 1000000))


def quantize(values):
    values = np.clip(values, -1, 1)
    return (np.sign(values) * np.floor(np.abs(values) * 32767 + .5)).astype(np.int16)


def pcm(path):
    with wave.open(str(path), "rb") as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate()) == (2, 2, SR)
        return np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").reshape(-1, 2)


def run(worker, report_path):
    report_path = report_path.resolve()
    assert not report_path.exists(), "Refusing to replace a prior report"
    out = report_path.parent / ("phase-" + uuid.uuid4().hex[:16])
    out.mkdir(parents=True, exist_ok=False)
    ffmpeg = tool(worker, "ffmpeg")
    bound = {str(p.resolve()): sha(p) for p in (worker, ffmpeg, Path(__file__))}
    for module in ("nested_waveforms", "audio_stream", "media_runtime"):
        p = Path(__import__(module).__file__)
        bound[str(p.resolve())] = sha(p)
    report = dict(schema="genesis.audio-tail-phase.v1", passed=False,
                  worker_sha256=sha(worker), checker_sha256=sha(__file__),
                  bound_inputs=bound, work_directory=str(out), cases=[], refusals=[],
                  thresholds=dict(float_error=2e-6, pcm16_codes=1),
                  policy="nearest microsecond/native count; whole native resample; actual DSP EOF; original-owner 48k crop")
    sources = {}
    try:
        for rate in (44100, 48000):
            n = np.arange(rate * 8, dtype=np.int64)
            # Independently authored, asymmetric sample-coded stereo, with an
            # impulse near each packet boundary to catch a shifted selection.
            left = ((n * 193 + 71) % 10001 - 5000).astype(np.int16)
            right = ((n * 307 + 139) % 14001 - 7000).astype(np.int16)
            left[4093::4096] = 12000
            right[4095::4096] = -14000
            source = out / ("native-%d.wav" % rate)
            with wave.open(str(source), "wb") as f:
                f.setparams((2, 2, rate, 0, "NONE", "PCM"))
                f.writeframes(np.stack((left, right), axis=1).astype("<i2").tobytes())
            sources[rate] = source
        source_hashes = {str(p): sha(p) for p in sources.values()}

        def reference(rate, fps, length, chain):
            ns, nc = native(37, rate, fps), native(length, rate, fps)
            chain = (f"atrim=start_sample={ns}:end_sample={ns + nc},asetpts=PTS-STARTPTS,"
                     "aresample=48000,aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo," + chain)
            p = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(sources[rate]),
                                "-af", chain, "-f", "f32le", "pipe:1"], capture_output=True,
                               timeout=30, creationflags=FLAGS)
            assert p.returncode == 0, p.stderr.decode("utf8", errors="replace")
            return np.frombuffer(p.stdout, dtype="<f4").reshape(-1, 2)

        def check(rate, fps, origin, length, offset, place, chain, marked=True, cap=False):
            label = f"r{rate}-f{fps.numerator}_{fps.denominator}-o{origin}-l{length}-crop{offset}-at{place}-{len(report['cases'])}"
            short = "c%d" % len(report["cases"])
            cache = out / (short + "-cache")
            cache.mkdir()
            N = sample(origin + length, fps) - sample(origin, fps)
            crop = sample(origin + offset, fps) - sample(origin, fps)
            start, end = sample(place, fps), sample(place + length - offset, fps)
            full = reference(rate, fps, length, chain)
            pre = reference(rate, fps, length, "anull")
            want = full[crop:]
            if chain == "anull":
                assert len(pre) == N - 1, (label, "negative native seam witness", len(pre), N)
            if cap:
                assert len(full) - len(pre) == 240000
            rows = [f"NESTLEAF leaf bus {start} {end} {wire(sources[rate])} {37 / float(fps):.17g} {length / float(fps):.17g} 1 0 0 {(end-start)/SR:.17g} {chain} AUDIOCTX:{37 / float(fps):.17g}:{length / float(fps):.17g}:{N}:{crop} AUDIOTAIL",
                    f"NESTBUS bus - {start} {end} {start} {end} 1 0 0 {(end-start)/SR:.17g} - AUDIOTAIL"]
            if marked:
                rows[0] += f" AUDIOPHASE:{rate}:{float(fps):.17g}:{origin}:{length}:37:{offset}:{length-offset}:{place}"
            p = Worker(worker)
            commands = []

            def cmd(line, code=None):
                result = p.command(line, code)
                commands.append(dict(command=line, response=result))
                return result

            def define(items):
                cmd("NESTBEGIN " + wire(cache))
                for row in items:
                    cmd(row)

            def hashes():
                return {f.name: sha(f) for f in cache.iterdir()}

            try:
                define(rows)
                cmd("NESTCOMMIT")
                files = list(cache.glob("*-output.rf64"))
                assert len(files) == 2
                errors = []
                for f in files:
                    raw = f.read_bytes()
                    actual = np.frombuffer(raw, dtype="<f4", offset=data_offset(raw)).reshape(-1, 2)
                    assert actual.shape == want.shape, (label, actual.shape, want.shape)
                    error = float(np.max(np.abs(actual - want), initial=0))
                    assert error <= 2e-6, (label, error)
                    errors.append(error)
                q = cmd("NESTEND 1 bus 0")[-1].split()
                generation, qs, qe, eof = map(int, q[4:])
                assert generation > 0 and (qs, qe, eof) == (start, end, start + len(want))
                assert cmd(f"NESTEND 2 bus {generation}")[-1].split()[4:] == q[4:]
                wav = out / (short + ".wav")
                count = len(want) + 1
                cmd(f"PLAYWAVE {wire(wav)} {count}")
                cmd(f"NESTMIXTAIL bus {start} {start + count} 0")
                cmd("WAVECLOSE " + wire(wav))
                expected = np.zeros((count, 2), np.int16)
                expected[:-1] = quantize(want)
                actual_pcm = pcm(wav)
                assert actual_pcm.shape == expected.shape
                pcm_error = int(np.max(np.abs(actual_pcm.astype(np.int32) - expected.astype(np.int32)), initial=0))
                assert pcm_error <= 1, (label, pcm_error)
                peaks = cache / "peaks.f32"
                cmd(f"NESTENV bus 37 {wire(peaks)}")
                authored = np.zeros((end-start, 2), np.float32)
                authored[:min(len(want), len(authored))] = want[:len(authored)]
                expected_peaks = np.array(buckets(array("f", authored.flatten()), 37))
                actual_peaks = np.fromfile(peaks, dtype="<f4")
                assert actual_peaks.shape == expected_peaks.shape
                peak_error = float(np.max(np.abs(actual_peaks - expected_peaks), initial=0))
                assert peak_error <= 2e-6
                accepted = hashes()
                if cap:
                    over = "aecho=0.8:0.9:5000.020833333334:0.4"
                    assert len(reference(rate, fps, length, over)) - len(pre) == 240001
                    define([rows[0].replace(chain, over), rows[1]])
                    cmd("NESTCOMMIT", "GA_AUDIO_CONTEXT_TAIL")
                    assert hashes() == accepted
                    report["refusals"].append(dict(kind="true five-second plus one tail", phase=len(pre)-N, old_cache_unchanged=True))
                if rate == 44100 and fps == Fraction(60000, 1001) and chain == "anull" and offset == 0:
                    token = next(t for t in rows[0].split() if t.startswith("AUDIOPHASE:"))
                    for unsupported in ("25", "50", "120", "59.94"):
                        # Give each unsupported FPS its own consistent seconds,
                        # counts and absolute bounds: refusal must not merely
                        # witness an unchanged row's inconsistent geometry.
                        owner = Fraction(unsupported)
                        ubegin, uend = sample(place, owner), sample(place + length-offset, owner)
                        un = sample(origin+length, owner)-sample(origin, owner)
                        ucrop = sample(origin+offset, owner)-sample(origin, owner)
                        bad = (f"NESTLEAF leaf bus {ubegin} {uend} {wire(sources[rate])} "
                               f"{37/float(owner):.17g} {length/float(owner):.17g} 1 0 0 {(uend-ubegin)/SR:.17g} "
                               f"anull AUDIOCTX:{37/float(owner):.17g}:{length/float(owner):.17g}:{un}:{ucrop} "
                               f"AUDIOTAIL AUDIOPHASE:{rate}:{unsupported}:{origin}:{length}:37:{offset}:{length-offset}:{place}")
                        cmd("NESTBEGIN " + wire(cache))
                        cmd(bad, "GA_AUDIO_PHASE")
                        assert hashes() == accepted
                        report["refusals"].append(dict(kind="unproved owner FPS", fps=unsupported, old_cache_unchanged=True))
                    cmd("NESTBEGIN " + wire(cache))
                    cmd(rows[0] + " " + token, "GA_AUDIO_PHASE")
                    assert hashes() == accepted
                    report["refusals"].append(dict(kind="duplicate phase", old_cache_unchanged=True))
                report["cases"].append(dict(name=label, native_rate=rate, fps=float(fps), native_body=len(pre),
                    original_authored_body=N, native_phase=len(pre)-N, destination_authored_body=end-start,
                    actual_eof=eof, query_generation=generation, actual_cache_frames=len(want),
                    float_errors=errors, pcm16_error=pcm_error, pcm16_values=expected.size,
                    peaks_error=peak_error, actual_eof_not_padded=True, marked=marked))
            finally:
                p.close()
                (out / (short + "-commands.json")).write_text(json.dumps(commands, indent=2) + "\n", encoding="utf8")
                assert not list(cache.glob("*.rf64")), "Owned accepted caches must be removed on close"

        for rate in (44100, 48000):
            for fps in FPS:
                check(rate, fps, 1, 61, 2, 4, "aecho=0.8:0.9:250:0.4")
        seams = [(44100, Fraction(60000,1001), 3, 44), (48000, Fraction(30000,1001), 4, 17),
                 (48000, Fraction(30000,1001), 4, 44)]
        for rate, fps, origin, length in seams:
            for offset, place in ((0, origin), (2, origin+2), (2, origin if length == 44 and rate == 48000 else origin+3)):
                check(rate, fps, origin, length, offset, place, "anull")
        for fps in (Fraction(25), Fraction(50), Fraction(120)):
            check(48000, fps, 1, 61, 2, 4, "aecho=0.8:0.9:250:0.4", marked=False)
        # Opposite signed phase seams prevent a positive-only allowance from
        # silently accepting a genuine five-seconds-plus-one native DSP tail.
        check(44100, Fraction(60000,1001), 3, 44, 2, 6, "aecho=0.8:0.9:5000:0.4", cap=True)
        check(44100, Fraction(30000,1001), 1, 16, 2, 4, "aecho=0.8:0.9:5000:0.4", cap=True)
        assert len(report["cases"]) == 26 and len(report["refusals"]) == 7
        assert {c["native_phase"] for c in report["cases"][-2:]} == {-1, 2}
        assert any(c["actual_cache_frames"] == c["destination_authored_body"]-2 for c in report["cases"])
        assert all(sha(p) == value for p, value in source_hashes.items())
        assert all(sha(p) == value for p, value in bound.items())
        report.update(passed=True, workers_joined=True, owned_cache_cleanup=True, source_immutable=True,
                      source_sha256=source_hashes, pcm16_values=sum(c["pcm16_values"] for c in report["cases"]))
    except BaseException as e:
        report.update(error=str(e), traceback=traceback.format_exc())
        raise
    finally:
        with report_path.open("x", encoding="utf8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
    print(json.dumps(dict(passed=report["passed"], cases=len(report["cases"]), refusals=len(report["refusals"]),
                          pcm16_values=report["pcm16_values"], report=str(report_path))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    run(args.worker.resolve(), args.report)
