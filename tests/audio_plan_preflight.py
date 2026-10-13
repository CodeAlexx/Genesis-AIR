"""Authored audio contexts must refuse before publishing misleading silence/static DSP.

The AIR client loads independent saved projects, checks all planning entry points,
then exercises actual audition, retained PCM and export. PCM references originate
in the authored stereo WAV; no Genesis output is an oracle input.
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
import wave
from audio_mix_project import document
from audio_nested import authored, effect, keys
from media_runtime import tool

FLAGS = 0x08000000 if os.name == "nt" else 0
AUTO = "GA_AUDIO_AUTOMATION_UNSUPPORTED"
OFFLINE = "GA_AUDIO_SOURCE_OFFLINE"
SR = 48000

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def cases(source, av=None):
    base = document([source], (0,))
    base["sources"][0].update(frames=60)
    base["program"].update(mark_in=0, mark_out=12)
    result = []
    def add(name, doc, expected="ACCEPT", clip=20, pcm="source", start=0, export=False, peak=None, source_status="ACCEPT"):
        result.append(dict(name=name, doc=doc, expected=expected, clip=clip, pcm=pcm,
                           start=start, export=export, peak=peak, source_status=source_status))
    add("valid-before", copy.deepcopy(base), export=True)
    pan = copy.deepcopy(base)
    keys(pan,20,2,"pan",[(-3,-1,2),(20,1,2)])
    add("direct-pan",pan,AUTO,export=True,peak=AUTO)
    for name, param in (("direct-speed","speed"),("direct-filter-speed","filter.50.speed.rate"),
                        ("direct-scoped-filter","filter.50.gain.level"),("direct-legacy-filter","gain.level")):
        doc = copy.deepcopy(base)
        if "filter-speed" in name:
            effect(doc,20,"speed",{"rate":1})
        elif "filter" in name:
            effect(doc,20,"gain",{"level":0})
        keys(doc,20,2,param,[(0,1,2),(6,2,2)])
        add(name,doc,AUTO,peak=AUTO)
    compressor=copy.deepcopy(base)
    effect(compressor,20,"compressor",dict(threshold=-14,ratio=4,attack=3,release=80))
    keys(compressor,20,2,"filter.50.compressor.threshold",[(-12,-30,2),(30,-6,2)])
    add("direct-compressor-curve",compressor,AUTO,peak=AUTO)
    for spelling in ("speed","filter.50.speed.rate","speed.rate"):
        doc=copy.deepcopy(base); doc["clips"][0]["speed"]=0
        if spelling!="speed": effect(doc,20,"speed",{"rate":1})
        keys(doc,20,2,spelling,[(0,0,4),(6,1,4)])
        add("held-"+spelling.replace(".","-"),doc,AUTO,peak=AUTO)
    held_muted=copy.deepcopy(result[-1]["doc"]); held_muted["tracks"][0]["muted"]=True
    add("held-speed-muted",held_muted,pcm="silence")
    held_noaudio=copy.deepcopy(result[-2]["doc"]); held_noaudio["sources"][0]["has_audio"]=False
    add("held-speed-noaudio",held_noaudio,pcm="silence")
    held_dormant=copy.deepcopy(result[-3]["doc"]); held_dormant["filters"][0]["enabled"]=False
    add("held-speed-disabled-filter",held_dormant,pcm="silence")
    offline=copy.deepcopy(base)
    offline["sources"][0]["online"]=False
    add("direct-offline",offline,OFFLINE,export=True,peak=OFFLINE,source_status=OFFLINE)
    for label, bad in (("key",pan),("offline",offline)):
        for state in ("disabled","muted","solo-excluded","held","no-audio","off-range","inactive","hidden","locked"):
            doc=copy.deepcopy(bad)
            expected="ACCEPT"; pcm="silence"; peak=None
            if state=="disabled": doc["clips"][0]["enabled"]=False
            elif state=="muted": doc["tracks"][0]["muted"]=True
            elif state=="solo-excluded": doc["tracks"].append(dict(doc["tracks"][0],id=4,solo=True,order=1))
            elif state=="held": doc["clips"][0]["speed"]=0
            elif state=="no-audio": doc["sources"][0]["has_audio"]=False
            elif state=="off-range": doc["clips"][0]["start"]=12
            elif state=="inactive":
                doc["sequences"].append(dict(doc["sequences"][0],id=10))
                doc["tracks"][0]["owner"]=10; doc["clips"][0]["owner"]=10
            else:
                doc["tracks"][0][state]=True; expected=AUTO if label=="key" else OFFLINE
                peak=expected; pcm=None
            add(label+"-"+state,doc,expected,pcm=pcm,peak=peak,
                source_status=OFFLINE if label=="offline" and state!="no-audio" else "ACCEPT")
            if state=="off-range": result[-1]["whole"]=AUTO if label=="key" else OFFLINE
    for state in ("disabled","orphan","foreign","picture"):
        doc=copy.deepcopy(base)
        effect(doc,20,"gain",{"level":0})
        if state=="disabled": doc["filters"][0]["enabled"]=False
        if state=="foreign": doc["filters"][0]["clip"]=999
        param="filter.999.gain.level" if state=="orphan" else "filter.50.gain.level"
        if state=="picture":
            doc["filters"][0]["kind"]="brightness"; param="filter.50.brightness.level"
            doc["tracks"][0]["kind"]=0
        keys(doc,20,2,param,[(0,0,2),(6,2,2)])
        add("dormant-"+state,doc,peak="ACCEPT")
    zero=copy.deepcopy(pan); zero["clips"][0]["gain"]=0
    keys(zero,20,2,"gain",[(0,1,4)])
    add("keyed-gain-replaces-zero",zero,AUTO,peak=AUTO)
    good=copy.deepcopy(base)
    keys(good,20,2,"gain",[(0,.25,2),(6,.75,4)])
    good["clips"][0].update(fade_in=3,fade_out=3)
    add("supported-gain-fades",good,pcm="gain-fades",peak="ACCEPT",export=True)
    nest=authored([source],root_fps=30,child_fps=60)
    nest["program"].update(mark_in=0,mark_out=12)
    nest["clips"][0]["length"]=120
    nest["clips"][-1]["length"]=12
    for scope in ("parent","child"):
        doc=copy.deepcopy(nest)
        clip_id=30 if scope=="parent" else 20
        owner=2 if scope=="parent" else 10
        effect(doc,clip_id,"gain",{"level":0})
        keys(doc,clip_id,owner,"filter.50.gain.level",[(0,0,2),(6,2,2)])
        add("nested-"+scope+"-key",doc,AUTO,clip=30,peak=AUTO,export=scope=="child")
    for scope in ("parent","child"):
        doc=copy.deepcopy(nest)
        target=doc["clips"][-1] if scope=="parent" else doc["clips"][0]
        target["speed"]=0
        keys(doc,target["id"],target["owner"],"speed",[(0,0,4),(6,1,4)])
        add("nested-held-"+scope+"-speed",doc,AUTO,clip=30,peak=AUTO)
    noff=copy.deepcopy(nest); noff["sources"][0]["online"]=False
    add("nested-child-offline",noff,OFFLINE,clip=30,peak=OFFLINE,source_status=OFFLINE)
    for suppressed in ("parent-muted","parent-disabled","child-muted","child-held"):
        doc=copy.deepcopy(noff)
        if suppressed=="parent-muted": doc["tracks"][0]["muted"]=True
        if suppressed=="parent-disabled": doc["clips"][-1]["enabled"]=False
        if suppressed=="child-muted": doc["tracks"][1]["muted"]=True
        if suppressed=="child-held": doc["clips"][0]["speed"]=0
        add("nested-"+suppressed,doc,clip=30,pcm="silence",source_status=OFFLINE)
    # Child source interval [0,.4); exact touching/offscreen leaf must be dormant.
    outside=copy.deepcopy(noff); outside["clips"][0].update(start=24,length=12)
    add("nested-touching-boundary",outside,clip=30,pcm="silence",source_status=OFFLINE,peak="ACCEPT")
    prior=copy.deepcopy(noff); prior["clips"][0].update(length=6)
    prior["clips"].insert(1,dict(prior["clips"][0],id=21,source=8,start=6,length=18))
    prior["sources"].append(dict(prior["sources"][0],id=8,online=True))
    add("nested-history-before-seek",prior,OFFLINE,clip=30,start=6,peak=OFFLINE,source_status=OFFLINE)
    if av is not None:
        legacy=copy.deepcopy(base)
        legacy["sources"][0].update(path=str(av),has_video=True,width=16,height=16)
        legacy["tracks"][0]["kind"]=0
        add("mask-legacy-both",legacy,export=True,peak="ACCEPT")
        result[-1]["picture_rgb"]=(45,90,135)
        paired=copy.deepcopy(legacy)
        paired["clips"][0].update(streams=1,group=99)
        paired["tracks"].append(dict(paired["tracks"][0],id=4,kind=1,name="A1"))
        paired["clips"].append(dict(paired["clips"][0],id=21,track=4,streams=2))
        add("mask-paired-once",paired,clip=21,export=True,peak="ACCEPT")
        result[-1]["picture_rgb"]=(45,90,135)
        muted=copy.deepcopy(paired); muted["tracks"][1]["muted"]=True
        add("mask-paired-audio-muted",muted,clip=21,pcm="silence",export=True)
        result[-1]["picture_rgb"]=(45,90,135)
        audioonly=copy.deepcopy(legacy); audioonly["clips"][0]["streams"]=2
        add("mask-audio-only-on-video-lane",audioonly,export=True,peak="ACCEPT")
        result[-1].update(picture_rgb=(0,0,0),picture_empty=True,filmstrip="GA_VIDEO_NESTED_PROTOCOL")
        picturebad=copy.deepcopy(audioonly)
        effect(picturebad,20,"lut3d",{})
        picturebad["filter_text_params"].append(dict(filter=50,name="path",value=str(source)+".missing.cube"))
        add("mask-audio-only-dormant-picture-lut",picturebad,peak="ACCEPT",export=True)
        result[-1].update(picture_rgb=(0,0,0),picture_empty=True,filmstrip="GA_VIDEO_NESTED_PROTOCOL")
        transition_only=copy.deepcopy(audioonly)
        transition_only["clips"][0]["length"]=6
        transition_only["clips"].append(dict(transition_only["clips"][0],id=21,start=6,source_in=6))
        transition_only["names"].append("unsupported-picture-transition")
        transition_only["transitions"].append(dict(id=60,owner=2,track=3,center=6,duration=12,kind=1))
        add("mask-audio-only-picture-transition",transition_only,export=True,peak="ACCEPT")
        result[-1].update(picture_rgb=(0,0,0),picture_empty=True,filmstrip="GA_VIDEO_NESTED_PROTOCOL")
        masked=copy.deepcopy(pan); masked["clips"][0]["streams"]=1
        add("mask-video-only-audio-key",masked,pcm="silence",peak="GA_AUDIO_CLIP_ENV")
        masked=copy.deepcopy(offline); masked["clips"][0]["streams"]=1
        add("mask-video-only-offline-audio",masked,pcm="silence",peak="GA_AUDIO_CLIP_ENV",source_status=OFFLINE)
        splitnested=copy.deepcopy(nest)
        splitnested["clips"][0]["streams"]=1
        splitnested["clips"].insert(1,dict(splitnested["clips"][0],id=21,streams=2,track=12))
        add("mask-nested-child-pair-once",splitnested,clip=30,peak="ACCEPT",export=True)
        result[-1]["picture_rgb"]=(0,0,0)
        parentoff=copy.deepcopy(noff); parentoff["clips"][-1]["streams"]=1
        add("mask-nested-video-parent-offline-leaf",parentoff,clip=30,pcm="silence",peak="GA_AUDIO_CLIP_ENV",source_status=OFFLINE)
        leafoff=copy.deepcopy(noff); leafoff["clips"][0]["streams"]=1
        add("mask-nested-video-leaf-offline",leafoff,clip=30,pcm="silence",peak="ACCEPT",source_status=OFFLINE)
    add("valid-after",copy.deepcopy(base),export=True,peak="ACCEPT")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--worker",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--expect-baseline",action="store_true")
    a=p.parse_args(); root=a.root.resolve(); root.mkdir(parents=True,exist_ok=False)
    source=root/"independent stereo Ã¦â€”Â¥Ã¦Å“Â¬Ã¨ÂªÅ¾.wav"
    values=array("h",(int(9000*math.sin(n*.017))+((n//137)%3)*800 for n in range(96000)))
    stereo=array("h")
    for n in range(96000): stereo.extend((values[n],-values[n]//2))
    with wave.open(str(source),"wb") as f:
        f.setparams((2,2,SR,0,"NONE","not compressed")); f.writeframes(stereo.tobytes())
    sourcehash=sha(source)
    av=root/"independent AV Ã¦â€”Â¥Ã¦Å“Â¬Ã¨ÂªÅ¾.mkv"
    raw=root/"independent RGB.rgb"
    raw.write_bytes(array("H",(45*257,90*257,135*257)).tobytes()*16*16*12)
    encoded=subprocess.run([str(tool(a.worker,"ffmpeg")),"-nostdin","-v","error","-f","rawvideo","-pixel_format","rgb48le",
                            "-video_size","16x16","-framerate","30","-i",str(raw),"-i",str(source),
                            "-map","0:v:0","-map","1:a:0","-c:v","ffv1","-pix_fmt","gbrp16le","-c:a","pcm_s16le",
                            str(av)],capture_output=True,timeout=30,creationflags=FLAGS)
    assert encoded.returncode==0,encoded.stderr
    decoded_source=subprocess.run([str(tool(a.worker,"ffmpeg")),"-nostdin","-v","error","-i",str(av),
                                  "-map","0:v:0","-f","rawvideo","-pix_fmt","rgb48le","pipe:1"],
                                 capture_output=True,timeout=30,creationflags=FLAGS)
    assert decoded_source.returncode==0 and decoded_source.stdout==raw.read_bytes(), "Independent native16 source authoring must be exact"
    avhash=sha(av); rawhash=sha(raw)
    authored_cases=cases(source,av); originals={}; manifest=[]; sentinels={}
    for case in authored_cases:
        name=case["name"]; file=root/(name+".air")
        file.write_text(json.dumps(case["doc"],ensure_ascii=False),encoding="utf-8"); originals[name]=sha(file)
        work=root/name; work.mkdir()
        # Sentinels are externally authored sidecars, never owned by this render.
        if case["export"] and case["expected"]!="ACCEPT":
            for suffix in (".nested-count",".prepared-count",".preclip0.rgba"):
                target=work/("refusal.mkv.genesis-air-part.mkv"+suffix)
                target.write_bytes(b"EXTERNAL SENTINEL\n"); sentinels[str(target)]=sha(target)
        manifest.append(f'{name}\t{case["clip"]}\t{case["start"]}\t12\t1\t{int(case["export"])}')
    (root/"cases.tsv").write_text("\n".join(manifest)+"\n",encoding="utf-8")
    env=dict(os.environ,GENESIS_FONT="C:/Windows/Fonts/segoeui.ttf")
    done=subprocess.run([str(a.binary.resolve()),str(a.worker.resolve()),str(root)],capture_output=True,env=env,
                        timeout=240,creationflags=FLAGS)
    (root/"native.log").write_bytes(done.stdout+done.stderr)
    assert done.returncode==0,(done.returncode,done.stdout[-3000:],done.stderr[-3000:])
    observed={}
    for line in (root/"observations.tsv").read_text(encoding="utf-8").splitlines():
        name,op,status=line.split("\t",2); observed.setdefault(name,{})[op]=status
    failures=[]; maximum=0.; master_maximum=0.; compared=0; master_compared=0
    def check(condition,label):
        if not condition: failures.append(label)
    for case in authored_cases:
        name=case["name"]; states=observed[name]; work=root/name
        check(states["immutable"]=="OK" and sha(root/(name+".air"))==originals[name],name+" immutable")
        for op in ("whole","range","audition","retained","export","source","peaks"):
            if op not in states: continue
            expect=case.get("whole",case["expected"]) if op in ("whole","audition") else case["expected"]
            if op=="source": expect=case["source_status"]
            if op=="peaks":
                if case["peak"] is None: continue
                expect=case["peak"]
            check(states[op] in ("OK","SILENT") if expect=="ACCEPT" else "["+expect+"]" in states[op],name+" "+op+" "+states[op])
        if case.get("picture_empty"):
            check(states["picture"]=="OK",name+" masked picture plan")
            commands=(work/"picture-plan.txt").read_text(encoding="utf-8")
            check("independent" not in commands and "CANVAS" not in commands,name+" no masked picture source/group")
        if case.get("filmstrip"):
            check("["+case["filmstrip"]+"]" in states["filmstrip"],name+" audio-only filmstrip refused")
        if case["expected"]!="ACCEPT" and case["expected"]==case.get("whole",case["expected"]):
            check(not any(work.glob("*.wav")),name+" refused PCM")
            check(not (work/"refusal.mkv").exists(),name+" refused export")
        if case["expected"]=="ACCEPT" and case["pcm"] is not None:
            f=work/"range.wav"
            check(f.is_file(),name+" retained silence/PCM file")
            if f.is_file():
                with wave.open(str(f),"rb") as audio:
                    check((audio.getnchannels(),audio.getsampwidth(),audio.getframerate())==(2,2,SR),name+" format")
                    actual=array("h",audio.readframes(audio.getnframes()))
                begin=case["start"]*1600; length=(12-case["start"])*1600
                expected=array("h",[0]*(2*length)) if case["pcm"]=="silence" else stereo[2*begin:2*(begin+length)]
                if case["pcm"]=="gain-fades":
                    expected=[v*(.25+.5*min(n//2,9600)/9600)*min(1,(n//2)/4800)*min(1,(19200-n//2)/4800)
                              for n,v in enumerate(expected)]
                check(len(actual)==len(expected),name+" exact count")
                err=max((abs(x-y) for x,y in zip(actual,expected)),default=0)
                maximum=max(maximum,err); compared+=len(actual)
                check(err<=1.0,name+" independent PCM "+str(err))
        if case["export"] and case["expected"]=="ACCEPT":
            output=work/"refusal.mkv"
            check(output.is_file(),name+" valid export recovery")
            if output.is_file():
                no_audible_root=name=="mask-paired-audio-muted"
                audio_streams=None
                if no_audible_root:
                    # This authored graph has video but no eligible audible root.
                    # Prove stream/packet absence before deciding whether to map audio.
                    probed=subprocess.run([str(tool(a.worker,"ffprobe")),"-v","error","-select_streams","a",
                                           "-show_streams","-show_packets","-of","json",str(output)],
                                          capture_output=True,timeout=30,creationflags=FLAGS)
                    check(probed.returncode==0,name+" independent absent-audio probe")
                    metadata=json.loads(probed.stdout)
                    check(isinstance(metadata,dict) and isinstance(metadata.get("streams"),list) and isinstance(metadata.get("packets"),list),name+" complete audio probe metadata")
                    audio_streams=metadata["streams"]
                    audio_packets=metadata["packets"]
                    check(not audio_packets,name+" no encoded audio sample packets")
                    check(all(row.get("codec_type")=="audio" for row in audio_streams),name+" selected audio stream metadata")
                actual=array("f")
                if not no_audible_root or audio_streams:
                    decoded=subprocess.run([str(tool(a.worker,"ffmpeg")),"-nostdin","-v","error","-i",str(output),
                                            "-map","0:a:0","-f","f32le","pipe:1"],capture_output=True,
                                           timeout=30,creationflags=FLAGS)
                    # A mapping/decode failure is always a failure, even for a zero-sample stream.
                    check(decoded.returncode==0,name+" independent lossless master decode")
                    actual.frombytes(decoded.stdout)
                expected=[] if no_audible_root else ([0.]*38400 if case["pcm"]=="silence" else [v/32768 for v in stereo[:38400]])
                if case["pcm"]=="gain-fades":
                    expected=[v*(.25+.5*min(n//2,9600)/9600)*min(1,(n//2)/4800)*min(1,(19200-n//2)/4800)
                              for n,v in enumerate(expected)]
                check(len(actual)==len(expected),name+" exact master sample count")
                error=max((abs(x-y) for x,y in zip(actual,expected)),default=0.)
                master_maximum=max(master_maximum,error); master_compared+=len(actual)
                check(error<=2e-6,name+" independent PCM24 master "+str(error))
                if "picture_rgb" in case:
                    picture=subprocess.run([str(tool(a.worker,"ffmpeg")),"-nostdin","-v","error","-i",str(output),
                                            "-map","0:v:0","-f","rawvideo","-pix_fmt","rgb48le","pipe:1"],
                                           capture_output=True,timeout=30,creationflags=FLAGS)
                    check(picture.returncode==0,name+" independent video decode")
                    pixels=array("H"); pixels.frombytes(picture.stdout)
                    check(len(pixels)==12*16*16*3,name+" exact masked picture frame count")
                    worst=max((abs(value-case["picture_rgb"][n%3]*257) for n,value in enumerate(pixels)),default=0.)
                    check(worst<=5,name+" authored picture coverage "+str(worst))
    sentinel_ok=all(Path(path).is_file() and sha(Path(path))==digest for path,digest in sentinels.items())
    check(sentinel_ok,"refusal preserves external sidecars")
    check(not list(root.rglob(".genesis-nested-*")),"owned caches cleaned")
    check(not list(root.rglob("*.genesis-air-part.mkv")),"owned export partials cleaned")
    check(sha(source)==sourcehash and sha(av)==avhash and sha(raw)==rawhash,"sources unchanged")
    result=dict(schema="genesis.audio-plan-preflight",cases=len(authored_cases),binary_sha256=sha(a.binary),
                worker_sha256=sha(a.worker),source_sha256=sourcehash,av_sha256=avhash,raw_rgb_sha256=rawhash,compared_pcm_values=compared,
                maximum_pcm_error=maximum,compared_master_values=master_compared,maximum_master_error=master_maximum,
                sentinels_preserved=sentinel_ok,failures=failures,passed=not failures,observations=observed)
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(result,indent=2),encoding="utf-8")
    if a.expect_baseline:
        assert all(observed[n]["range"]=="OK" for n in ("direct-pan","direct-scoped-filter","nested-child-key"))
        assert observed["direct-offline"]["range"]=="SILENT" and observed["direct-offline"]["source"]=="OK"
        print(f'Baseline reproduced {len(failures)} failures across {len(authored_cases)} authored cases')
    else:
        assert not failures,"\n".join(failures)
        print(f'Audio preflight PASS {len(authored_cases)} cases; {compared} PCM16 values max {maximum:.9f} codes; {master_compared} PCM24 values max {master_maximum:.12g}')

if __name__=="__main__": main()
