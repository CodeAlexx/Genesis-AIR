"""Actual clipboard commands must preserve independently authored pictures/PCM.

The native helper produces a saved graph through Copy/Cut/Paste, Undo/Redo and
Save/Open. Expected media comes only from the original authored graph and source
samples. Shared FFmpeg supplies the declared tempo/pan DSP reference, never a
Genesis output. Title glyph raster is excluded from color math but its placement,
white coverage, exact content and parameters are separately required.
"""
import argparse
from array import array
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

from media_runtime import tool
from nested_picture import source, track, clip, project, SIZE, SOURCE_FRAMES, coded

SR = 48000
FPS = 30
DESTINATION = 30
FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, env=None, data=None):
    done = subprocess.run(list(map(str, argv)), env=env, input=data, capture_output=True,
                          timeout=120, creationflags=FLAGS)
    assert done.returncode == 0, (argv, done.returncode, done.stdout[-3000:], done.stderr[-3000:])
    return done.stdout


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def sample(frame):
    return math.floor(frame * SR / FPS + .5)


def add_filter(doc, owner, ident, kind, order, values=None, textual=None):
    doc["filters"].append(dict(id=ident, clip=owner, kind=kind, order=order, enabled=True))
    doc["filter_params"] += [dict(filter=ident, name=name, value=value)
                             for name, value in (values or {}).items()]
    doc["filter_text_params"] += [dict(filter=ident, name=name, value=value)
                                  for name, value in (textual or {}).items()]


def keys(doc, ident, owner, name, points):
    if name not in doc["names"]:
        doc["names"].append(name)
    doc["keys"] += [dict(clip=ident, owner=owner, param=doc["names"].index(name)+1,
                        frame=frame, value=value, interp=mode) for frame, value, mode in points]


def curve(doc, item, name, position, fallback):
    points = sorted((key for key in doc["keys"] if key["clip"] == item["id"] and
                     doc["names"][key["param"]-1] == name), key=lambda key: key["frame"])
    if not points:
        return fallback
    if position <= points[0]["frame"]:
        return points[0]["value"]
    for left, right in zip(points, points[1:]):
        if position < right["frame"]:
            if left["interp"] == 4:
                return left["value"]
            assert left["interp"] == 2, "Authored oracle uses only linear and Hold curves"
            return left["value"] + (right["value"]-left["value"]) * (position-left["frame"])/(right["frame"]-left["frame"])
    return points[-1]["value"]


