"""NESTPEAK: exact streamed direct-clip peaks and unchanged cached-bus oracle.

Independent sample-coded stereo, exact floor partitions, scalar envelopes and
headroom provide the numerical oracle. Cached RF64 output is a separate parity
check, not the expected signal. No source or installed payload is modified.
"""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile

from audio_stream import wire
from nested_waveforms import Worker, float_wav

SR=48000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peaks(values,buckets):
    frames=len(values)//2
    return array("f",[max((abs(values[2*n+c]) for n in range(k*frames//buckets,(k+1)*frames//buckets)
                           for c in (0,1)),default=0.) for k in range(buckets)])


def read(path):
    values=array("f");values.frombytes(path.read_bytes())
    return values


def definition(source,frames,start=16001,gain=1.75,fade_in=.07,fade_out=.19,duration=None,chain="-"):
    length=frames/SR
    duration=length if duration is None else duration
    leaf=f"NESTLEAF bus.leaf bus {start} {start+frames} {wire(source)} 0 {duration:.17g} {gain:.17g} {fade_in:.17g} {fade_out:.17g} {length:.17g} {chain}"
    bus=f"NESTBUS bus - {start} {start+frames} {start} {start+frames} 1 0 0 {length:.17g} -"
    return leaf,bus


def define(process,cache,rows):
    process.command(f"NESTBEGIN {wire(cache)}")
    for row in rows:process.command(row)


def independent(values,frames,gain,fi,fo):
    out=array("f",values[:frames*2])
    out.extend([0.]*(frames*2-len(out)))
    gain=struct.unpack("<f",struct.pack("<f",gain))[0]
    for n in range(frames):
        local=n/SR
        envelope=1.
        if fi and local<fi:envelope*=max(0.,local/fi)
        if fo and local>=frames/SR-fo:envelope*=min(1.,max(0.,(frames/SR-local)/fo))
        env=struct.unpack("<f",struct.pack("<f",envelope))[0]
        applied=struct.unpack("<f",struct.pack("<f",gain*env))[0]
        out[2*n]*=applied;out[2*n+1]*=applied
    return out


def run(root,worker):
    source=root/"sample coded stereo 日本語 %20.wav"
    frames=240013 # Crosses the actual five-second native read boundary.
    values=array("f")
    for n in range(frames):
        values.extend((((n*73)%257-128)/80.,((n*31)%251-125)/96.))
    float_wav(source,values)
    original=sha(source)
    cases=[]
    for label,total,gain,fi,fo in (("headroom-fades",frames,1.75,.07,.19),
                                  ("source-eof-padding",frames+73,.625,0.,.13),
                                  ("authored-truncation",frames-61,1.,0.,0.),
                                  ("tiny-empty-buckets",7,1.,0.,0.)):
        rows=definition(source,total,gain=gain,fade_in=fi,fade_out=fo)
        wanted=independent(values,total,gain,fi,fo)
        stream_cache=root/(label+" stream");stream_cache.mkdir()
        old_cache=root/(label+" cached");old_cache.mkdir()
        streamed=Worker(worker);cached=Worker(worker)
        try:
            define(cached,old_cache,rows);cached.command("NESTCOMMIT")
            assert len(list(old_cache.glob("*.rf64")))==3,"Cached oracle did not exercise all three complete bodies"
            for count in (1,600,25567,65536):
                output=stream_cache/f"peak-{count}.f32"
                reference=old_cache/f"peak-{count}.f32"
                define(streamed,stream_cache,rows)
                trace=streamed.command(f"NESTPEAK bus {count} {wire(output)}")
                assert any("GA_AUDIO_CLIP_ENV_STREAM_STATS" in line for line in trace),trace
                assert not list(stream_cache.glob("*.rf64")),"Stream created intermediate RF64"
                assert not list(stream_cache.glob("*.active")),"Completed stream retained trace marker"
                cached.command(f"NESTENV bus {count} {wire(reference)}")
                actual=read(output);old=read(reference);expected=peaks(wanted,count)
                error=max(abs(a-b) for a,b in zip(actual,expected))
                assert len(actual)==len(old)==len(expected)==count
                assert error<=2e-6,(label,count,error)
                assert actual==old,(label,count,"Changed cached-bus peak bytes")
                cases.append(dict(name=label,buckets=count,frames=total,maximum_independent_error=error,
                                  cached_peak_bytes_exact=True,intermediate_rf64_absent=True))
        finally:streamed.close();cached.close()
        assert not list(old_cache.glob("*.rf64")),"Cached oracle survived worker close"
    # Keep an accepted real cached tree during malformed streamed transactions.
    # Every refusal must preserve it and recover in the SAME retained worker.
    cache=root/"refusal retained cache";cache.mkdir()
    process=Worker(worker)
    refusal=[]
    valid=definition(source,7,gain=1.,fade_in=0.,fade_out=0.)
    outside=root/"outside.f32";outside.write_bytes(b"outside immutable")
    existing=cache/"existing.f32"
    invalid_source=root/"nonfinite authored float.wav"
    float_wav(invalid_source,array("f",[.25,-.75,float("nan"),.5]*4))
    try:
        define(process,cache,valid);process.command("NESTCOMMIT")
        existing.write_bytes(b"existing immutable")
        bad=[("zero",valid,"bus",0,cache/"zero.f32","GA_AUDIO_CLIP_ENV_STREAM"),
             ("excess",valid,"bus",65537,cache/"excess.f32","GA_AUDIO_CLIP_ENV_STREAM"),
             ("unknown",valid,"missing",3,cache/"unknown.f32","GA_AUDIO_CLIP_ENV_STREAM"),
             ("wrapper-gain",(valid[0],valid[1].replace(" 1 0 0 "," .5 0 0 ")),"bus",3,cache/"gain.f32","GA_AUDIO_CLIP_ENV_STREAM"),
             ("missing-wrapper",valid[:1],"bus",3,cache/"missing.f32","GA_AUDIO_CLIP_ENV_STREAM"),
             ("existing",valid,"bus",3,existing,"GA_AUDIO_NESTED_ENV"),
             ("outside",valid,"bus",3,outside,"GA_AUDIO_NESTED_ENV"),
             ("missing-source",definition(root/"missing.wav",7),"bus",3,cache/"source.f32","GA_AUDIO_NESTED_RENDER"),
             ("nonfinite-source",definition(invalid_source,7),"bus",3,cache/"nonfinite.f32","GA_AUDIO_NESTED_CACHE"),
             ("wrapper-filter",(valid[0],valid[1][:-1]+"volume=.5"),"bus",3,cache/"filter.f32","GA_AUDIO_CLIP_ENV_STREAM"),
             ("different-domain",(valid[0],valid[1].replace("16001 16008 16001 16008","16001 16009 16001 16009")),"bus",3,cache/"domain.f32","GA_AUDIO_CLIP_ENV_STREAM")]
        for index,(label,rows,node,buckets,out,code) in enumerate(bad):
            before={p.name:sha(p) for p in cache.iterdir()}
            define(process,cache,rows)
            process.command(f"NESTPEAK {node} {buckets} {wire(out)}",code)
            assert {p.name:sha(p) for p in cache.iterdir()}==before,(label,"Refusal changed retained data")
            assert outside.read_bytes()==b"outside immutable"
            recovered=cache/f"recovered-{index}.f32"
            define(process,cache,valid)
            process.command(f"NESTPEAK bus 3 {wire(recovered)}")
            old=cache/f"accepted-{index}.f32"
            process.command(f"NESTENV bus 3 {wire(old)}")
            assert read(recovered)==read(old)==peaks(values[:14],3)
            refusal.append(dict(name=label,code=code,accepted_cache_unchanged=True,same_process_recovery=True))
    finally:process.close()
    assert sha(source)==original
    return dict(cases=cases,refusals=refusal,source_immutable=True,peak_threshold=2e-6,
                exact_floor_partitions=True,no_codec_bundle=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    worker=args.worker.resolve()
    report=dict(passed=False,worker_sha256=sha(worker))
    prior={key:os.environ.get(key) for key in ("GENESIS_NESTED_PROFILE","GENESIS_CLIP_ENV_TRACE")}
    os.environ.update(GENESIS_NESTED_PROFILE="1",GENESIS_CLIP_ENV_TRACE="1")
    try:
        with tempfile.TemporaryDirectory(prefix="genesis-stream-peaks-") as temp:
            report.update(run(Path(temp),worker))
        assert sha(worker)==report["worker_sha256"]
        report["passed"]=True
        print(f"Streamed direct peaks: {len(report['cases'])} numerical cases, {len(report['refusals'])} coded refusals; cached bytes exact; no RF64 intermediates")
    finally:
        for key,value in prior.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":main()
