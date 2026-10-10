"""Source sample selection must survive coarse container PTS and fresh seeks.

PCM is independently authored and identical in WAV, NUT and Matroska. Native
selection rounds seconds to microseconds, then to native samples. Resampling
starts at that selected clip edge, preserving the existing public phase. A
retained stream slices its full resampled clip; a fresh forward flat seek starts
a fresh selected/resampled interval. A fresh reverse seek shortens the native
selected interval at its right edge before reversing; its new resampler EOF is
not the interior of the original interval. Nested seeks slice the cached bus.
No Genesis output is ever an oracle input. This is not a device timing test.
"""
import argparse
from array import array
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

from audio_mix_project import document
from audio_stream import pcm, wire
from media_runtime import tool

SR=48000
FLAGS=0x08000000 if os.name=="nt" else 0
OFFSETS=(0,1,3,5,7,11,17)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv,env=None,data=None):
    result=subprocess.run(list(map(str,argv)),env=env,input=data,capture_output=True,
                          timeout=180,creationflags=FLAGS)
    assert result.returncode==0,(argv,result.returncode,result.stdout[-4000:],result.stderr[-4000:])
    return result.stdout


def rate(value):
    return Fraction(60000,1001) if abs(value-60000/1001)<1e-8 else Fraction(str(value))


def nearest(value):
    return math.floor(value+Fraction(1,2))


def timestamp_sample(value):
    # Signed rational PTS projection rounds half a native sample away from zero.
    return nearest(value) if value>=0 else -nearest(-value)


def output_sample(frame,fps):
    return nearest(Fraction(frame)*SR/rate(fps))


def native_sample(seconds,native_rate):
    # The existing duration parser rounds to integer microseconds first.
    return nearest(Fraction(nearest(seconds*1000000))*native_rate/1000000)