def authored(sources):
    base = project(sources, FPS, FPS)
    base["tracks"] = [track(3,2,0), track(4,2,1)]
    base["tracks"][1].update(gain=.75, pan=0)
    base["clips"] = [clip(20,2,3,source=7,start=2,length=12,source_in=4)]
    base["clips"][0].update(speed=2, reverse=True, gain=.6, fade_in=2, fade_out=3)
    add_filter(base,20,50,"brightness",0,{"level":1.08})
    add_filter(base,20,51,"brightness",1,{"level":.98})
    add_filter(base,20,52,"contrast",2,{"level":1.05})
    add_filter(base,20,53,"gain",3,{"level":-6.0})
    add_filter(base,20,54,"text",4,{"size":200.,"x":0.,"y":0.},{"content":"COPY"})
    keys(base,20,2,"filter.50.brightness.level",[(-3,1.02,2),(5,1.08,2),(15,1.03,2)])
    keys(base,20,2,"filter.51.brightness.level",[(-2,.98,4),(6,1.02,4),(15,.96,4)])
    keys(base,20,2,"gain",[(-2,.5,2),(6,.75,2),(15,.25,2)])
    direct = ("copy-direct-reverse-rate-title",base,"copy")
    audio = copy.deepcopy(base)
    audio["tracks"][0]["kind"] = audio["tracks"][1]["kind"] = 1
    audio["tracks"][1]["pan"] = -.15
    audio["clips"][0].update(source=9,speed=1,pan=.3)
    audio["filters"] = [effect for effect in audio["filters"] if effect["kind"]=="gain"]
    audio["filters"][0]["order"] = 0  # Editor filter stacks have contiguous zero-based positions.
    audio["filter_params"] = [param for param in audio["filter_params"] if param["filter"]==53]
    audio["filter_text_params"] = []
    audio["keys"] = [key for key in audio["keys"] if audio["names"][key["param"]-1]=="gain"]
    audio_case = ("cut-audio-reverse-gain-pan",audio,"cut")
    nested = project(sources,FPS,FPS)
    nested["tracks"] = [track(3,2,0),track(4,2,1),track(11,10,0),track(12,10,1)]
    nested["tracks"][1]["gain"] = .75
    nested["tracks"][2]["gain"] = .5
    nested["tracks"][3]["gain"] = .25
    nested["clips"] = [clip(20,2,3,nested=10,start=2,length=12,source_in=4),
                        clip(40,10,11,source=7,length=64,source_in=1),
                        clip(41,10,12,source=8,length=64,source_in=2)]
    nested["clips"][0].update(speed=1.5,reverse=True,gain=.6,fade_in=2,fade_out=3)
    nested["clips"][1]["gain"] = .8
    nested["clips"][2]["gain"] = .4
    add_filter(nested,20,50,"contrast",0,{"level":1.3})
    add_filter(nested,40,51,"brightness",0,{"level":1.025})
    add_filter(nested,40,52,"contrast",1,{"level":1.1})
    keys(nested,41,10,"opacity",[(0,.3,4),(63,.3,4)])
    keys(nested,20,2,"gain",[(-2,.5,2),(6,.75,2),(15,.25,2)])
    single_grade = copy.deepcopy(nested)
    single_grade["filters"] = [effect for effect in single_grade["filters"] if effect["id"] != 52]
    single_grade["filter_params"] = [param for param in single_grade["filter_params"] if param["filter"] != 52]
    flat = project(sources,FPS,FPS)
    flat["tracks"] = [track(3,2,2),track(4,2,0),track(5,2,1)]
    flat["tracks"][1]["gain"] = .75
    flat["tracks"][2]["gain"] = .25
    flat["clips"] = [clip(20,2,3,source=7,start=2,length=12,source_in=4),
                     clip(30,2,5,source=8,start=DESTINATION,length=12,source_in=2)]
    flat["clips"][0].update(speed=1.5,reverse=True,gain=.6,fade_in=2,fade_out=3)
    flat["clips"][1]["gain"] = .4
    add_filter(flat,20,50,"brightness",0,{"level":1.025})
    keys(flat,30,2,"opacity",[(0,.3,4),(11,.3,4)])
    keys(flat,20,2,"gain",[(-2,.5,2),(6,.75,2),(15,.25,2)])
    fixtures = [direct,audio_case,("copy-compound-postgroup",nested,"copy"),
                ("copy-compound-single-grade",single_grade,"copy"),
                ("copy-flat-single-grade",flat,"copy")]
    for _, doc, _ in fixtures:
        for sequence in doc["sequences"]:
            sequence.update(width=SIZE[0], height=SIZE[1])
        # Native key lookup uses sorted (clip,param,frame) runs. Authored imports
        # must satisfy that schema invariant, exactly as controller writes do.
        doc["keys"].sort(key=lambda key:(key["clip"],key["param"],key["frame"]))
    return fixtures


def pasted_oracle(doc):
    wanted = copy.deepcopy(doc)
    selected = next(item for item in wanted["clips"] if item["id"]==20)
    selected.update(start=DESTINATION,track=4)
    # Original placement cannot intersect this private export body. Keeping the
    # original ID also leaves oracle scoped keys independent of copied new IDs.
    wanted["program"].update(frame=DESTINATION,mark_in=DESTINATION,mark_out=DESTINATION+selected["length"])
    return wanted


