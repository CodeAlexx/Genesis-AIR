"""Compound filmstrip waveforms must describe the actual unclamped stereo bus.

Native client calls preview.waveforms and dumps the owned application cache;
neither application audition nor exported audio is an oracle. Authored PCM,
sample-domain placement, float sums and envelope ramps are independent inputs.
The shared command-line media tool is solely an offline DSP adapter on our own
float arrays. Legacy flat mono/DC controls retain their existing source envelope.
"""
import argparse
from array import array
import copy
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import struct
import subprocess
import tempfile
import threading
import time
import wave

from audio_nested import authored, curve, dsp, effect, f32, filter_chain, keys, points
from audio_source_boundaries import native_sample, output_sample, rate
from audio_stream import wire
from audio_nested_cancel import children, handle_alive, image, terminate_children, worker_handle

SR=48000
FLAGS=0x08000000 if os.name=="nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def float_wav(path,values,channels=2):
    payload=values.tobytes()
    fmt=struct.pack("<HHIIHH",3,channels,SR,SR*channels*4,channels*4,32)
    path.write_bytes(b"RIFF"+struct.pack("<I",36+len(payload))+b"WAVEfmt "+
                     struct.pack("<I",16)+fmt+b"data"+struct.pack("<I",len(payload))+payload)


def source_files(root):
    values=[]
    coded=array("f")
    amplitudes=(.0625,.3125,.125,.5,.1875,.375,.25,.4375)
    for n in range(4*SR):
        level=amplitudes[(n//6000)%len(amplitudes)]
        coded.extend((level if n%5 else -level,level/2 if n%7 else -level/2))
    values.append(coded)
    values.append(array("f",[.8,.6]*(4*SR)))
    values.append(array("f",[-.8,-.6]*(4*SR)))
    values.append(array("f",[.75,-.75]*(4*SR)))
    values.append(array("f",[0.]*(8*SR)))
    values.append(array("f",[.25,.25]*(4*SR)))
    impulse=array("f",[0.]*(8*SR))
    for n in (37,799,1600,4801,12001,24009,36003,48007,96001):
        impulse[n*2]=.9375
        impulse[n*2+1]=-.8125
    values.append(impulse)
    paths=[]
    for n,data in enumerate(values):
        path=root/f"authored waveform {n} 日本語 %20.wav"
        if n==5:
            with wave.open(str(path),"wb") as output:
                output.setparams((1,2,SR,0,"NONE","PCM"))
                output.writeframes(array("h",[8192]*(4*SR)).tobytes())
        else:
            float_wav(path,data)
        paths.append(path)
    return paths,{7+n:data for n,data in enumerate(values)}


def fitted(values,count):
    return values[:count*2]+array("f",[0.]*(max(0,count*2-len(values))))


def clip_signal(doc,clip_id,sources,worker):
    """Full independent child sums, then each enclosing clip's DSP/envelopes."""
    seq={item["id"]:item for item in doc["sequences"]}
    tracks={item["id"]:item for item in doc["tracks"]}
    clips={item["id"]:item for item in doc["clips"]}
    memo={}

    def sequence(owner):
        if owner in memo:return memo[owner]
        fps=seq[owner]["fps"]
        children=[item for item in doc["clips"] if item["owner"]==owner]
        finish=max((item["start"]+item["length"] for item in children),default=0)
        out=array("f",[0.]*(output_sample(finish,fps)*2))
        solo=any(t["solo"] for t in tracks.values() if t["owner"]==owner)
        for item in children:
            track=tracks[item["track"]]
            if not item["enabled"] or track["muted"] or (solo and not track["solo"]):continue
            values=signal(item)
            at=output_sample(item["start"],fps)*2
            for k,value in enumerate(values):out[at+k]=f32(out[at+k]+value)
        memo[owner]=out
        return out

    def signal(clip):
        fps=seq[clip["owner"]]["fps"]
        speed=Fraction(str(clip["speed"]))
        # Held pictures have no progressing audio: preserve the owner's exact
        # clip interval as silence without reading descendants or running DSP.
        if speed==0:
            count=output_sample(clip["start"]+clip["length"],fps)-output_sample(clip["start"],fps)
            return array("f",[0.]*(count*2))
        seconds=Fraction(clip["source_in"])/rate(fps)
        duration=Fraction(clip["length"])*speed/rate(fps)
        if clip["nested"]:
            child=sequence(clip["nested"])
            begin=output_sample(clip["source_in"],fps)
            end=round_fraction((Fraction(clip["source_in"])+clip["length"]*speed)*SR/rate(fps))
            raw=fitted(child[begin*2:end*2],end-begin)
        else:
            begin=native_sample(seconds,SR)
            count=native_sample(duration,SR)
            raw=sources[clip["source"]][begin*2:(begin+count)*2]
        chain=[]
        if clip["reverse"]:chain.append("areverse")
        if speed!=1:chain.append(f"atempo={float(speed):.17g}")
        track=tracks[clip["track"]]
        for pan in (clip["pan"],track["pan"]):
            if pan:chain.append(f"stereotools=balance_out={pan:.17g}")
        chain+=filter_chain(doc,clip)
        values=dsp(worker,raw,",".join(chain))
        placement=output_sample(clip["start"],fps)
        count=output_sample(clip["start"]+clip["length"],fps)-placement
        values=fitted(values,count)
        gain_keys,fade_in,fade_out=(points(doc,clip,name) for name in ("gain","fade_in","fade_out"))
        for n in range(count):
            gain=f32(track["gain"]*max(0.,curve(gain_keys,placement+n,clip["start"],fps,clip["gain"])))
            incoming=max(0.,curve(fade_in,placement+n,clip["start"],fps,clip["fade_in"]))/fps
            outgoing=max(0.,curve(fade_out,placement+n,clip["start"],fps,clip["fade_out"]))/fps
            local=n/SR
            ramp=min(1.,max(0.,local/incoming)) if incoming else 1.
            if outgoing:ramp*=min(1.,max(0.,(clip["length"]/fps-local)/outgoing))
            gain=f32(gain*f32(ramp))
            for channel in (0,1):values[n*2+channel]=f32(values[n*2+channel]*gain)
        return values

    return signal(clips[clip_id])


def round_fraction(value):
    return math.floor(value+Fraction(1,2))


def buckets(values,count):
    frames=len(values)//2
    return [max((abs(x) for x in values[(k*frames//count)*2:((k+1)*frames//count)*2]),default=0.)
            for k in range(count)]


def cases(paths):
    base=authored(paths,30,30)
    for source in base["sources"]:source["frames"]=120
    result=[("nested-coded",base,30)]
    for name,source in (("stereo-antiphase",10),("single-sample-spikes",13),("digital-silence",11)):
        doc=copy.deepcopy(base);doc["clips"][0]["source"]=source
        result.append((name,doc,30))
    summed=copy.deepcopy(base)
    summed["clips"][0]["source"]=8
    summed["clips"].insert(1,dict(summed["clips"][0],id=21,source=8,track=12))
    result.append(("raw-headroom",summed,30))
    cancelled=copy.deepcopy(summed);cancelled["clips"][1]["source"]=9
    result.append(("child-sum-cancellation",cancelled,30))
    scaled=copy.deepcopy(summed);scaled["clips"][-1]["gain"]=.5
    result.append(("parent-gain-after-sum",scaled,30))
    pan=copy.deepcopy(base);pan["clips"][-1]["pan"]=.625
    pan["tracks"][0].update(gain=.75,pan=-.25)
    result.append(("parent-track-gain-pan",pan,30))
    fades=copy.deepcopy(base);fades["clips"][-1].update(fade_in=9,fade_out=12)
    result.append(("overlapping-parent-fades",fades,30))
    automated=copy.deepcopy(base)
    keys(automated,20,10,"gain",[(-2,.1,2),(0,.2,2),(12,.8,4),(40,.3,2),(119,.5,2)])
    keys(automated,30,2,"fade_in",[(-3,10.,2),(0,8.,2),(12,0.,4),(23,0.,4)])
    result.append(("child-and-parent-automation",automated,30))
    for name,backwards,speed in (("trim",False,1),("reverse",True,1),("rate125",False,1.25),("reverse-rate2",True,2)):
        doc=copy.deepcopy(base);doc["clips"][-1].update(start=3,source_in=4,reverse=backwards,speed=speed)
        result.append((name,doc,30))
    fractional=authored(paths,60000/1001,24)
    for source in fractional["sources"]:source["frames"]=120
    fractional["clips"][0].update(start=2,source_in=3,length=72)
    fractional["clips"][-1].update(start=3,source_in=11,length=47)
    result.append(("fractional-owner-child-fps",fractional,30))
    held=copy.deepcopy(fractional)
    held["clips"][-1].update(speed=0,reverse=True,gain=2)
    result.append(("held-compound-silence",held,30))
    muted=copy.deepcopy(summed);muted["tracks"][1]["muted"]=True
    result.append(("child-track-muted",muted,30))
    solo=copy.deepcopy(summed);solo["tracks"][2].update(solo=True,gain=.25)
    result.append(("child-track-solo",solo,30))
    nonlinear=copy.deepcopy(summed)
    effect(nonlinear,30,"compressor",dict(threshold=-6.020599913279624,ratio=4,attack=.01,release=50))
    result.append(("parent-compressor-on-child-sum",nonlinear,30))
    repeated=copy.deepcopy(base)
    repeated["clips"][-1].update(source_in=0,length=12)
    repeated["clips"].append(dict(repeated["clips"][-1],id=31,start=12,source_in=18,gain=.25))
    result.extend((("repeated-instance-first",repeated,30),("repeated-instance-second",copy.deepcopy(repeated),31)))
    for name,source in (("flat-mono-dc",12),("flat-silence",11)):
        doc=copy.deepcopy(base)
        doc["clips"]=[dict(doc["clips"][-1],id=20,nested=0,source=source,source_in=6)]
        if source==12:doc["sources"][5]["audio_channels"]=1
        result.append((name,doc,20))
    return result


def read_cache(path):
    lines=path.read_text(encoding="utf-8").splitlines()
    version2=bool(lines and lines[0].split("\t")[0]=="WAVEFORMS 2")
    rows={}
    for line in lines[1:] if version2 else lines:
        if not line:continue
        fields=line.split("\t")
        metadata=7 if version2 else 6
        assert len(fields)>metadata,(path,"No waveform bucket payload")
        ident,source,length,first,last,revision=map(int,fields[:6])
        peaks=list(map(float,fields[metadata:]))
        assert all(math.isfinite(x) and x>=0 for x in peaks),(path,"Nonfinite/negative cache peaks")
        assert ident not in rows,(path,"Duplicate waveform clip")
        rows[ident]=dict(source=source,length=length,first=first,last=last,revision=revision,
                         document_revision=int(fields[6]) if version2 else None,peaks=peaks)
    return version2,rows


class Worker:
    def __init__(self,path):
        self.process=subprocess.Popen([str(path),"--serve"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",
                                      creationflags=FLAGS)
        self.lines=queue.Queue()
        def read():
            for line in self.process.stdout:self.lines.put(line.strip())
            self.lines.put(None)
        self.reader=threading.Thread(target=read,daemon=True)
        self.reader.start()

    def command(self,line,code=None):
        self.process.stdin.write(line+"\n");self.process.stdin.flush()
        deadline=time.monotonic()+30
        trace=[]
        while True:
            result=self.lines.get(timeout=max(.01,deadline-time.monotonic()))
            assert result is not None,(line,"Worker exited",trace)
            trace.append(result)
            if result=="ERR" or result.startswith("DONE"):
                assert (result=="ERR")==bool(code),(line,trace)
                if code:assert any("["+code+"]" in x for x in trace),(line,code,trace)
                return trace
            assert time.monotonic()<deadline,(line,"Worker deadline",trace)

    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill();self.process.wait(timeout=10)
            raise
        self.reader.join(timeout=2)
        assert self.process.returncode==0,self.process.returncode


def data_offset(payload):
    assert payload[:4] in (b"RIFF",b"RF64") and payload[8:12]==b"WAVE"
    at=12
    while at+8<=len(payload):
        name=payload[at:at+4]
        size=struct.unpack_from("<I",payload,at+4)[0]
        if name==b"data":return at+8
        at+=8+size+(size%2)
    raise AssertionError("No independently readable float WAV data chunk")


def protocol(root,worker):
    source=root/"tiny native stereo.wav"
    values=array("f",[.25,-.75,1.5,.125,-.5,.25,0.,0.,.75,-.125,-1.25,.375,.0625,-.5])
    float_wav(source,values)
    original=sha(source)
    cache=root/"private NESTENV 日本語 %20";cache.mkdir()
    process=Worker(worker)
    checks=[];refused=[];outputs=[]
    try:
        process.command(f"NESTBEGIN {wire(cache)}")
        process.command(f"NESTLEAF bus.leaf bus 0 7 {wire(source)} 0 {7/SR:.17g} 1 0 0 {7/SR:.17g} -")
        process.command(f"NESTBUS bus - 0 7 0 7 1 0 0 {7/SR:.17g} -")
        process.command("NESTCOMMIT")
        for count in (1,3,11,65536):
            path=cache/f"peaks-{count}.f32"
            process.command(f"NESTENV bus {count} {wire(path)}")
            actual=array("f");actual.frombytes(path.read_bytes())
            wanted=array("f",buckets(values,count))
            assert actual==wanted,("Exact stereo floor partition",count)
            outputs.append(path)
            checks.append(dict(buckets=count,native_frames=7,maximum=max(actual),every_float_exact=True))
        sentinel=cache/"sentinel.f32";sentinel.write_bytes(b"never overwrite")
        outside=root/"outside.f32";outside.write_bytes(b"outside remains unchanged")
        bad=[("missing-root",f"NESTENV missing 3 {wire(cache/'missing.f32')}"),
             ("nonroot",f"NESTENV bus.leaf 3 {wire(cache/'nonroot.f32')}"),
             ("zero-buckets",f"NESTENV bus 0 {wire(cache/'zero.f32')}"),
             ("excess-buckets",f"NESTENV bus 65537 {wire(cache/'excess.f32')}"),
             ("negative-buckets",f"NESTENV bus -1 {wire(cache/'negative.f32')}"),
             ("existing-output",f"NESTENV bus 3 {wire(sentinel)}"),
             ("outside-output",f"NESTENV bus 3 {wire(outside)}"),
             ("missing-field","NESTENV bus 3")]
        for name,command in bad:
            before={path.name:sha(path) for path in cache.iterdir()}
            process.command(command,"GA_AUDIO_NESTED_ENV")
            assert {path.name:sha(path) for path in cache.iterdir()}==before,(name,"Refusal mutated accepted cache")
            assert outside.read_bytes()==b"outside remains unchanged"
            refused.append(name)
        # Keep a pending transaction and prove refusal doesn't erase its state.
        process.command(f"NESTBEGIN {wire(cache)}")
        process.command(f"NESTLEAF bus.leaf bus 0 7 {wire(source)} 0 {7/SR:.17g} 1 0 0 {7/SR:.17g} -")
        process.command(f"NESTENV bus 3 {wire(cache/'pending.f32')}","GA_AUDIO_NESTED_ENV")
        process.command(f"NESTBUS bus - 0 7 0 7 1 0 0 {7/SR:.17g} -")
        process.command("NESTCOMMIT")
        refused.append("pending-transaction-preserved")
        original_caches={path:path.read_bytes() for path in cache.glob("*-output.rf64")}
        assert original_caches,"No owned processed cache to exercise corruption refusal"
        for label,mutation in (("nonfinite",None),("truncated",b"RF64")):
            for path,payload in original_caches.items():
                if mutation is None:
                    damaged=bytearray(payload)
                    struct.pack_into("<f",damaged,data_offset(payload),float("nan"))
                    path.write_bytes(damaged)
                else:path.write_bytes(payload[:data_offset(payload)+4])
            query=cache/(label+".f32")
            process.command(f"NESTENV bus 3 {wire(query)}","GA_AUDIO_NESTED_CACHE")
            assert not query.exists(),(label,"Partial refusal output published")
            for path,payload in original_caches.items():path.write_bytes(payload)
            recovered=cache/(label+"-recovery.f32")
            process.command(f"NESTENV bus 3 {wire(recovered)}")
            actual=array("f");actual.frombytes(recovered.read_bytes())
            assert actual==array("f",buckets(values,3)),label
            outputs.append(recovered)
            refused.append(label+"-cache-coded-and-recovery")
        assert sha(source)==original,"Authored source mutated during refusal"
    finally:process.close()
    assert not list(cache.glob("*.rf64")),"Worker-owned float cache survived close"
    assert all(path.is_file() for path in outputs),"Published envelope vanished before caller read"
    return dict(exact_bucket_cases=checks,refusals=refused,source_immutable=True,
                worker_cache_removed_after_close=True,published_peaks_survive_close=True)


def cancellation(root,client,worker,expected,env):
    source=root/"30-minute authored sparse silence.wav"
    byte_count=SR*1800*4
    with source.open("wb") as output:
        output.write(struct.pack("<4sI4s4sIHHIIHH4sI",b"RIFF",byte_count+36,b"WAVE",b"fmt ",16,
                                 1,2,SR,SR*4,4,16,b"data",byte_count))
        output.seek(44+byte_count-1);output.write(b"\0")
    before=sha(source)
    doc=authored([source],30,30)
    doc["sources"][0]["frames"]=1800*30
    doc["clips"][0]["length"]=1800*30
    doc["clips"][-1]["length"]=1800*30
    effect(doc,30,"compressor",dict(threshold=-12.,ratio=4,attack=.01,release=50))
    project=root/"cancel-long.air";project.write_text(json.dumps(doc),encoding="utf-8")
    project_before=sha(project)
    manifest=root/"cancel.tsv";manifest.write_text("cancel-long\t30\n",encoding="utf-8")
    result=[]
    for mode in ("superseded","stop"):
        signals=root/("signals-"+mode);signals.mkdir()
        marker=signals/"request.id";marker.write_text("17",encoding="utf-8")
        native=root/("cancel-native-"+mode)
        process=subprocess.Popen([str(client),str(native),str(worker),str(manifest),str(signals),"17"],
                                 env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=FLAGS)
        handle=None
        try:
            deadline=time.monotonic()+20
            witness=None
            while witness is None:
                assert process.poll() is None,(mode,"No actual cache warm before client exit")
                for candidate in native.rglob("*.rf64"):
                    if candidate.is_file() and candidate.stat().st_size>=80:
                        witness=candidate
                        break
                assert time.monotonic()<deadline,(mode,"Real audio cache warm deadline")
                if witness is None:time.sleep(.002)
            owned=[pid for pid in children(process.pid) if image(pid)==worker]
            assert len(owned)==1,(mode,"No unique live worker during real cache warm",owned)
            handle=worker_handle(owned[0])
            observed=witness.stat().st_size
            start=time.monotonic()
            if mode=="stop":(signals/"stop").write_text("stop",encoding="utf-8")
            else:marker.write_text("18",encoding="utf-8")
            stdout,stderr=process.communicate(timeout=10)
            elapsed=time.monotonic()-start
            error=(native/"cancel-long-error.txt").read_text(encoding="utf-8")
            assert process.returncode!=0 and "GA_AUDIO_STREAM_CANCELLED" in error,(mode,stdout,stderr,error)
            assert elapsed<=2.5,(mode,"Bounded cancellation+join",elapsed)
            assert not list(native.rglob(".genesis-nested-*")),(mode,"Owned cache survived canceled join")
            _,rows=read_cache(native/"cancel-long-waveforms.tsv")
            assert 30 not in rows,(mode,"Canceled partial peaks published")
            assert not handle_alive(handle),"Live retained owned worker after joined cancellation"
            result.append(dict(mode=mode,genuine_rf64_warm_bytes=observed,cancel_join_seconds=elapsed,
                               coded_refusal=error,partial_peaks_absent=True,cache_removed=True))
        finally:
            if process.poll() is None:
                (signals/"stop").write_text("stop",encoding="utf-8")
                try:process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate_children(process.pid,worker)
                    process.kill();process.communicate(timeout=5)
            if handle is not None and os.name=="nt":
                import ctypes
                from ctypes import wintypes
                kernel=ctypes.WinDLL("kernel32",use_last_error=True)
                kernel.CloseHandle.argtypes=[wintypes.HANDLE]
                kernel.CloseHandle(handle)
    assert sha(source)==before and sha(project)==project_before,"Canceled source/project changed"
    recovery=root/"recover.tsv";recovery.write_text("nested-coded\t30\n",encoding="utf-8")
    native=root/"recovery-native"
    done=subprocess.run([str(client),str(native),str(worker),str(recovery)],env=env,capture_output=True,
                        timeout=60,creationflags=FLAGS)
    assert done.returncode==0,("Fresh request after cancellation",done.stdout,done.stderr)
    _,rows=read_cache(native/"nested-coded-waveforms.tsv")
    actual=rows[30]["peaks"]
    assert len(actual)==len(expected) and max(abs(a-b) for a,b in zip(actual,expected))<=2/8388608
    assert not list(native.rglob(".genesis-nested-*")),"Recovery cache survived join"
    return dict(cases=result,fresh_recovery_independent_peaks=True,long_source_project_immutable=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--client",type=Path,required=True)
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--expect-missing",action="store_true",help="Record old nested omission while requiring flat controls")
    args=parser.parse_args()
    client,worker=args.client.resolve(),args.worker.resolve()
    report=dict(schema="genesis.nested_waveforms.v1",passed=False,client_sha256=sha(client),
                worker_sha256=sha(worker),oracle_sha256=sha(Path(__file__)),cases=[],scope=__doc__)
    try:
        with tempfile.TemporaryDirectory(prefix="genesis-nested-waveforms-") as temporary:
            root=Path(temporary)
            paths,source_values=source_files(root)
            original={path:sha(path) for path in paths}
            manifest=[];prepared=[]
            for name,doc,ident in cases(paths):
                path=root/(name+".air");path.write_text(json.dumps(doc),encoding="utf-8")
                original[path]=sha(path)
                clip=next(c for c in doc["clips"] if c["id"]==ident)
                count=max(8,min(512,max(8,clip["length"])//3))
                values=clip_signal(doc,ident,source_values,worker)
                wanted=buckets(values,count) if clip["nested"] else [.25 if name=="flat-mono-dc" else 0.]*count
                prepared.append((name,doc,ident,wanted,len(values)//2))
                manifest.append(f"{name}\t{ident}\n")
            manifest_file=root/"cases.tsv";manifest_file.write_text("".join(manifest),encoding="utf-8")
            env=dict(os.environ,GENESIS_GCOMPOSE=str(worker),GENESIS_SCRATCH=str(root/"state"))
            env.pop("GENESIS_FAKE_PROVIDER",None)
            done=subprocess.run([str(client),str(root/"native"),str(worker),str(manifest_file)],env=env,
                                capture_output=True,timeout=180,creationflags=FLAGS)
            report["client_stdout"]=done.stdout.decode("utf-8",errors="replace")
            report["client_stderr"]=done.stderr.decode("utf-8",errors="replace")
            assert done.returncode==0,(done.returncode,report["client_stdout"],report["client_stderr"])
            for name,doc,ident,wanted,samples in prepared:
                v2,rows=read_cache(root/"native"/(name+"-waveforms.tsv"))
                clip=next(c for c in doc["clips"] if c["id"]==ident)
                missing=ident not in rows
                check=dict(name=name,clip=ident,missing=missing,source_samples=samples,buckets=len(wanted))
                if missing:
                    assert args.expect_missing and clip["nested"],(name,"Expected processed compound waveform missing")
                else:
                    actual=rows[ident]
                    assert actual["source"]==clip["source"] and actual["length"]==clip["length"],(name,actual)
                    fps=next(s["fps"] for s in doc["sequences"] if s["id"]==clip["owner"])
                    target_fps=next(s["fps"] for s in doc["sequences"] if s["id"]==clip["nested"]) if clip["nested"] else 30
                    ends=[math.floor((Fraction(clip["source_in"])+pos*Fraction(str(clip["speed"]))) *rate(target_fps)/rate(fps))
                          for pos in ((clip["length"]-1,0) if clip["reverse"] else (0,clip["length"]-1))]
                    assert (actual["first"],actual["last"])==tuple(ends),(name,"Clip time endpoints",actual,ends)
                    assert len(actual["peaks"])==len(wanted),(name,"Bucket count")
                    maximum=max(abs(a-b) for a,b in zip(actual["peaks"],wanted))
                    assert maximum<=2/8388608,(name,"Independent stereo bucket maxima",maximum,actual["peaks"],wanted)
                    if clip["nested"]:assert v2 and actual["document_revision"] is not None
                    check.update(maximum_peak_error=maximum,maximum_peak=max(actual["peaks"]),metadata=actual)
                report["cases"].append(check)
            assert all(sha(path)==value for path,value in original.items()),"Source/project bytes changed"
            assert not list(root.rglob(".genesis-nested-*")),"Owned compound cache survived native join"
            assert sha(worker)==report["worker_sha256"] and sha(client)==report["client_sha256"],"Tested binaries changed"
            omitted=[row for row in report["cases"] if row["missing"]]
            if args.expect_missing:assert omitted,"Installed nested omission was not reproduced"
            else:
                suite=json.loads((root/"native/nested-waveforms-tests.json").read_text(encoding="utf-8"))["payload"]
                assert suite["status"]=="pass" and suite["cases"]["failed"]==0
                assert any("Descendant edits" in c["name"] for c in suite["case_details"]),"No actual stale/display oracle"
                report["native_publication_display_suite"]=suite
                report["protocol"]=protocol(root,worker)
                report["cancellation"]=cancellation(root,client,worker,prepared[0][3],env)
            report.update(passed=not omitted,expected_missing=args.expect_missing,
                          immutable_sources_projects_binaries=True,no_owned_cache_after_join=True)
    except BaseException as problem:
        report["failure"]=repr(problem)
        raise
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=report["passed"],cases=len(report["cases"]),
                         expected_missing=args.expect_missing)))


if __name__=="__main__":main()
