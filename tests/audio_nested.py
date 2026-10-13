"""Recursive audio must retain authored source time, bus DSP and float headroom.

Projects and PCM are independently authored here. The oracle sums float children,
applies a parent's effects once to that sum, then its gain/fades. FFmpeg is only
the independent DSP/tempo adapter; no Genesis output is an oracle input.
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

from audio_mix_project import document
from media_runtime import tool

SR = 48000
FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_clear(root, label):
    remaining = [str(path.relative_to(root)) for path in root.rglob(".genesis-nested-*")]
    assert not remaining, (label, "owned nested cache retained", remaining)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def sample(frame, fps):
    return math.floor(frame*SR/fps+.5)


def run(argv, env=None, data=None, accepted=True):
    done = subprocess.run(list(map(str, argv)), env=env, input=data, capture_output=True,
                          timeout=120, creationflags=FLAGS)
    if accepted:
        assert done.returncode == 0, (done.returncode, done.stdout[-3000:], done.stderr[-3000:])
    return done


def pcm(path):
    with wave.open(str(path), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (2, 2, SR)
        return array("h", audio.readframes(audio.getnframes()))


def floats(data):
    out = array("f")
    out.frombytes(data)
    assert all(math.isfinite(value) for value in out), "Nonfinite float audio"
    return out


def dsp(worker, values, chain):
    if not chain:
        return array("f", values)
    return floats(run([tool(worker, "ffmpeg"), "-nostdin", "-v", "error", "-f", "f32le",
                       "-ar", SR, "-ac", 2, "-i", "pipe:0", "-af", chain,
                       "-f", "f32le", "pipe:1"], data=values.tobytes()).stdout)


def points(doc, clip, name):
    return [(key["frame"], key["value"], key["interp"]) for key in doc["keys"]
            if key["clip"] == clip["id"] and doc["names"][key["param"]-1] == name]


def curve(keys, position, placement, fps, fallback):
    if not keys:
        return fallback
    if position <= sample(placement+keys[0][0], fps):
        return keys[0][1]
    for (a, av, mode), (b, bv, _) in zip(keys, keys[1:]):
        begin, end = sample(placement+a, fps), sample(placement+b, fps)
        if position < end:
            if mode == 4:
                return av
            assert mode == 2, "Independent nested oracle authors linear/hold curves"
            return av+(bv-av)*(position-begin)/(end-begin)
    return keys[-1][1]


def filter_chain(doc, clip):
    chain = []
    for effect in sorted((effect for effect in doc["filters"]
                          if effect["clip"] == clip["id"] and effect["enabled"]), key=lambda effect: effect["order"]):
        values = {item["name"]: item["value"] for item in doc["filter_params"]
                  if item["filter"] == effect["id"]}
        if effect["kind"] == "compressor":
            threshold = 10**(values["threshold"]/20)
            chain.append(f"acompressor=threshold={threshold:.17g}:ratio={values['ratio']}:attack={values['attack']}:release={values['release']}")
        elif effect["kind"] == "delay":
            chain.append(f"aecho=0.8:0.9:{int(values['time'])}:{values['decay']}")
        elif effect["kind"] == "gain":
            chain.append(f"volume={values['level']:.17g}dB")
        else:
            raise AssertionError(("Unauthored oracle effect", effect))
    return chain


def render(doc, source_values, worker):
    """Independent full-sequence float bus. Clamp only the final root output."""
    sequences = {item["id"]: item for item in doc["sequences"]}
    memo = {}

    def sequence(ident, ancestors=()):
        assert ident not in ancestors, "Oracle composition cycle"
        if ident in memo:
            return memo[ident]
        fps = sequences[ident]["fps"]
        tracks = {item["id"]: item for item in doc["tracks"] if item["owner"] == ident}
        solo = any(item["solo"] for item in tracks.values())
        clips = [item for item in doc["clips"] if item["owner"] == ident]
        finish = max((item["start"]+item["length"] for item in clips), default=0)
        out = array("f", [0.]*(sample(finish, fps)*2))
        for clip in clips:
            track = tracks[clip["track"]]
            if not clip["enabled"] or track["muted"] or (solo and not track["solo"]):
                continue
            assert clip["pan"] == track["pan"] == 0, "No implicit pan oracle"
            speed = clip["speed"]
            first = sample(clip["source_in"], fps)
            final = sample(clip["source_in"]+clip["length"]*speed, fps)
            child = sequence(clip["nested"], ancestors+(ident,)) if clip["nested"] else source_values[clip["source"]]
            raw = array("f", child[first*2:final*2])
            if clip["nested"] and not child:
                raw = array("f",[0.]*((final-first)*2))
            assert len(raw) == (final-first)*2, ("Oracle source range", ident, clip["id"], len(raw), final-first)
            chain = []
            if clip["reverse"]:
                chain.append("areverse")
            if speed != 1:
                chain.append(f"atempo={speed}")
            chain += filter_chain(doc, clip)
            values = dsp(worker, raw, ",".join(chain))
            placement, end = sample(clip["start"], fps), sample(clip["start"]+clip["length"], fps)
            wanted = end-placement
            values = values[:wanted*2]
            values.extend([0.]*(wanted*2-len(values)))
            gain_keys, incoming, outgoing = (points(doc, clip, name) for name in ("gain", "fade_in", "fade_out"))
            for n in range(wanted):
                absolute = placement+n
                gain = f32(track["gain"]*max(0., curve(gain_keys, absolute, clip["start"], fps, clip["gain"])))
                local = n/SR
                length_in = max(0., curve(incoming, absolute, clip["start"], fps, clip["fade_in"]))/fps
                length_out = max(0., curve(outgoing, absolute, clip["start"], fps, clip["fade_out"]))/fps
                envelope = min(1., max(0., local/length_in)) if length_in else 1.
                if length_out:
                    envelope *= min(1., max(0., (clip["length"]/fps-local)/length_out))
                gain = f32(gain*f32(envelope))
                for channel in (0, 1):
                    at = absolute*2+channel
                    out[at] = f32(out[at]+f32(values[n*2+channel]*gain))
        memo[ident] = out
        return out

    root = sequence(doc["active"])
    return array("f", (max(-1., min(1., value)) for value in root))


def authored(paths, root_fps=30, child_fps=60):
    doc = document(paths, (0,))
    doc["sequences"][0].update(fps=root_fps, name="Parent")
    doc["sequences"].append(dict(id=10, name="Child", fps=child_fps, width=16, height=16))
    doc["sources"] = [dict(id=7+n, path=str(path), name=path.name, bin=1, frames=240,
                           fps=30, width=0, height=0, has_video=False, has_audio=True,
                           audio_rate=SR, audio_channels=2, online=True) for n, path in enumerate(paths)]
    doc["tracks"] = [dict(id=ident, owner=owner, kind=1, name=name, order=order,
                          hidden=False, muted=False, locked=False, solo=False,
                          gain=1, pan=0, height=44)
                     for ident, owner, name, order in ((3, 2, "Parent A1", 0), (11, 10, "Child A1", 0), (12, 10, "Child A2", 1))]
    prototype = dict(group=0, enabled=True, selected=False, fade_in=0, fade_out=0,
                     gain=1, pan=0, speed=1, reverse=False)
    doc["clips"] = [dict(prototype, id=20, owner=10, source=7, nested=0, source_in=0,
                         length=int(4*child_fps), start=0, track=11),
                    dict(prototype, id=30, owner=2, source=0, nested=10, source_in=0,
                         length=24, start=0, track=3)]
    doc["next_id"] = 100
    return doc


def effect(doc, clip, kind, values, ident=50):
    doc["filters"].append(dict(id=ident, clip=clip, kind=kind, enabled=True, order=0))
    for name, value in values.items():
        if name not in doc["names"]:
            doc["names"].append(name)
        doc["filter_params"].append(dict(filter=ident, name=name, value=value))


def keys(doc, clip, owner, name, values):
    if name not in doc["names"]:
        doc["names"].append(name)
    doc["keys"] += [dict(clip=clip, owner=owner, param=doc["names"].index(name)+1,
                         frame=frame, value=value, interp=mode) for frame, value, mode in values]


def cases(paths):
    base = authored(paths)
    result = [("nested-only", base)]
    second = copy.deepcopy(base["clips"][0])
    second.update(id=21, track=12, source=8)
    summed = copy.deepcopy(base)
    summed["clips"].insert(1, second)
    result.append(("child-sum", summed))
    headroom = copy.deepcopy(summed)
    headroom["clips"][-1]["gain"] = .5
    result.append(("intermediate-headroom", headroom))
    gains = copy.deepcopy(summed)
    gains["tracks"][0]["gain"] = .75
    gains["tracks"][1]["gain"] = .5
    gains["tracks"][2]["gain"] = .25
    gains["clips"][-1]["gain"] = .5
    result.append(("parent-child-gain", gains))
    for name, which in (("parent-muted", 0), ("child-muted", 1)):
        doc = copy.deepcopy(summed)
        doc["tracks"][which]["muted"] = True
        if which == 0:
            doc["tracks"].append(dict(doc["tracks"][0], id=4, muted=False, order=1))
            doc["clips"].append(dict(doc["clips"][-1], id=32, track=4, source=10, nested=0))
        result.append((name, doc))
    solo = copy.deepcopy(summed)
    solo["tracks"][2].update(solo=True, gain=.25)
    result.append(("child-solo", solo))
    parent_solo = copy.deepcopy(summed)
    parent_solo["tracks"].append(dict(parent_solo["tracks"][0], id=4, order=1, solo=True))
    parent_solo["clips"].append(dict(parent_solo["clips"][-1], id=31, track=4, source_in=3, gain=.125))
    result.append(("parent-solo", parent_solo))
    nonlinear = copy.deepcopy(summed)
    for clip in nonlinear["clips"][:-1]:
        clip["gain"] = .5
    effect(nonlinear, 30, "compressor", dict(threshold=-6.020599913279624, ratio=4, attack=.01, release=50))
    result.append(("parent-compressor-on-sum", nonlinear))
    repeated = copy.deepcopy(base)
    repeated["clips"][0]["source"] = 9
    repeated["clips"][-1].update(length=12)
    repeated["clips"].append(dict(repeated["clips"][-1], id=31, start=12, source_in=6))
    effect(repeated, 30, "delay", dict(time=40, decay=.4))
    effect(repeated, 31, "delay", dict(time=40, decay=.4), 51)
    result.append(("repeated-child-instance-state", repeated))
    for name, reverse, speed in (("owner-fps-trim-seek", False, 1), ("nested-reverse", True, 1), ("nested-speed2", False, 2)):
        doc = copy.deepcopy(base)
        doc["clips"][0].update(source=9, start=2, source_in=3)
        doc["clips"][-1].update(source_in=4, reverse=reverse, speed=speed, start=3)
        doc["program"]["frame"] = 9
        result.append((name, doc))
    automated = copy.deepcopy(base)
    keys(automated, 20, 10, "gain", [(0, .2, 2), (12, .8, 4), (24, .4, 2), (239, .7, 2)])
    keys(automated, 20, 10, "fade_in", [(-5, 3., 2), (0, 12., 2), (20, 0., 4), (239, 0., 4)])
    keys(automated, 30, 2, "gain", [(0, .3, 2), (12, .9, 4), (23, .5, 4)])
    result.append(("child-parent-automation", automated))
    fractional = authored(paths,60000/1001,24)
    fractional["clips"][0].update(source=9,start=2,source_in=3)
    fractional["clips"][-1].update(start=3,source_in=11)
    fractional["program"]["frame"] = 9
    result.append(("fractional-owner-child-fps-seek",fractional))
    deep = copy.deepcopy(base)
    deep["sequences"].append(dict(id=40, name="Grandchild", fps=24, width=16, height=16))
    deep["tracks"].append(dict(deep["tracks"][1], id=41, owner=40))
    deep["clips"][0].update(source=0, nested=40, length=120, gain=.5)
    deep["clips"].insert(0, dict(base["clips"][0], id=42, owner=40, track=41, length=96, source=9))
    result.append(("two-level-recursion", deep))
    empty = copy.deepcopy(base)
    empty["clips"] = [empty["clips"][-1]]
    empty["tracks"].append(dict(empty["tracks"][0],id=4,order=1))
    empty["clips"].append(dict(empty["clips"][0],id=32,source=10,nested=0,track=4))
    effect(empty,30,"compressor",dict(threshold=-6.020599913279624,ratio=4,attack=.01,release=50))
    result.append(("empty-child-silence",empty))
    result.append(("after-empty-child-recovery",copy.deepcopy(base)))
    return result


def refusals(paths):
    base = authored(paths)
    cycle = copy.deepcopy(base)
    cycle["clips"][0].update(source=0, nested=2)
    missing = copy.deepcopy(base)
    missing["clips"][-1]["nested"] = 999999
    failed_source = copy.deepcopy(base)
    failed_source["sources"][0]["path"] = str(paths[0].parent / "missing online child.wav")
    excessive = copy.deepcopy(base)
    excessive["clips"][-1]["length"] = 30*6*60*60+1
    depth = copy.deepcopy(base)
    depth["clips"][0].update(source=0, nested=100)
    for n in range(19):
        ident, track, clip = 100+n, 200+n, 300+n
        depth["sequences"].append(dict(id=ident,name=f"Depth{n}",fps=60,width=16,height=16))
        depth["tracks"].append(dict(depth["tracks"][1],id=track,owner=ident))
        depth["clips"].append(dict(base["clips"][0],id=clip,owner=ident,track=track,
                                   source=7 if n==18 else 0,nested=0 if n==18 else ident+1))
    nodes = copy.deepcopy(base)
    nodes["clips"] = [nodes["clips"][-1],nodes["clips"][0]]+[dict(base["clips"][0],id=1000+n,length=1)
                                           for n in range(4097)]
    disk = copy.deepcopy(base)
    disk["sources"][0]["frames"] = 30*6*60*60
    disk["clips"] = [disk["clips"][-1]]+[dict(base["clips"][0],id=1000+n,length=60*6*60*60)
                                         for n in range(5)]
    return [("cycle",cycle,"GA_AUDIO_NESTED_CYCLE"),
            ("missing-sequence",missing,"GA_AUDIO_NESTED_PROTOCOL"),
            ("missing-online-child",failed_source,"GA_AUDIO_NESTED_RENDER"),
            ("six-hour-capacity",excessive,"GA_AUDIO_NESTED_CAPACITY"),
            ("depth-capacity",depth,"GA_AUDIO_NESTED_CAPACITY"),
            ("node-capacity",nodes,"GA_AUDIO_NESTED_CAPACITY"),
            ("float-disk-capacity",disk,"GA_AUDIO_NESTED_CAPACITY")]


def compare(actual, wanted, pcm_units, label):
    assert actual and len(actual) == len(wanted), (label, "length", len(actual), len(wanted))
    assert all(math.isfinite(value) for value in actual), (label, "nonfinite output")
    scale = 32767 if pcm_units else 1
    maximum = max(abs(a-b*scale) for a, b in zip(actual, wanted))
    limit = 2 if pcm_units else 1/8388608
    assert maximum <= limit, (label, "every-sample error", maximum, limit)
    return maximum


def amplitude(values, begin, end, channel, frequency):
    first, final = int(begin*SR), int(end*SR)
    assert final*2 <= len(values)
    real = sum(values[n*2+channel]*math.cos(2*math.pi*frequency*n/SR) for n in range(first,final))
    imag = sum(values[n*2+channel]*math.sin(2*math.pi*frequency*n/SR) for n in range(first,final))
    return 2*math.hypot(real,imag)/(final-first)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary, client, worker = (value.resolve() for value in (args.binary, args.client, args.worker))
    report = dict(schema="genesis.audio_nested.v1", passed=False, app_sha256=sha(binary),
                  client_sha256=sha(client), worker_sha256=sha(worker), cases=[])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-nested-audio-") as temporary:
        root = Path(temporary)
        paths, source_values = [], {}
        for n in range(4):
            source = root / f"child {n} 日本語.wav"
            values = array("h", (value for at in range(8*SR) for value in
                ((26214, -19661) if n < 2 else (0, 0) if n == 3 else (int(9000+4000*math.sin(2*math.pi*431.3*at/SR)),
                                               int(-7000+3000*math.cos(2*math.pi*211.7*at/SR))))))
            with wave.open(str(source), "wb") as audio:
                audio.setparams((2, 2, SR, 0, "NONE", "not compressed"))
                audio.writeframes(values.tobytes())
            source_values[7+n] = array("f", (value/32768 for value in values))
            paths.append(source)
        source_hashes = [sha(path) for path in paths]
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root/"state"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        env.pop("GENESIS_SESSION_REPORT", None)
        manifest, targets, project_hashes = [], {}, {}
        try:
            for name, doc in cases(paths):
                project = root/(name+".air")
                project.write_text(json.dumps(doc), encoding="utf-8")
                project_hashes[project] = sha(project)
                target = render(doc, source_values, worker)
                if name == "parent-compressor-on-sum":
                    # Both child contributions are .4 after their own gain.
                    # Duplicating the parent compressor onto each contribution
                    # filters .4 twice, whereas the real bus filters their .8 sum.
                    contribution = array("f",(f32(value*.5) for value in source_values[7][:len(target)]))
                    flattened = dsp(worker,contribution,",".join(filter_chain(doc,doc["clips"][-1])))
                    alternate = array("f",(f32(value*2) for value in flattened[:len(target)]))
                    separation = max(abs(a-b) for a,b in zip(target,alternate))
                    assert separation > .05, ("Oracle cannot distinguish parent-on-sum from per-leaf filtering",separation)
                    report["nonlinear_bus_vs_leaf_maximum_difference"] = separation
                if name == "intermediate-headroom":
                    assert abs(target[2000]-.79998779296875)<1e-7, "Oracle must retain1.6×.5 headroom"
                targets[name] = (doc, target)
                fps, begin = doc["sequences"][0]["fps"], doc["program"]["frame"]
                finish = max(clip["start"]+clip["length"] for clip in doc["clips"] if clip["owner"] == 2)
                manifest.append(f"{name}\t{begin}\t{finish}\t{min(finish-1,begin+5)}\n")
                audition = root/(name+".wav")
                run([binary, "audio", audition, project], env)
                cache_clear(root,(name,"whole audition exit"))
                audition_error = compare(pcm(audition), target[sample(begin,fps)*2:], True, (name,"audition"))
                movie = root/(name+".mkv")
                run([binary, "export", movie, project], env)
                cache_clear(root,(name,"master export exit"))
                master = floats(run([tool(worker,"ffmpeg"),"-nostdin","-v","error","-i",movie,"-vn","-f","f32le","pipe:1"]).stdout)
                master_error = compare(master,target,False,(name,"master"))
                assert sha(project) == project_hashes[project], "Rendering changed authored project"
                report["cases"].append(dict(name=name, audition_max_error_pcm=audition_error,
                                            master_max_error=master_error, master_frames=len(master)//2))
                print(f"Nested audio: {name}, every audition/master sample passed", flush=True)
            (root/"cases.tsv").write_text("".join(manifest),encoding="utf-8")
            run([client,worker,root])
            cache_clear(root,"native Stop and worker join")
            native = root/"native"
            native_facts = (native/"model.tsv").read_text(encoding="utf-8")
            assert "child_key_signature_undo_saveopen_picture\ttrue\n" in native_facts
            assert "stop_join_no_owned_cache\ttrue\n" in native_facts
            assert f"checked_cases\t{len(targets)}\n" in native_facts
            for name,(doc,target) in targets.items():
                fps,begin = doc["sequences"][0]["fps"],doc["program"]["frame"]
                seek = min(max(clip["start"]+clip["length"] for clip in doc["clips"] if clip["owner"]==2)-1,begin+5)
                for suffix,offset in (("whole",0),("chunks",begin),("seek",seek)):
                    actual = pcm(native/(name+"-"+suffix+".wav")) if suffix=="whole" else array("h")
                    if suffix!="whole":
                        for path in sorted(native.glob(name+"-"+suffix+"-*.wav"),key=lambda value:int(value.stem.rsplit("-",1)[1])):
                            actual.extend(pcm(path))
                    compare(actual,target[sample(offset,fps)*2:],True,(name,suffix))
            assert source_hashes == [sha(path) for path in paths], "Rendering changed authored source"
            assert all(sha(path)==original for path,original in project_hashes.items()), "Native client changed authored project"
            refused = []
            for name,doc,code in refusals(paths):
                project = root/("refuse-"+name+".air")
                project.write_text(json.dumps(doc),encoding="utf-8")
                original = sha(project)
                for verb,suffix in (("audio",".wav"),("export",".mkv")):
                    output = root/("refused-"+name+suffix)
                    done = run([binary,verb,output,project],env,accepted=False)
                    note = (done.stdout+done.stderr).decode("utf-8",errors="replace")
                    assert done.returncode != 0 and code in note, (name,verb,"coded refusal",done.returncode,note[-3000:])
                    assert not output.exists() and not list(root.glob(output.name+"*")), (name,verb,"published output or owned partial after refusal")
                    cache_clear(root,(name,verb,"refusal exit"))
                    assert sha(project)==original, "Refusal changed authored malformed project"
                refused.append(dict(name=name,code=code,audition_export_no_output=True,project_unchanged=True))
            report["refusals"] = refused
            tone = root/"nested AAC tones.wav"
            tones = array("h",(value for n in range(8*SR) for value in
                (round(.3*32768*math.sin(2*math.pi*440*n/SR)),round(.2*32768*math.sin(2*math.pi*660*n/SR)))))
            with wave.open(str(tone),"wb") as output:
                output.setparams((2,2,SR,0,"NONE","not compressed"))
                output.writeframes(tones.tobytes())
            tone_hash = sha(tone)
            aac_doc = authored(paths)
            aac_doc["sources"][2]["path"] = str(tone)
            aac_doc["clips"][0]["source"] = 9
            aac_doc["clips"][-1].update(length=60,gain=.5)
            keys(aac_doc,20,10,"gain",[(0,.2,4),(60,.8,4),(239,.8,4)])
            aac_sources = dict(source_values)
            aac_sources[9] = array("f",(value/32768 for value in tones))
            aac_target = render(aac_doc,aac_sources,worker)
            aac_project = root/"nested-aac.air"
            aac_project.write_text(json.dumps(aac_doc),encoding="utf-8")
            aac_hash = sha(aac_project)
            output_values = {}
            for suffix in ("mkv","mp4"):
                movie = root/("nested-aac."+suffix)
                run([binary,"export",movie,aac_project],env)
                cache_clear(root,("nested AAC",suffix,"export exit"))
                decoded = floats(run([tool(worker,"ffmpeg"),"-nostdin","-v","error","-i",movie,"-vn","-f","f32le","pipe:1"]).stdout)
                output_values[suffix] = decoded
            compare(output_values["mkv"],aac_target,False,"nested AAC fixture lossless master")
            assert 2*SR*2<=len(output_values["mp4"])<=(2*SR+1024)*2, "Nested AAC sample count/padding"
            windows = []
            for begin,end in ((.25,.75),(1.25,1.75)):
                for channel,frequency in ((0,440),(1,660)):
                    wanted = amplitude(aac_target,begin,end,channel,frequency)
                    actual = amplitude(output_values["mp4"],begin,end,channel,frequency)
                    assert wanted>.01 and math.isfinite(actual) and abs(actual-wanted)<=.001+.02*wanted, ("Nested AAC envelope",begin,channel,actual,wanted)
                    windows.append(dict(begin=begin,end=end,channel=channel,expected=wanted,actual=actual))
            assert sha(tone)==tone_hash and sha(aac_project)==aac_hash, "AAC render changed source/project bytes"
            report["aac_amplitude_windows"] = windows
            report.update(passed=True, source_project_bytes_unchanged=True,
                          stop_join_and_command_exit_no_owned_cache=True,
                          scope="recursive sample processing, model and encoded output; no device/cadence claim")
        except Exception as problem:
            report["execution_error"] = str(problem)
            report["diagnostics"] = {str(path.relative_to(root)):path.read_text(encoding="utf-8",errors="replace")[-5000:]
                                     for path in root.rglob("*") if path.is_file() and path.suffix in (".tsv",".log",".jsonl") and path.stat().st_size<65536}
            report["worker_sha256_after"] = sha(worker)
            report["worker_unchanged_during_run"] = report["worker_sha256_after"] == report["worker_sha256"]
            args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
            raise
        report["worker_sha256_after"] = sha(worker)
        report["worker_unchanged_during_run"] = report["worker_sha256_after"] == report["worker_sha256"]
        assert report["worker_unchanged_during_run"], "Worker binary changed during acceptance run"
    args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