def picture(doc, source_colors, owner, frame):
    color = [0.,0.,0.]
    lanes = sorted((lane for lane in doc["tracks"] if lane["owner"]==owner),key=lambda lane:lane["order"])
    for lane in lanes:
        if lane["hidden"] or lane["kind"]!=0:
            continue
        for item in doc["clips"]:
            if item["track"]!=lane["id"] or not item["enabled"] or not item["start"]<=frame<item["start"]+item["length"]:
                continue
            local = frame-item["start"]
            position = item["length"]-1-local if item["reverse"] else local
            selected = math.floor(item["source_in"]+position*item["speed"])
            layer = picture(doc,source_colors,item["nested"],selected) if item["nested"] else [value/255 for value in source_colors[item["source"]][selected]]
            for effect in sorted((effect for effect in doc["filters"] if effect["clip"]==item["id"] and effect["enabled"]),key=lambda effect:effect["order"]):
                params = {entry["name"]:entry["value"] for entry in doc["filter_params"] if entry["filter"]==effect["id"]}
                if effect["kind"] in ("brightness","contrast"):
                    level = curve(doc,item,f"filter.{effect['id']}.{effect['kind']}.level",local,params["level"])
                    layer = [max(0.,min(1.,value+level-1)) if effect["kind"]=="brightness" else max(0.,min(1.,(value-.5)*level+.5)) for value in layer]
            alpha = curve(doc,item,"opacity",local,1.)
            if item["fade_in"]:
                alpha *= min(1.,local/item["fade_in"])
            if item["fade_out"]:
                alpha *= min(1.,(item["length"]-local)/item["fade_out"])
            color = [value*alpha+base*(1-alpha) for value,base in zip(layer,color)]
    return color


def pcm_oracle(doc, source_pcm, worker):
    memo = {}
    def sequence(owner):
        if owner in memo:
            return memo[owner]
        clips = [item for item in doc["clips"] if item["owner"]==owner]
        count = sample(max(item["start"]+item["length"] for item in clips))
        output = array("f",[0.]*(count*2))
        for item in clips:
            lane = next(lane for lane in doc["tracks"] if lane["id"]==item["track"])
            if not item["enabled"] or lane["muted"]:
                continue
            incoming = sequence(item["nested"]) if item["nested"] else source_pcm[item["source"]]
            first, end = sample(item["source_in"]),sample(item["source_in"]+item["length"]*item["speed"])
            raw = array("f",incoming[first*2:end*2])
            assert len(raw)==(end-first)*2
            chain = []
            if item["reverse"]:
                chain.append("areverse")
            if item["speed"]!=1:
                chain.append(f"atempo={item['speed']}")
            for balance in (item["pan"],lane["pan"]):
                if balance:
                    chain.append(f"stereotools=balance_out={balance}")
            for effect in sorted((effect for effect in doc["filters"] if effect["clip"]==item["id"] and effect["enabled"]),key=lambda effect:effect["order"]):
                if effect["kind"]=="gain":
                    gain = next(entry["value"] for entry in doc["filter_params"] if entry["filter"]==effect["id"] and entry["name"]=="level")
                    chain.append(f"volume={gain}dB")
            if chain:
                raw = array("f",run([tool(worker,"ffmpeg"),"-nostdin","-v","error","-f","f32le","-ar",SR,"-ac",2,"-i","pipe:0","-af",",".join(chain),"-f","f32le","pipe:1"],data=raw.tobytes()))
            count = sample(item["length"])
            raw = raw[:count*2]
            raw.extend([0.]*(count*2-len(raw)))
            placement = sample(item["start"])
            for n in range(count):
                local = n*FPS/SR
                gain = f32(f32(lane["gain"])*f32(max(0.,curve(doc,item,"gain",local,item["gain"]))))
                envelope = min(1.,local/item["fade_in"]) if item["fade_in"] else 1.
                if item["fade_out"]:
                    envelope *= min(1.,(item["length"]-local)/item["fade_out"])
                gain = f32(gain*f32(envelope))
                for channel in (0,1):
                    at = (placement+n)*2+channel
                    output[at] = f32(output[at]+f32(raw[n*2+channel]*gain))
        memo[owner] = output
        return output
    full = sequence(doc["active"])
    first = sample(DESTINATION)*2
    count = sample(12)*2
    return array("f",(max(-1.,min(1.,value)) for value in full[first:first+count]))


