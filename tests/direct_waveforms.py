"""Processed direct-source stereo peaks, independently authored in sample time.

Genesis audition/export is never the oracle. Native selected PCM, offline DSP,
raw gain/fade curves, exact owner sample endpoints and floor bucket partitions
produce the reference. The existing MM-AIR media tool is only the DSP adapter.
"""
import argparse
from array import array
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import struct
import time
import wave

from audio_nested import authored, effect, keys, f32, points, curve, filter_chain, run, floats
from fractions import Fraction
from media_runtime import tool
from nested_waveforms import source_files, clip_signal, read_cache
from audio_nested_cancel import children, handle_alive, image, terminate_children, worker_handle
from audio_source_boundaries import output_sample, native_sample, rate

FLAGS=0x08000000 if os.name=="nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def projects(paths):
    nested=authored(paths,30,30)
    base=copy.deepcopy(nested)
    base["sequences"]=base["sequences"][:1]
    base["tracks"]=base["tracks"][:1]
    base["clips"]=[dict(base["clips"][-1],source=10,nested=0,length=48,start=3)]
    result=[]
    def add(name,source=10,**values):
        doc=copy.deepcopy(base)
        doc["clips"][0].update(source=source,**values)
        result.append((name,doc,"ok"))
        return doc
    add("anti-phase")
    doc=add("mono-stereo-rematrix",12)
    doc["sources"][5]["audio_channels"]=1
    add("sparse-impulse",13,start=0,length=60)
    doc=add("fine-600",14,start=0,length=1800)
    doc["sequences"][0]["fps"]=60
    doc["sources"][-1].update(frames=1980,fps=60)
    add("headroom",10,gain=2)
    doc=add("clip-track-gain",7,gain=.375);doc["tracks"][0]["gain"]=.625
    add("clip-pan",7,pan=.5)
    doc=add("track-pan",7);doc["tracks"][0]["pan"]=-.5
    doc=add("double-pan",7,pan=-.25);doc["tracks"][0]["pan"]=.625
    add("trimmed",7,source_in=17,length=37)
    add("reverse",7,source_in=17,length=37,reverse=True)
    add("slow",7,source_in=5,length=60,speed=.5)
    add("fast",7,source_in=5,length=30,speed=2)
    add("fractional-rate",7,source_in=3,length=30,speed=1.5,reverse=True)
    for fps in (24,29.97,59.94):
        doc=add(f"owner-{fps}",7,start=7,source_in=17,length=37)
        doc["sequences"][0]["fps"]=fps
    add("scalar-fades",7,fade_in=25,fade_out=31)
    doc=add("fractional-scalar-fades",7,start=7,source_in=17,length=37,fade_in=13,fade_out=17)
    doc["sequences"][0]["fps"]=29.97
    add("overlapping-fades",7,length=24,fade_in=19,fade_out=20)
    doc=add("gain-keys",7,gain=.17)
    keys(doc,30,2,"gain",[(-3,.25,2),(7,1.75,2),(31,.375,4),(55,.875,2)])
    doc["tracks"][0]["gain"]=.75
    doc=add("fade-keys",7,fade_in=4,fade_out=6)
    keys(doc,30,2,"fade_in",[(-3,17,2),(11,5,2),(51,31,2)])
    keys(doc,30,2,"fade_out",[(-9,2,4),(21,24,2),(57,12,2)])
    doc=add("gain-fade-keys",7,start=7,source_in=11)
    doc["sequences"][0]["fps"]=29.97
    keys(doc,30,2,"gain",[(-7,.5,2),(17,1.5,2),(57,.25,2)])
    keys(doc,30,2,"fade_in",[(-3,25,2),(11,7,2),(51,19,2)])
    doc=add("compressor",7,gain=1.25)
    effect(doc,30,"compressor",dict(threshold=-14,ratio=4,attack=3,release=80))
    doc=add("delay-history",13,source_in=1,length=80,fade_in=3,fade_out=7)
    effect(doc,30,"delay",dict(time=35,decay=.5))
    add("held",7,speed=0,reverse=True,gain=2)
    add("disabled",7,enabled=False,gain=2)
    doc=add("muted-keyed",7)
    keys(doc,30,2,"gain",[(0,2,2),(48,1,2)])
    doc["tracks"][0]["muted"]=True
    doc=add("solo-excluded",7)
    doc["tracks"].append(dict(doc["tracks"][0],id=4,solo=True,order=1))
    for name,param in (("animated-pan","pan"),("animated-speed","speed"),
                       ("animated-effect","filter.50.compressor.threshold")):
        doc=add(name,7)
        if name=="animated-effect":
            effect(doc,30,"compressor",dict(threshold=-14,ratio=4,attack=3,release=80))
        keys(doc,30,2,param,[(0,0,2),(48,.5,2)])
        result[-1]=(name,doc,"GA_AUDIO_CLIP_ENV")
    doc=add("offline-source",7)
    doc["sources"][0]["online"]=False
    result[-1]=("offline-source",doc,"GA_AUDIO_CLIP_ENV")
    doc=add("invalid-rate",7,speed=17)
    result[-1]=("invalid-rate",doc,"GA_AUDIO_NESTED_PROTOCOL")
    return result