def authored(native_rate):
    return array("h",(value for n in range(native_rate*4) for value in
                      (((n*73+(n//4096)*197)%20011)-10005,
                       ((n*131+(n//4096)*89)%16001)-8000)))


def sources(root,ffmpeg,ffprobe,native_rate):
    values=authored(native_rate)
    wav=root/f"sample coded {native_rate} 日本語.wav"
    with wave.open(str(wav),"wb") as output:
        output.setparams((2,2,native_rate,0,"NONE","not compressed"))
        output.writeframes(values.tobytes())
    results=[]
    for container in ("wav","nut","mkv"):
        path=wav if container=="wav" else root/f"sample coded {native_rate} 日本語.{container}"
        if path!=wav:
            run([ffmpeg,"-nostdin","-y","-v","error","-i",wav,
                 "-af","asetnsamples=n=4096:p=0","-c:a","pcm_s16le",path])
        independently_decoded=run([ffmpeg,"-nostdin","-v","error","-i",path,
                                  "-map","0:a:0","-f","s16le","pipe:1"])
        assert independently_decoded==values.tobytes(),("Authored PCM changed in container",container,native_rate)
        probe=json.loads(run([ffprobe,"-v","error","-select_streams","a:0","-show_streams",
                              "-show_packets","-of","json",path]))
        packet_counts=[int(packet["size"])//4 for packet in probe["packets"]]
        if container!="wav":
            assert packet_counts.count(4096)>=2,(container,packet_counts)
        results.append(dict(path=path,container=container,native_rate=native_rate,values=values,
                            time_base=probe["streams"][0]["time_base"],packet_frames=packet_counts,
                            full_decode_sha256=hashlib.sha256(independently_decoded).hexdigest()))
    assert results[-1]["time_base"]=="1/1000","Matroska must exercise coarse timestamps"
    return results


def timestamp_sources(root,ffmpeg,ffprobe,original):
    """Reference timeline comes from independently decoded native PCM and PTS.

    Positive first decoded PTS represents silence from asset time zero. A
    negative first decoded PTS contributes pre-zero samples which are skipped.
    AAC decoder skip/edit-list processing precedes this timeline projection.
    Packet timestamps are never substituted for decoded frame timestamps.
    """
    result=[]
    for codec,container,shift in (("pcm_s16le","nut",.5),("pcm_s16le","mkv",.5),
                                  ("pcm_s16le","mkv",-.125),("aac","m4a",0),
                                  ("aac","m4a",.25),("aac","m4a",-.125)):
        label=f"{container}-{codec}-pts{shift:g}"
        path=root/(label+"."+container)
        command=[ffmpeg,"-nostdin","-y","-v","error","-i",original["path"],
                 "-af",f"asetnsamples=n=4096:p=0,asetpts=PTS+({shift})/TB","-c:a",codec]
        if codec=="aac":command.extend(["-b:a","256k"])
        run(command+["-avoid_negative_ts","disabled",path])
        probe=json.loads(run([ffprobe,"-v","error","-select_streams","a:0","-show_streams",
                              "-show_frames","-show_packets","-of","json",path]))
        frames=probe.get("frames",[]) or [x for x in probe.get("packets_and_frames",[]) if x["type"]=="frame"]
        packets=probe.get("packets",[]) or [x for x in probe.get("packets_and_frames",[]) if x["type"]=="packet"]
        assert frames and "pts" in frames[0],("Independent decoded origin missing",label)
        native_rate=int(probe["streams"][0]["sample_rate"])
        origin=timestamp_sample(Fraction(int(frames[0]["pts"]))*Fraction(probe["streams"][0]["time_base"])*native_rate)
        decoded=array("f")
        decoded.frombytes(run([ffmpeg,"-nostdin","-v","error","-i",path,
                               "-map","0:a:0","-f","f32le","pipe:1"]))
        assert all(math.isfinite(x) for x in decoded)
        if codec=="pcm_s16le":
            assert decoded==array("f",(x/32768 for x in original["values"])),label
        values=(array("f",[0.]*(origin*2))+decoded) if origin>=0 else decoded[-origin*2:]
        result.append(dict(path=path,container=label,native_rate=native_rate,values=values,
                           time_base=probe["streams"][0]["time_base"],native_origin_sample=origin,
                           first_decoded_pts=frames[0]["pts"],first_packet_pts=packets[0].get("pts"),
                           decoded_frames=len(decoded)//2,codec=codec,
                           full_decode_sha256=hashlib.sha256(decoded.tobytes()).hexdigest()))
    assert result[0]["native_origin_sample"]==24000
    assert result[1]["native_origin_sample"]==24000
    assert result[2]["native_origin_sample"]==-6000
    assert result[3]["first_packet_pts"]<0 and result[3]["native_origin_sample"]==0,"AAC skip/edit-list fixture absent"
    assert result[4]["native_origin_sample"]>0,"AAC positive origin absent"
    assert result[5]["decoded_frames"]<result[3]["decoded_frames"],"Negative AAC edit-list trimming absent"
    return result


class Oracle:
    def __init__(self,ffmpeg):
        self.ffmpeg=ffmpeg
        self.cache={}

    def select(self,source,seconds,duration,out_rate=SR,mono=False):
        first=native_sample(seconds,source["native_rate"])
        count=native_sample(duration,source["native_rate"])
        assert first>=0 and count>0 and first+count<=len(source["values"])//2
        key=(source["full_decode_sha256"],source.get("native_origin_sample",0),first,count,out_rate,mono)
        if key not in self.cache:
            selected=source["values"][first*2:(first+count)*2]
            if mono:
                selected=array(source["values"].typecode,selected[::2])
            if source["native_rate"]==out_rate:
                decoded=array("f",(value/32768 if selected.typecode=="h" else value for value in selected))
            else:
                channels=1 if mono else 2
                payload=run([self.ffmpeg,"-nostdin","-v","error","-f","s16le" if selected.typecode=="h" else "f32le",
                             "-ar",source["native_rate"],"-ac",channels,"-i","pipe:0",
                             "-af",f"aresample={out_rate},aformat=sample_fmts=flt",
                             "-f","f32le","pipe:1"],data=selected.tobytes())
                decoded=array("f");decoded.frombytes(payload)
            assert all(math.isfinite(value) for value in decoded)
            self.cache[key]=decoded
        return array("f",self.cache[key])


def reverse(values):
    return array("f",(value for n in range(len(values)//2-1,-1,-1) for value in values[n*2:n*2+2]))


def fit(values,count):
    return values[:count*2]+array("f",[0.]*(max(0,count*2-len(values))))


def flat(source,offset,backwards=False,length=18):
    doc=document([source["path"]],(0,))
    doc["sources"][0].update(frames=120,audio_rate=source["native_rate"])
    doc["clips"][0].update(source_in=offset,length=length,reverse=backwards)
    return doc


def nested(source,parent_fps=30,child_fps=30,backwards=False):
    doc=flat(source,5)
    doc["sequences"][0]["fps"]=parent_fps
    doc["sequences"].append(dict(id=10,name="Child",fps=child_fps,width=16,height=16))
    doc["tracks"].append(dict(doc["tracks"][0],id=11,owner=10,name="Child A1"))
    doc["clips"][0].update(owner=10,track=11,start=1,source_in=5,length=72)
    doc["clips"].append(dict(doc["clips"][0],id=30,owner=2,track=3,source=0,nested=10,
                             start=2,source_in=3,length=18,reverse=backwards))
    doc["next_id"]=100
    return doc


def target(doc,source,oracle,seek=None):
    parent_fps=doc["sequences"][0]["fps"]
    if len(doc["sequences"])==1:
        clip=doc["clips"][0]
        seconds=Fraction(clip["source_in"])/rate(parent_fps)
        duration=Fraction(clip["length"])/rate(parent_fps)
        offset=0 if seek is None else seek
        if seek is not None:
            if not clip["reverse"]:
                seconds+=Fraction(seek)/rate(parent_fps)
            duration-=Fraction(seek)/rate(parent_fps)
            offset=0
        values=oracle.select(source,seconds,duration)
        if clip["reverse"]:
            values=reverse(values)
        values=values[output_sample(offset,parent_fps)*2:]
        return fit(values,output_sample(clip["length"],parent_fps)-output_sample(seek or 0,parent_fps))
    child_fps=doc["sequences"][1]["fps"]
    leaf,parent=doc["clips"]
    leaf_values=oracle.select(source,Fraction(leaf["source_in"])/rate(child_fps),
                             Fraction(leaf["length"])/rate(child_fps))
    child=array("f",[0.]*(output_sample(leaf["start"]+leaf["length"],child_fps)*2))
    at=output_sample(leaf["start"],child_fps)*2
    count=output_sample(leaf["start"]+leaf["length"],child_fps)-at//2
    child[at:at+count*2]=fit(leaf_values,count)
    first=output_sample(parent["source_in"],parent_fps)
    last=output_sample(parent["source_in"]+parent["length"],parent_fps)
    selected=child[first*2:last*2]
    if parent["reverse"]:
        selected=reverse(selected)
    count=output_sample(parent["start"]+parent["length"],parent_fps)-output_sample(parent["start"],parent_fps)
    out=array("f",[0.]*(output_sample(parent["start"]+parent["length"],parent_fps)*2))
    first=output_sample(parent["start"],parent_fps)*2
    out[first:first+count*2]=fit(selected,count)
    return out[output_sample(seek or 0,parent_fps)*2:]


def cases(all_sources,aligned_sources):
    # The existing native client's first case exercises descendant signature,
    # Undo/save-open and cleanup; keep a valid nested clip20 first.
    result=[("nested-first-48000-wav",nested(all_sources[0]),all_sources[0])]
    for source in all_sources:
        prefix=f"{source['native_rate']}-{source['container']}"
        for offset in OFFSETS:
            result.append((f"flat-{prefix}-offset{offset}",flat(source,offset),source))
        for offset in (1,5,17):
            result.append((f"reverse-{prefix}-offset{offset}",flat(source,offset,True),source))
        result.append((f"reverse-long-{prefix}",flat(source,1,True,96),source))
        for parent,child in ((24,30),(60000/1001,24)):
            for backwards in (False,True):
                result.append((f"nested-{prefix}-{parent:g}-{child:g}-{int(backwards)}",
                               nested(source,parent,child,backwards),source))
    for source in aligned_sources:
        for offset in (0,1,5,17):
            result.append((f"aligned-{source['container']}-offset{offset}",flat(source,offset),source))
        result.append((f"aligned-reverse-{source['container']}",flat(source,5,True),source))
        result.append((f"aligned-nested-{source['container']}",nested(source,60000/1001,24),source))
        if source["native_origin_sample"]>0:
            result.append((f"aligned-wholly-gap-{source['container']}",flat(source,0,length=3),source))
    return result


def difference(actual,wanted,label):
    if len(actual)!=len(wanted):
        return dict(passed=False,label=label,actual_frames=len(actual)//2,wanted_frames=len(wanted)//2,
                    failure="exact endpoint sample count")
    errors=[abs(a-b*32767) for a,b in zip(actual,wanted)]
    maximum=max(errors,default=0.)
    at=errors.index(maximum) if errors else 0
    return dict(passed=maximum<=1,label=label,frames=len(actual)//2,maximum_pcm_error=maximum,
                first_bad_sample=next((n//2 for n,value in enumerate(errors) if value>1),None),
                worst_sample=at//2,worst_channel=at%2,actual=actual[at] if actual else None,
                expected=wanted[at]*32767 if wanted else None)


def clipaud_checks(root,ffmpeg,worker,oracle):
    """Stateless alignment decoding uses independently authored mono sources.

    Testing every returned float, including the tail, distinguishes valid
    content from CLIPAUD's mandatory zero padding to its requested length.
    """
    commands=[]
    pending=[]
    for native_rate in (48000,44100):
        original=authored(native_rate)
        mono=array("h",original[::2])
        wav=root/f"mono-{native_rate}.wav"
        with wave.open(str(wav),"wb") as output:
            output.setparams((1,2,native_rate,0,"NONE","not compressed"))
            output.writeframes(mono.tobytes())
        for container,lead in (("wav",0),("nut",0),("mkv",0),("mkv",.5),("mkv",-.125)):
            path=wav if container=="wav" else root/f"mono-{native_rate}-{lead:g}.{container}"
            if path!=wav:
                run([ffmpeg,"-nostdin","-y","-v","error","-i",wav,
                     "-af",f"asetnsamples=n=4096:p=0,asetpts=PTS+({lead})/TB",
                     "-c:a","pcm_s16le","-avoid_negative_ts","disabled",path])
            # Exact authored shift values, rather than Genesis's origin probe.
            origin=timestamp_sample(Fraction(str(lead))*native_rate)
            values=(array("h",[0]*(origin*2))+original) if origin>=0 else original[-origin*2:]
            source=dict(native_rate=native_rate,values=values,native_origin_sample=origin,
                        full_decode_sha256=hashlib.sha256(original.tobytes()).hexdigest())
            intervals=[(offset,Fraction(3,5)) for offset in OFFSETS]
            if lead>0:intervals.append((0,Fraction(1,10)))
            for offset,duration in intervals:
                for out_rate in (8000,48000):
                    name=f"clipaud-{native_rate}-{container}-{lead:g}-{offset}-{float(duration):g}-{out_rate}"
                    out=root/(name+".f32")
                    count=nearest(duration*out_rate)
                    wanted=oracle.select(source,Fraction(offset,30),duration,out_rate,mono=True)
                    wanted=wanted[:count]+array("f",[0.]*(max(0,count-len(wanted))))
                    commands.append(f"CLIPAUD {wire(path)} {offset/30:.17g} {float(duration):.17g} {out_rate} {count} {wire(out)}")
                    pending.append((name,out,wanted))
    completed=subprocess.run([str(worker),"--serve"],input="\n".join(commands)+"\n",text=True,
                             encoding="utf-8",errors="replace",stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             timeout=120,creationflags=FLAGS)
    assert completed.returncode==0 and "ERR" not in completed.stdout,completed.stdout[-4000:]
    checks=[]
    for name,path,wanted in pending:
        actual=array("f");actual.frombytes(path.read_bytes())
        assert len(actual)==len(wanted) and all(math.isfinite(x) for x in actual),(name,"Invalid float output")
        errors=[abs(a-b) for a,b in zip(actual,wanted)]
        maximum=max(errors,default=0.)
        at=errors.index(maximum) if errors else 0
        checks.append(dict(name=name,label="CLIPAUD mono exact content and EOF",passed=maximum<=2/8388608,
                           frames=len(actual),maximum_float_error=maximum,worst_sample=at,
                           actual=actual[at],expected=wanted[at]))
    return checks


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--binary",type=Path,required=True)
    parser.add_argument("--client",type=Path,required=True)
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--expect-failure",action="store_true",help="Record installed defect without accepting sample errors")
    parser.add_argument("--core-only",action="store_true",help="Reproduce the original PCM container defect with all91cases; excludes additional origin/mono probes")
    args=parser.parse_args()
    binary,client,worker=(path.resolve() for path in (args.binary,args.client,args.worker))
    report=dict(schema="genesis.audio_source_boundaries.v1",passed=False,
                oracle_sha256=sha(Path(__file__)),
                binary_sha256=sha(binary),client_sha256=sha(client),worker_sha256=sha(worker),
                phase_contract=__doc__,cases=[],checks=[])
    try:
        with tempfile.TemporaryDirectory(prefix="genesis-audio-boundaries-") as temporary:
            root=Path(temporary)
            ffmpeg,ffprobe=tool(worker,"ffmpeg"),tool(worker,"ffprobe")
            all_sources=[source for native_rate in (48000,44100) for source in sources(root,ffmpeg,ffprobe,native_rate)]
            aligned_sources=[] if args.core_only else timestamp_sources(root,ffmpeg,ffprobe,all_sources[0])
            sources_under_test=all_sources+aligned_sources
            report["sources"]=[{key:value for key,value in source.items() if key not in ("path","values")}
                               for source in sources_under_test]
            source_hashes={source["path"]:sha(source["path"]) for source in sources_under_test}
            oracle=Oracle(ffmpeg)
            env=dict(os.environ,GENESIS_GCOMPOSE=str(worker),GENESIS_SCRATCH=str(root/"state"))
            env.pop("GENESIS_FAKE_PROVIDER",None)
            env.pop("GENESIS_SESSION_REPORT",None)
            manifest=[]
            prepared=[]
            for name,doc,source in cases(all_sources,aligned_sources):
                request=root/(name+".air")
                request.write_text(json.dumps(doc),encoding="utf-8")
                fps=doc["sequences"][0]["fps"]
                finish=max(item["start"]+item["length"] for item in doc["clips"] if item["owner"]==2)
                seek=min(5,finish-1)
                manifest.append(f"{name}\t0\t{finish}\t{seek}\n")
                wanted=target(doc,source,oracle)
                audition=root/(name+".wav")
                run([binary,"audio",audition,request],env)
                check=difference(pcm(audition),wanted,(name,"CLI whole"))
                check["name"]=name
                report["checks"].append(check)
                prepared.append((name,doc,source,sha(request),wanted,seek))
            (root/"cases.tsv").write_text("".join(manifest),encoding="utf-8")
            native_stdout=run([client,worker,root],env).decode("utf-8",errors="replace")
            report["native_model"]=(root/"native/model.tsv").read_text(encoding="utf-8")
            assert "stop_join_no_owned_cache\ttrue" in report["native_model"]
            for name,doc,source,original,wanted,seek in prepared:
                row=dict(name=name,native_rate=source["native_rate"],container=source["container"],checks=[])
                for suffix in ("whole","chunks","seek"):
                    values=array("h")
                    if suffix=="whole":
                        values=pcm(root/"native"/(name+"-whole.wav"))
                    else:
                        for path in sorted((root/"native").glob(name+"-"+suffix+"-*.wav"),
                                           key=lambda path:int(path.stem.rsplit("-",1)[1])):
                            values.extend(pcm(path))
                    expected=target(doc,source,oracle,seek) if suffix=="seek" else wanted
                    check=difference(values,expected,(name,suffix))
                    check["name"]=name
                    report["checks"].append(check)
                    row["checks"].append(check)
                assert sha(root/(name+".air"))==original,(name,"Project changed")
                report["cases"].append(row)
            if not args.core_only:
                report["checks"].extend(clipaud_checks(root,ffmpeg,worker,oracle))
            assert all(sha(path)==value for path,value in source_hashes.items()),"Authored source changed"
            assert not list(root.rglob(".genesis-nested-*")),"Owned cache survived Stop/join"
            assert sha(worker)==report["worker_sha256"],"Worker changed during acceptance gate"
            failures=[check for check in report["checks"] if not check["passed"]]
            report.update(sample_failures=len(failures),source_project_bytes_unchanged=True,
                          no_owned_cache_after_stop=True,native_case_count=len(prepared),
                          passed=not failures,expected_installed_failure=args.expect_failure,
                          core_only=args.core_only)
            if args.expect_failure:
                assert any("-mkv-" in check["name"] for check in failures),"Coarse Matroska defect was not reproduced"
                assert all(check["passed"] for check in report["checks"] if
                           check["name"].startswith("flat-48000-wav-")),"Known WAV forward control failed"
            else:
                assert not failures,("Exact source-selection regressions",failures[:10],len(failures))
    except BaseException as problem:
        report["failure"]=repr(problem)
        raise
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(dict(passed=report["passed"],cases=report["native_case_count"],
                         sample_failures=report["sample_failures"],expected_failure=args.expect_failure)))


if __name__=="__main__":
    main()