def graph_check(before, after, new_id, mode):
    original = next(item for item in before["clips"] if item["id"]==20)
    pasted = next(item for item in after["clips"] if item["id"]==new_id)
    for name in ("owner","source","nested","source_in","length","enabled","fade_in","fade_out","gain","pan","speed","reverse"):
        assert pasted[name]==original[name],("Copied scalar",name,pasted[name],original[name])
    assert new_id != original["id"], "Paste must allocate a fresh clip identity"
    assert (pasted["start"],pasted["track"],pasted["group"],pasted["selected"])==(DESTINATION,4,0,True)
    old = sorted((item for item in before["filters"] if item["clip"]==20),key=lambda item:item["order"])
    new = sorted((item for item in after["filters"] if item["clip"]==new_id),key=lambda item:item["order"])
    assert len(old)==len(new),("Copied filter count",len(old),len(new))
    mapping = {}
    for left,right in zip(old,new):
        assert right["id"] not in {effect["id"] for effect in before["filters"]}, "Paste must allocate fresh filter identities"
        assert left["id"]!=right["id"] and (left["kind"],left["order"],left["enabled"])==(right["kind"],right["order"],right["enabled"])
        mapping[left["id"]] = right["id"]
        for records in ("filter_params","filter_text_params"):
            a = sorted((item["name"],item["value"]) for item in before[records] if item["filter"]==left["id"])
            b = sorted((item["name"],item["value"]) for item in after[records] if item["filter"]==right["id"])
            assert a==b,(records,a,b)
    def key_records(doc,ident,rewrite=False):
        result=[]
        for key in doc["keys"]:
            if key["clip"]!=ident:
                continue
            name=doc["names"][key["param"]-1]
            if rewrite and name.startswith("filter."):
                fields=name.split(".")
                fields[1]=str(mapping[int(fields[1])])
                name=".".join(fields)
            result.append((name,key["frame"],key["value"],key["interp"]))
        return sorted(result)
    assert key_records(before,20,True)==key_records(after,new_id),"Full signed/off-body/scoped curve preservation"
    assert (mode=="cut") == (not any(item["id"]==20 for item in after["clips"]))
    if mode=="copy":
        assert next(item for item in after["clips"] if item["id"]==20)["gain"]==.125
    return pasted