def peaks(values,count):
    frames=len(values)//2
    return [max((abs(values[n*2+c]) for n in range(k*frames//count,(k+1)*frames//count)
                 for c in (0,1)),default=0.) for k in range(count)]


def reference(doc,sources,worker):
    clip=doc["clips"][0]
    track=doc["tracks"][0]
    solo=any(t["solo"] for t in doc["tracks"] if t["owner"]==clip["owner"])
    fps=doc["sequences"][0]["fps"]
    count=output_sample(clip["start"]+clip["length"],fps)-output_sample(clip["start"],fps)
    if not clip["enabled"] or track["muted"] or (solo and not track["solo"]) or clip["speed"]==0:
        return array("f",[0.]*(count*2))
    source=next(s for s in doc["sources"] if s["id"]==clip["source"])
    # Decode the independently authored original container, not a repacketized
    # selected float pipe: atempo depends on input frame boundaries. Native
    # selection is before resampling and retains the decoder's source framing.
    speed=Fraction(str(clip["speed"]))
    begin=native_sample(Fraction(clip["source_in"])/rate(fps),48000)
    source_count=native_sample(Fraction(clip["length"])*speed/rate(fps),48000)
    chain=[f"atrim=start_sample={begin}:end_sample={begin+source_count}",
           "asetpts=N/SR/TB", "aresample=48000",
           "aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo"]
    if clip["reverse"]:chain.append("areverse")
    if speed!=1:chain.append(f"atempo={float(speed):.17g}")
    for pan in (clip["pan"],track["pan"]):
        if pan:chain.append(f"stereotools=balance_out={pan:.17g}")
    chain+=filter_chain(doc,clip)
    chain.append("aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo")
    values=floats(run([tool(worker,"ffmpeg"),"-nostdin","-v","error","-i",source["path"],
                      "-af",",".join(chain),"-f","f32le","pipe:1"]).stdout)
    values=values[:count*2]+array("f",[0.]*(max(0,count*2-len(values))))
    placement=output_sample(clip["start"],fps)
    gain_keys,fade_in,fade_out=(points(doc,clip,name) for name in ("gain","fade_in","fade_out"))
    for n in range(count):
        gain=f32(track["gain"]*max(0.,curve(gain_keys,placement+n,clip["start"],fps,clip["gain"])))
        incoming=max(0.,curve(fade_in,placement+n,clip["start"],fps,clip["fade_in"]))/fps
        outgoing=max(0.,curve(fade_out,placement+n,clip["start"],fps,clip["fade_out"]))/fps
        local=n/48000
        ramp=min(1.,max(0.,local/incoming)) if incoming else 1.
        if outgoing:ramp*=min(1.,max(0.,(clip["length"]/fps-local)/outgoing))
        gain=f32(gain*f32(ramp))
        for channel in (0,1):values[n*2+channel]=f32(values[n*2+channel]*gain)
    return values



def cancel_direct(root,client,worker,recovery_doc,recovery_peaks):
    source=root/"30-minute direct-source silence.wav"
    size=48000*1800*4
    with source.open("wb") as output:
        output.write(struct.pack("<4sI4s4sIHHIIHH4sI",b"RIFF",size+36,b"WAVE",b"fmt ",16,
                                 1,2,48000,192000,4,16,b"data",size))
        output.seek(44+size-1);output.write(b"\0")
    doc=copy.deepcopy(recovery_doc)
    doc["sources"]=[dict(doc["sources"][0],path=str(source),frames=54000)]
    doc["clips"][0].update(source=7,start=0,source_in=0,length=54000)
    effect(doc,30,"compressor",dict(threshold=-12,ratio=4,attack=.01,release=50))
    project=root/"cancel-direct.air";project.write_text(json.dumps(doc),encoding="utf-8")
    original=(sha(source),sha(project))
    manifest=root/"cancel-direct.tsv";manifest.write_text("cancel-direct\t30\tok\n",encoding="utf-8")
    result=[]
    for mode in ("superseded","stop"):
        signals=root/("signals-"+mode);signals.mkdir()
        marker=signals/"request.id";marker.write_text("17",encoding="utf-8")
        native=root/("cancel-native-"+mode)
        process=subprocess.Popen([str(client),str(native),str(worker),str(manifest),str(signals),"17"],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=FLAGS)
        handle=None
        try:
            deadline=time.monotonic()+20
            witness=None
            while witness is None:
                assert process.poll() is None,(mode,"Client exited before real cache warm")
                witness=next((p for p in native.rglob("*.rf64") if p.is_file() and p.stat().st_size>=80),None)
                assert time.monotonic()<deadline,(mode,"Cache warm deadline")
                if witness is None:time.sleep(.002)
            owned=[pid for pid in children(process.pid) if image(pid)==worker]
            assert len(owned)==1,(mode,"No unique live owned worker",owned)
            handle=worker_handle(owned[0])
            warm_bytes=witness.stat().st_size
            start=time.monotonic()
            if mode=="stop":(signals/"stop").write_text("stop",encoding="utf-8")
            else:marker.write_text("18",encoding="utf-8")
            stdout,stderr=process.communicate(timeout=10)
            elapsed=time.monotonic()-start
            error=(native/"cancel-direct-error.txt").read_text(encoding="utf-8")
            assert process.returncode!=0 and "GA_AUDIO_STREAM_CANCELLED" in error,(mode,error,stdout,stderr)
            assert elapsed<=2.5,(mode,"Cancellation+join bound",elapsed)
            assert not list(native.rglob(".genesis-nested-*")),(mode,"Cache survived cancellation")
            _,rows=read_cache(native/"cancel-direct-waveforms.tsv")
            assert 30 not in rows,(mode,"Partial waveform was published")
            assert not handle_alive(handle),(mode,"Worker survived confirmed join")
            result.append(dict(mode=mode,warm_rf64_bytes=warm_bytes,cancel_join_seconds=elapsed,
                               no_partial_peaks=True,owned_cache_removed=True,worker_joined=True))
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
    assert (sha(source),sha(project))==original,"Canceled source/project changed"
    manifest.write_text("anti-phase\t30\tok\n",encoding="utf-8")
    native=root/"recovery-native"
    done=subprocess.run([str(client),str(native),str(worker),str(manifest)],capture_output=True,
                        timeout=60,creationflags=FLAGS)
    assert done.returncode==0,("Fresh recovery request",done.stdout,done.stderr)
    _,rows=read_cache(native/"anti-phase-waveforms.tsv")
    actual=rows[30]["peaks"]
    assert len(actual)==len(recovery_peaks) and max(abs(a-b) for a,b in zip(actual,recovery_peaks))<=2e-6
    assert not list(native.rglob(".genesis-nested-*")),"Recovery cache survived joined request"
    return dict(cases=result,fresh_request_independent_peaks=True,sources_projects_immutable=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--client",type=Path,required=True)
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path)
    parser.add_argument("--skip-cancel",action="store_true")
    parser.add_argument("--baseline-client",type=Path)
    args=parser.parse_args()
    worker=args.worker.resolve()
    client=(args.baseline_client or args.client).resolve()
    report=dict(passed=False,worker_sha256=sha(worker),client_sha256=sha(client),cases=[],
                oracle="Independently authored original WAV decoder framing; native-sample atrim before stereo resampling/DSP; complete gain/fade curves; floor bucket partitions")
    with tempfile.TemporaryDirectory(prefix="genesis-direct-waveforms-") as temp:
        root=Path(temp)
        paths,sources=source_files(root)
        cases=projects(paths)
        before={str(p):sha(p) for p in paths}
        manifest=root/"direct.tsv"
        authored_files=[]
        expected={}
        for name,doc,code in cases:
            saved=root/(name+".air")
            saved.write_text(json.dumps(doc),encoding="utf-8")
            authored_files.append(saved)
            if code=="ok":expected[name]=reference(doc,sources,worker)
        before.update({str(p):sha(p) for p in authored_files})
        manifest.write_text("".join(f"{name}\t30"+("" if args.baseline_client else f"\t{code}")+"\n"
                                    for name,_,code in cases),encoding="utf-8")
        native=root/"native"
        try:
            done=subprocess.run([str(client),str(native),str(worker),str(manifest)],
                                capture_output=True,timeout=180,creationflags=FLAGS)
            report["client_exit"]=done.returncode
            report["client_stdout"]=done.stdout.decode("utf-8",errors="replace")
            report["client_stderr"]=done.stderr.decode("utf-8",errors="replace")
            errors=[]
            for name,doc,code in cases:
                error=(native/(name+"-error.txt")).read_text(encoding="utf-8")
                _,rows=read_cache(native/(name+"-waveforms.tsv"))
                if code!="ok":
                    passed=code in error and 30 not in rows
                    report["cases"].append(dict(name=name,passed=passed,refusal=code,
                                                no_approximate_publication=30 not in rows))
                    if not passed:errors.append((name,"Expected coded refusal",error))
                    continue
                clip=doc["clips"][0]
                buckets=max(8,min(512 if args.baseline_client else 65536,clip["length"]//3))
                target=peaks(expected[name],buckets)
                actual=rows.get(30,{}).get("peaks",[])
                maximum=max((abs(a-b) for a,b in zip(actual,target)),default=math.inf)
                passed=len(actual)==buckets and maximum<=2e-6 and not error
                pcm_error=None
                native_parity=None
                if not args.baseline_client:
                    actual_pcm=array("h")
                    rows_pcm=(native/name/"pulls.tsv").read_text(encoding="utf-8").splitlines()
                    fps=doc["sequences"][0]["fps"]
                    for row in rows_pcm:
                        filename,begin,finish=row.split("\t")
                        with wave.open(str(native/name/filename),"rb") as audio:
                            assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())==(2,2,48000)
                            assert audio.getnframes()==output_sample(int(finish),fps)-output_sample(int(begin),fps)
                            part=array("h");part.frombytes(audio.readframes(audio.getnframes()))
                            actual_pcm.extend(part)
                    assert len(actual_pcm)==len(expected[name]),(name,"Retained clip sample count",len(actual_pcm),len(expected[name]))
                    target_pcm=[int(max(-1.,min(1.,v))*32767) for v in expected[name]]
                    pcm_error=max(abs(a-b) for a,b in zip(actual_pcm,target_pcm))
                    if (native/name/"processed.wav").is_file():
                        with wave.open(str(native/name/"processed.wav"),"rb") as audio:
                            processed=array("h");processed.frombytes(audio.readframes(audio.getnframes()))
                        assert len(processed)==len(actual_pcm),(name,"Native processed/retained body count")
                        native_parity=max(abs(a-b) for a,b in zip(actual_pcm,processed))
                    passed=passed and pcm_error<=1 and (native_parity is None or native_parity<=1)
                report["cases"].append(dict(name=name,passed=passed,buckets=buckets,
                    sample_frames=len(expected[name])//2,maximum_peak_error=maximum,
                    maximum_peak=max(actual,default=0.),expected_maximum=max(target),
                    maximum_retained_pcm_error=pcm_error,maximum_native_bus_retained_error=native_parity,metadata=rows.get(30)))
                if not passed:errors.append((name,"Independent processed peak/retained PCM mismatch",maximum,pcm_error,error))
            report["cases_count"]=len(cases)
            report["errors"]=errors
            assert not errors,errors
            assert done.returncode==0,(done.returncode,report["client_stdout"],report["client_stderr"])
            assert not list(native.rglob(".genesis-nested-*")),"Owned cache survived joined command"
            if not args.skip_cancel:
                report["cancellation"]=cancel_direct(root,client,worker,cases[0][1],
                    peaks(expected["anti-phase"],max(8,min(65536,cases[0][1]["clips"][0]["length"]//3))))
            assert all(sha(Path(p))==digest for p,digest in before.items()),"Source/project mutation"
            assert sha(worker)==report["worker_sha256"] and sha(client)==report["client_sha256"]
            report.update(passed=True,sources_projects_binaries_immutable=True,owned_cache_removed=True,
                          peak_threshold=2e-6)
        finally:
            if args.report:
                args.report.parent.mkdir(parents=True,exist_ok=True)
                args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Direct stereo waveforms: {len(cases)} cases passed; maximum raw-float peak error {max(x.get('maximum_peak_error',0) for x in report['cases']):.9g}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