def compare_picture(values, expected, scale, title=False, exclude_title=False):
    assert len(values)==SIZE[0]*SIZE[1]*3
    worst=0.
    white=[]
    for index in range(SIZE[0]*SIZE[1]):
        x,y=index%SIZE[0],index//SIZE[0]
        pixel=values[index*3:index*3+3]
        if (title or exclude_title) and 12<=x<52 and 5<=y<31:
            if min(pixel)>=scale*.98:
                white.append((x,y))
            continue
        worst=max(worst,max(abs(actual-wanted*scale) for actual,wanted in zip(pixel,expected)))
    assert worst <= (2 if scale==65535 else 1.1), ("Independent picture error",worst,expected)
    if title:
        assert len(white)>=8,("Missing intended white title",len(white))
        assert all(16<=x<49 and 7<=y<30 for x,y in white),("Mispositioned intended title",white)
        assert abs(sum(x for x,y in white)/len(white)-31.5)<10,"Title is not centered at authored x0"
    return worst,len(white)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--client",type=Path,required=True)
    parser.add_argument("--binary",type=Path,required=True)
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--work",type=Path)
    parser.add_argument("--expect-failure",action="store_true")
    args=parser.parse_args()
    client,binary,worker=(value.resolve() for value in (args.client,args.binary,args.worker))
    root=args.work.resolve() if args.work else Path(tempfile.mkdtemp(prefix="genesis-clipboard-media-"))
    if args.work:
        root.mkdir(parents=True,exist_ok=False)
    report=dict(schema="genesis.clipboard-media.v1",client_sha256=sha(client),app_sha256=sha(binary),
                worker_sha256=sha(worker),oracle_sha256=sha(Path(__file__)),work=str(root),cases=[],passed=False)
    try:
        ffmpeg=tool(worker,"ffmpeg")
        fonts=[Path("C:/Windows/Fonts/segoeuib.ttf"),Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
        font=next((face for face in fonts if face.is_file()),None)
        assert font is not None,"A known bold face is required for a solid-white title interior at this tiny legal size"
        report["title_font"]=dict(path=str(font),sha256=sha(font),legal_size=200,scope="Explicit bold face; no generic font raster equivalence claim")
        sources={7:source(root,ffmpeg,FPS,"clipboard source 日本語 %20",sound=True),
                 8:source(root,ffmpeg,FPS,"second source",color=(90,130,160),sound=True)}
        source_pcm={}
        for ident,info in sources.items():
            payload=run([ffmpeg,"-nostdin","-v","error","-i",info["path"],"-map","0:a:0","-f","f32le","pipe:1"])
            source_pcm[ident]=array("f",payload)
        sources[9]=dict(sources[7],path=root/"audio-only.wav")
        run([ffmpeg,"-nostdin","-v","error","-i",sources[7]["path"],"-map","0:a:0","-c:a","pcm_s16le",sources[9]["path"]])
        source_pcm[9]=array("f",source_pcm[7])
        fixtures=authored(sources)
        immutable={str(info["path"]):sha(info["path"]) for info in sources.values()}
        rows=[]
        for name,doc,mode in fixtures:
            for info in doc["sources"]:
                if info["id"]==9:
                    info.update(has_video=False,width=0,height=0)
            filename=root/f"{name}-input.air"
            filename.write_text(json.dumps(doc),encoding="utf-8")
            immutable[str(filename)]=sha(filename)
            rows.append(f"{name}\t{filename}\t20\t4\t{DESTINATION}\t{mode}")
        manifest=root/"cases.tsv"
        manifest.write_text("\n".join(rows)+"\n",encoding="utf-8")
        native=root/"native"
        env=dict(os.environ,GENESIS_GCOMPOSE=str(worker),GENESIS_SCRATCH=str(root/"scratch"),GENESIS_FONT=str(font))
        env.pop("GENESIS_FAKE_PROVIDER",None)
        env.pop("GENESIS_SESSION_REPORT",None)
        done=subprocess.run([str(client),str(native),str(worker),str(manifest)],env=env,capture_output=True,timeout=120,creationflags=FLAGS)
        (root/"native-client.log").write_bytes(done.stdout+done.stderr)
        report["native_exit"]=done.returncode
        # Even a failed baseline helper can publish outputs revealing lost content.
        colors={7:[coded(n) for n in range(SOURCE_FRAMES)],8:[(90,130,160)]*SOURCE_FRAMES}
        for name,doc,mode in fixtures:
            result=dict(name=name,passed=False)
            report["cases"].append(result)
            try:
                for operation in ("copy","paste"):
                    failure_file=native/f"{name}-{operation}-error.txt"
                    if failure_file.exists():
                        result["clipboard_refusal"]=dict(operation=operation,message=failure_file.read_text(encoding="utf-8"),nested=doc["clips"][0]["nested"])
                output=native/f"{name}.air"
                actual=json.loads(output.read_text(encoding="utf-8"))
                pasted_id=json.loads((native/f"{name}-id.json").read_text())["pasted_id"]
                try:
                    graph_check(doc,actual,pasted_id,mode)
                except Exception as failure:
                    result["graph_error"]=repr(failure)
                result["copied_graph_preserved"]="graph_error" not in result
                expected=pasted_oracle(doc)
                if name=="copy-compound-postgroup":
                    per_leaf = copy.deepcopy(expected)
                    per_leaf["filters"] = [effect for effect in per_leaf["filters"] if effect["clip"] != 20]
                    for child in per_leaf["clips"]:
                        if child["owner"] == 10:
                            add_filter(per_leaf,child["id"],2000+child["id"],"contrast",
                                       sum(effect["clip"]==child["id"] for effect in per_leaf["filters"]),{"level":1.3})
                    difference=max(abs(group-leaf) for local in range(12) for group,leaf in
                                   zip(picture(expected,colors,2,DESTINATION+local),picture(per_leaf,colors,2,DESTINATION+local)))
                    assert difference > .02,"Authored parent grade must distinguish postgroup from per-leaf clipping"
                    result["postgroup_vs_perleaf_difference"]=difference
                audition=root/f"{name}.wav"
                run([binary,"audio",audition,output],env)
                with wave.open(str(audition),"rb") as audio:
                    assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getnframes())==(2,2,SR,sample(12))
                    pcm=array("h",audio.readframes(audio.getnframes()))
                target=pcm_oracle(expected,source_pcm,worker)
                assert len(target)==len(pcm)
                error=max(abs(value-wanted*32767) for value,wanted in zip(pcm,target))
                result["audition_max_error_pcm16"]=error
                if error>1:
                    result["audition_error"]=repr(("Audition PCM error",error))
                movie=root/f"{name}.mkv"
                run([binary,"export",movie,output],env)
                payload=run([ffmpeg,"-nostdin","-v","error","-i",movie,"-map","0:v:0","-f","rawvideo","-pix_fmt","rgb48le","pipe:1"])
                frames=array("H",payload)
                assert len(frames)==12*SIZE[0]*SIZE[1]*3,"Lossless video frame count"
                pixel_error=0.
                title_count=0
                for local in range(12):
                    # Title validation at the full-opacity midpoint; other title
                    # frames remain exempt only in its independently bounded region.
                    titled=name=="copy-direct-reverse-rate-title"
                    values=frames[local*SIZE[0]*SIZE[1]*3:(local+1)*SIZE[0]*SIZE[1]*3]
                    err,count=compare_picture(values,picture(expected,colors,2,DESTINATION+local),
                                              65535,titled and local==6,exclude_title=titled)
                    pixel_error=max(pixel_error,err)
                    title_count+=count
                exported=array("f",run([ffmpeg,"-nostdin","-v","error","-i",movie,"-map","0:a:0","-f","f32le","pipe:1"]))
                assert len(exported)==len(target) and all(math.isfinite(value) for value in exported)
                master_error=max(abs(value-wanted) for value,wanted in zip(exported,target))
                assert master_error<=1/8388608,("Lossless PCM24 error",master_error)
                for local in (0,6,11,0):
                    request=copy.deepcopy(actual)
                    request["program"]["frame"]=DESTINATION+local
                    path=root/f"{name}-preview.air"
                    path.write_text(json.dumps(request),encoding="utf-8")
                    preview=root/f"{name}-{local}.png"
                    run([binary,"preview",preview,path],env)
                    data=run([ffmpeg,"-nostdin","-v","error","-i",preview,"-vf",f"scale={SIZE[0]}:{SIZE[1]}:flags=neighbor","-f","rawvideo","-pix_fmt","rgb24","pipe:1"])
                    values=list(data)
                    reference=picture(expected,colors,2,DESTINATION+local)
                    titled=name=="copy-direct-reverse-rate-title"
                    compare_picture(values,reference,255,titled and local==6,exclude_title=titled)
                result.update(passed="graph_error" not in result and "audition_error" not in result,audition_max_error_pcm16=error,master_max_error=master_error,
                              picture_max_error_codes16=pixel_error,title_white_pixels=title_count,
                              copied_graph_preserved="graph_error" not in result,preview_frames=[0,6,11,0])
            except Exception as failure:
                result["error"]=repr(failure)
        report["immutable_inputs"]=all(sha(Path(filename))==digest for filename,digest in immutable.items())
        assert report["immutable_inputs"],"Authored source/project files changed"
        report["passed"]=done.returncode==0 and all(case["passed"] for case in report["cases"])
        report["clipboard_defect_witnesses"]=[case["name"] for case in report["cases"] if
            ("graph_error" in case and ("audition_error" in case or "Independent picture error" in case.get("error",""))) or
            (case.get("clipboard_refusal",{}).get("nested",0)!=0 and
             case["clipboard_refusal"].get("operation")=="paste" and
             case["clipboard_refusal"].get("message","").strip()=="clipboard is empty")]
    except Exception as failure:
        report["error"]=repr(failure)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(dict(passed=report["passed"],cases=report["cases"],report=str(args.report),work=str(root)),indent=2))
    if args.expect_failure:
        assert not report["passed"] and report.get("clipboard_defect_witnesses"),"Baseline must expose copied graph plus wrong media, or the specific compound clipboard refusal"
    else:
        assert report["passed"],"Clipboard media gate failed; diagnostics and authored media preserved"


if __name__=="__main__":
    main()
