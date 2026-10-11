"""Independent transition pictures and unchanged separate A1 sample identity.

The AIR client creates/types/resizes/removes transitions through real commands,
roundtrips their saved graph and renders every requested frame through the
retained production provider. This script authors lossless input codes, derives
source time and transition weights itself, and measures native preview plus
CLI lossless master. No Genesis output is an expected-media input.
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
import struct
import subprocess
import tempfile
from urllib.parse import unquote
import wave

from media_runtime import tool

WIDTH, HEIGHT, SOURCE_FRAMES, SR = 64, 36, 72, 48000
KINDS = ("crossfade", "wipe_lr", "wipe_rl", "wipe_up", "wipe_down",
         "slide_lr", "zoom", "dissolve", "iris", "clock", "barn_door")
FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(argv, env=None, data=None):
    done = subprocess.run(list(map(str, argv)), input=data, env=env, capture_output=True,
                          timeout=120, creationflags=FLAGS)
    assert done.returncode == 0, (argv, done.returncode, done.stdout[-3000:], done.stderr[-3000:])
    return done.stdout


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def ulp32(value):
    return max(2.**-149, 2.**(math.frexp(abs(value))[1]-24)) if value else 2.**-149


def rounded_interval(low, high, ulps=.5):
    error = ulps*ulp32(max(abs(low),abs(high)))
    return low-error, high+error


def normalized_interval(coordinate, extent):
    # OpenCL C Full Profile Table 65: division <=2.5 ulp; subtraction
    # correctly rounded. Bounds are calculated before examining any output.
    ratio = coordinate/extent
    low, high = rounded_interval(ratio,ratio,2.5)
    return rounded_interval(low-.5,high-.5)


def boundary_ambiguous(kind, progress, x, y):
    """Whether declared single-precision error can flip a hard predicate.

    Reference: https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_C.html
    Table 65: / <=2.5 ulp, sqrt <=3 ulp, atan2 <=6 ulp, +/* correctly
    rounded. This admits only an authored complete A or B pixel at the
    analytically bounded seam, never interpolation or an unchecked pixel.
    """
    nx, ny = normalized_interval(x,WIDTH), normalized_interval(y,HEIGHT)
    t = f32(progress)
    if kind == "iris":
        def squared(interval):
            low, high = interval
            minimum = 0. if low<=0<=high else min(low*low,high*high)
            return rounded_interval(minimum,max(low*low,high*high))
        xx, yy = squared(nx), squared(ny)
        low, high = rounded_interval(xx[0]+yy[0],xx[1]+yy[1])
        radius = rounded_interval(math.sqrt(max(0.,low)),math.sqrt(max(0.,high)),3)
        threshold = f32(t*f32(.72))
        return radius[0] <= threshold <= radius[1]
    if kind == "clock":
        cx, cy = x/WIDTH-.5, y/HEIGHT-.5
        radius = math.hypot(cx,cy)
        displacement = math.hypot(max(abs(nx[0]-cx),abs(nx[1]-cx)),
                                  max(abs(ny[0]-cy),abs(ny[1]-cy)))
        if radius <= displacement:
            return True  # atan2 is singular only within this coordinate box.
        angle = math.atan2(cx,-cy)
        angular_error = math.asin(min(1.,displacement/radius))
        angular_error += 6*ulp32(min(math.pi,abs(angle)+angular_error))
        pi = f32(math.pi)
        # Split across the atan2 branch cut; points near it are not silently
        # turned into a large interval covering the interior of the wipe.
        for shift in (-2*math.pi,0.,2*math.pi):
            low, high = max(-math.pi,angle-angular_error+shift), min(math.pi,angle+angular_error+shift)
            if low > high:
                continue
            low, high = rounded_interval(low+pi,high+pi)
            low, high = rounded_interval(low/(2*pi),high/(2*pi),2.5)
            if low <= t <= high:
                return True
    return False


def picture_error(actual, expected, doc, center, duration, kind, frame, scale):
    assert len(actual)==len(expected)==WIDTH*HEIGHT*3
    first = center-duration//2
    active = first<=frame<first+duration
    maximum, eligible, alternatives = 0.,0,0
    for pixel in range(WIDTH*HEIGHT):
        offset, x, y = pixel*3,pixel%WIDTH,pixel//WIDTH
        observed, wanted = actual[offset:offset+3],expected[offset:offset+3]
        strict = max(abs(v-w*scale) for v,w in zip(observed,wanted))
        error = strict
        if active and kind in ("iris","clock") and boundary_ambiguous(kind,(frame-first)/duration,x,y):
            eligible += 1
            # One complete RGB triplet must match a separately authored input.
            candidates = [authored_rgb(clip_info["source"]==8,source_index(doc,clip_info,frame),x,y)
                          for clip_info in doc["clips"][:2]]
            error = min(max(abs(v-w/65535*scale) for v,w in zip(observed,candidate))
                        for candidate in candidates)
            alternatives += int(strict>2 and error<=2)
        maximum = max(maximum,error)
    return maximum,eligible,alternatives


def rational(fps):
    return Fraction(60000, 1001) if abs(fps-60000/1001) < 1e-8 else Fraction(str(fps))


def sample(frame, fps):
    return math.floor(Fraction(frame)*SR/rational(fps)+Fraction(1, 2))


def authored_rgb(incoming, frame, x, y):
    # Arbitrary low 16-bit codes and spatial variation expose wrong frame
    # selection, slide/zoom sampling and loss of precision separately.
    if incoming:
        return (43000-frame*89-x*47-y*83, 9000+frame*127+x*31+y*67,
                31000+frame*43-x*73+y*59)
    return (7000+frame*113+x*97+y*53, 35000-frame*71-x*43-y*101,
            11000+frame*157+x*29+y*89)


def source(root, ffmpeg, ident, fps):
    incoming = ident == 8
    values = array("H", (code for frame in range(SOURCE_FRAMES)
                         for y in range(HEIGHT) for x in range(WIDTH)
                         for code in authored_rgb(incoming, frame, x, y)))
    raw, media = root/f"source-{ident}.rgb48", root/f"source-{ident}.nut"
    raw.write_bytes(values.tobytes())
    run([ffmpeg, "-nostdin", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb48le",
         "-s", f"{WIDTH}x{HEIGHT}", "-r", str(rational(fps)), "-i", raw,
         "-c:v", "ffv1", "-level", "3", "-pix_fmt", "gbrp16le", media])
    decoded = run([ffmpeg, "-nostdin", "-v", "error", "-i", media, "-map", "0:v:0",
                   "-f", "rawvideo", "-pix_fmt", "rgb48le", "pipe:1"])
    assert decoded == values.tobytes(), "Every authored RGB48 source code must survive independent decode"
    return dict(id=ident, path=str(media), name=media.name, bin=1, frames=SOURCE_FRAMES,
                fps=fps, width=WIDTH, height=HEIGHT, has_video=True, has_audio=False,
                audio_rate=0, audio_channels=0, online=True)


def audio_source(root):
    pcm = array("h", (value for i in range(SR*2)
                      for value in (900+((i*37)%17000), -700-((i*53)%15000))))
    path = root/"independent A1.wav"
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
        output.writeframes(pcm.tobytes())
    return dict(id=9, path=str(path), name=path.name, bin=1, frames=120, fps=60,
                width=0, height=0, has_video=False, has_audio=True, audio_rate=SR,
                audio_channels=2, online=True), pcm


def lane(ident, kind):
    return dict(id=ident, owner=2, kind=kind, name="V1" if kind == 0 else "A1",
                order=0 if kind == 0 else 1, hidden=False, muted=False, locked=False,
                solo=False, gain=1, pan=0, height=54)


def clip(ident, source_id, track, start, length, source_in=0, reverse=False):
    return dict(id=ident, owner=2, source=source_id, nested=0, source_in=source_in,
                start=start, length=length, track=track, group=0, enabled=True,
                selected=False, fade_in=0, fade_out=0, gain=1, pan=0, speed=1,
                reverse=reverse, streams=1 if track == 3 else 2)


def fixtures(sources):
    for shape, fps, second, center, duration in (
            ("touch", 30, 14, 14, 8),
            ("gap", 24, 16, 14, 7),
            ("overlap", 60000/1001, 10, 12, 9)):
        start = center-duration//2
        end = start+duration
        for kind in KINDS:
            doc = dict(schema="air.editor.project", revision=2, active=2, source_bounds=0,
                       monitor_source=7, next_id=100,
                       program=dict(playing=False, frame=start-1, mark_in=start-1,
                                    mark_out=end+1, rate=1, looping=False),
                       monitor=dict(playing=False, frame=0, mark_in=-1, mark_out=-1,
                                    rate=1, looping=False),
                       bins=[dict(id=1, name="Independent sources", parent=0)],
                       sequences=[dict(id=2, name="Transition oracle", fps=fps,
                                       width=WIDTH, height=HEIGHT)],
                       sources=copy.deepcopy(sources), tracks=[lane(3, 0), lane(4, 1)],
                       clips=[clip(20, 7, 3, 2, 12, 3, True),
                              clip(21, 8, 3, second, 12, 7), clip(22, 9, 4, 0, 32)],
                       transitions=[], keys=[], markers=[], subtitles=[], filters=[],
                       filter_params=[], filter_text_params=[], names=[])
            yield f"{shape}-{kind}", doc, center, duration, kind


def source_index(doc, item, frame):
    # Clamp transition halves to authored clip endpoints *before* retiming.
    local = max(0, min(item["length"]-1, frame-item["start"]))
    position = item["length"]-1-local if item["reverse"] else local
    source_info = next(s for s in doc["sources"] if s["id"] == item["source"])
    return math.floor((Fraction(item["source_in"])+position) * rational(source_info["fps"])
                      / rational(doc["sequences"][0]["fps"]))


def transition_pixel(kind, progress, a, b, x, y, incoming_frame):
    # Analytic working-pixel contract. Nearest integer sampler truncates toward
    # zero after +.5, including negative positions (not Python round/floor).
    t = f32(progress)
    w = t
    if kind.startswith("wipe_"):
        along, extent = (x, WIDTH) if kind in ("wipe_lr", "wipe_rl") else (y, HEIGHT)
        if kind in ("wipe_rl", "wipe_up"):
            along = extent-1-along
        w = max(0., min(1., f32(f32(f32(t*extent)-along)/36.)+.5))
    elif kind == "dissolve":
        luma = f32(f32(f32(a[0]*.299)+f32(a[1]*.587))+f32(a[2]*.114))
        w = max(0., min(1., f32(f32(f32(t*1.25)-luma)*4.)))
    elif kind == "iris":
        nx, ny = f32(x/WIDTH-.5), f32(y/HEIGHT-.5)
        w = int(math.sqrt(f32(f32(nx*nx)+f32(ny*ny))) <= f32(t*.72))
    elif kind == "clock":
        nx, ny = f32(x/WIDTH-.5), f32(y/HEIGHT-.5)
        angle = f32(math.atan2(nx, -ny))
        w = int(f32(f32(angle+f32(math.pi))/f32(2*f32(math.pi))) <= t)
    elif kind == "barn_door":
        w = int(abs(f32(x/WIDTH-.5)) <= f32(t*.5))
    elif kind == "slide_lr":
        sx = int(f32(f32(x-f32(f32(1-t)*WIDTH))+.5))
        return [v/65535 for v in authored_rgb(True, incoming_frame, sx, y)] if 0 <= sx < WIDTH else a
    elif kind == "zoom":
        # One rounded affine expression preserves the OpenCL contraction
        # contract. Rounding its product separately moves nearest sample ties.
        scale = f32(.25+.75*t)
        sx = int(f32(f32(WIDTH/2+f32((x-WIDTH/2)/scale))+.5))
        sy = int(f32(f32(HEIGHT/2+f32((y-HEIGHT/2)/scale))+.5))
        return [v/65535 for v in authored_rgb(True, incoming_frame, sx, sy)] if 0 <= sx < WIDTH and 0 <= sy < HEIGHT else a
    return [av*(1-w)+bv*w for av, bv in zip(a, b)]


def picture(doc, center, duration, kind, frame):
    a, b = doc["clips"][:2]
    first = center-duration//2
    active = first <= frame < first+duration
    incoming_frame = source_index(doc, b, frame)
    outgoing_frame = source_index(doc, a, frame)
    result = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            av = [v/65535 for v in authored_rgb(False, outgoing_frame, x, y)]
            bv = [v/65535 for v in authored_rgb(True, incoming_frame, x, y)]
            if active:
                rgb = transition_pixel(kind, (frame-first)/duration, av, bv, x, y, incoming_frame)
            elif a["start"] <= frame < a["start"]+a["length"]:
                rgb = av
            elif b["start"] <= frame < b["start"]+b["length"]:
                rgb = bv
            else:
                rgb = (0., 0., 0.)
            result.extend(rgb)
    return result


def graph_check(original, saved, center, duration, kind):
    assert len(saved["transitions"]) == 1
    transition = saved["transitions"][0]
    assert (transition["owner"], transition["track"], transition["center"], transition["duration"],
            saved["names"][transition["kind"]-1]) == (2, 3, center, duration, kind)
    for field in ("sources", "tracks", "sequences", "keys", "filters", "filter_params", "filter_text_params"):
        assert saved[field] == original[field], ("Transition changed unrelated graph", field)
    for old, new in zip(original["clips"], saved["clips"]):
        assert {k:v for k,v in new.items() if k != "selected"} == {k:v for k,v in old.items() if k != "selected"}
    assert saved["program"] == original["program"]


def plans_check(path, doc, center, duration, kind):
    frames, lines, current = [], [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("FRAME\t"):
            if current is not None:
                frames.append((current, lines))
            current, lines = int(line.split("\t")[1]), []
        else:
            lines.append(line.split())
    if current is not None:
        frames.append((current, lines))
    start, end = doc["program"]["mark_in"], doc["program"]["mark_out"]
    assert [frame for frame,_ in frames] == list(range(start,end))+[start]
    first = center-duration//2
    count = 0
    for frame, commands in frames:
        final = next(fields for fields in reversed(commands) if fields[0] == "PREVIEW")
        wire = final[1:]
        expected_type = KINDS.index(kind) if first <= frame < first+duration else -1
        assert int(wire[16]) == expected_type, ("Emitted transition kind", frame, wire[16], expected_type)
        if expected_type >= 0:
            assert abs(float(wire[17])-(frame-first)/duration) < 1e-12
            assert int(wire[2]) == source_index(doc, doc["clips"][0], frame)
            assert int(wire[20]) == source_index(doc, doc["clips"][1], frame)
            assert Path(unquote(wire[0])).resolve() == Path(doc["sources"][0]["path"]).resolve()
            assert Path(unquote(wire[19])).resolve() == Path(doc["sources"][1]["path"]).resolve()
            count += 1
    assert count == duration
    return len(frames)


def main():
    parser = argparse.ArgumentParser()
    for name in ("client", "binary", "worker", "report"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--shape", choices=("touch", "gap", "overlap"))
    args = parser.parse_args()
    client, binary, worker = (path.resolve() for path in (args.client,args.binary,args.worker))
    root = args.work.resolve() if args.work else Path(tempfile.mkdtemp(prefix="genesis-transition-controls-"))
    if args.work:
        root.mkdir(parents=True, exist_ok=False)
    assert not args.report.exists(), "Refuse to replace a previous acceptance receipt"
    report = dict(schema="genesis.transition-controls-media.v1", app_sha256=sha(binary),
                  client_sha256=sha(client), worker_sha256=sha(worker), oracle_sha256=sha(Path(__file__)),
                  fixture_sha256=sha(Path(__file__).with_suffix(".ai")), work=str(root), passed=False,
                  scope="Tiny native working canvas; no UI/device/cadence or large-canvas throughput claim",
                  oracle_contract=dict(canvas=[WIDTH,HEIGHT],preview_codes8=2,master_codes16=2,
                    audition_codes16=1,master_pcm_absolute=1/8388608,
                    hard_mask_boundary="OpenCL Full Profile float interval; complete authored A or B triplet only",
                    numerical_spec="https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_C.html",
                    master_audio_count="ceil(range duration*48000); every allocated sample checked",
                    sample_selection="rounded absolute range start; legacy context-free native sample duration"),
                  cases=[])
    immutable = {}
    try:
        ffmpeg = tool(worker, "ffmpeg")
        a = source(root, ffmpeg, 7, 24)
        b = source(root, ffmpeg, 8, 60000/1001)
        sound, pcm = audio_source(root)
        chosen = [(name,doc,center,duration,kind) for name,doc,center,duration,kind in fixtures([a,b,sound])
                  if (not args.kind or args.kind==kind) and (not args.shape or name.startswith(args.shape+"-"))]
        rows = []
        for name, doc, center, duration, kind in chosen:
            path = root/(name+".air")
            path.write_text(json.dumps(doc), encoding="utf-8")
            immutable[str(path)] = sha(path)
            rows.append(f"{name}\t{path}\t3\t{center}\t{duration}\t{kind}")
        for info in (a,b,sound):
            immutable[info["path"]] = sha(info["path"])
        manifest, native = root/"cases.tsv", root/"native"
        manifest.write_text("\n".join(rows)+"\n", encoding="utf-8")
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root/"scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        env.pop("GENESIS_SESSION_REPORT", None)
        executed = subprocess.run(list(map(str,[client,native,worker,manifest])), env=env,
                                  capture_output=True,timeout=120,creationflags=FLAGS)
        (root/"client.log").write_bytes(executed.stdout+executed.stderr)
        report["native_exit"] = executed.returncode
        assert executed.returncode==0, ("Native command/preview fixture failed",executed.returncode,
                                        str(root/"client.log"))
        report["native_report_sha256"] = sha(native/"transition-controls-media-tests.json")
        for name, doc, center, duration, kind in chosen:
            result = dict(name=name, duration=duration, fps=doc["sequences"][0]["fps"], passed=False)
            report["cases"].append(result)
            try:
                directory = native/name
                saved = json.loads((directory/"selected.air").read_text(encoding="utf-8"))
                graph_check(doc,saved,center,duration,kind)
                result["emitted_plan_frames"] = plans_check(directory/"plans.txt",doc,center,duration,kind)
                removed = (directory/"removed.rgba").read_bytes()
                assert len(removed)==WIDTH*HEIGHT*4
                hard_cut = picture(doc,center,0,kind,center)
                removed_error = max(abs(value-wanted*255) for value,wanted in zip(
                    (byte for at,byte in enumerate(removed) if at%4!=3),hard_cut))
                assert removed_error <= 2, ("Remove did not render the authored hard cut/gap",removed_error)
                removed_fields = (directory/"removed-plan.txt").read_text(encoding="utf-8").splitlines()[-1].split()[1:]
                assert int(removed_fields[16])==-1
                begin, end = doc["program"]["mark_in"], doc["program"]["mark_out"]
                references = [picture(doc,center,duration,kind,frame) for frame in range(begin,end)]
                preview_error, preview_boundaries, preview_alternatives = 0.,0,0
                for frame in range(begin,end+1):
                    raw = (directory/f"frame-{frame}.rgba").read_bytes()
                    assert len(raw)==WIDTH*HEIGHT*4 and set(raw[3::4])=={255}
                    reference = references[0 if frame==end else frame-begin]
                    actual_frame = begin if frame==end else frame
                    error,eligible,alternatives = picture_error(
                        [byte for at,byte in enumerate(raw) if at%4!=3],reference,
                        doc,center,duration,kind,actual_frame,255)
                    preview_error = max(preview_error,error)
                    preview_boundaries += eligible
                    preview_alternatives += alternatives
                assert preview_error <= 2, ("Native preview code error",preview_error)
                movie = root/(name+".mkv")
                run([binary,"export",movie,directory/"selected.air"],env)
                pixels = array("H",run([ffmpeg,"-nostdin","-v","error","-i",movie,"-map","0:v:0",
                                         "-f","rawvideo","-pix_fmt","rgb48le","pipe:1"]))
                expected = [value for frame in references for value in frame]
                assert len(pixels)==len(expected), "Exact lossless master frame count"
                error,master_boundaries,master_alternatives = 0.,0,0
                stride = WIDTH*HEIGHT*3
                for at,reference in enumerate(references):
                    measured,eligible,alternatives = picture_error(
                        pixels[at*stride:(at+1)*stride],reference,
                        doc,center,duration,kind,begin+at,65535)
                    error = max(error,measured)
                    master_boundaries += eligible
                    master_alternatives += alternatives
                assert error <= 2, ("Lossless RGB48 transition error",error)
                fps = doc["sequences"][0]["fps"]
                first, last = sample(begin,fps), sample(end,fps)
                # OPEN has always allocated ceil(duration*48000), independently
                # of rounded absolute timeline endpoints. Preserve and inspect
                # that declared encoder count, including its fractional final
                # sample; picture transitions must not change any sample.
                master_count = math.ceil(Fraction(end-begin)*SR/rational(fps))
                target = pcm[first*2:(first+master_count)*2]
                master = array("f",run([ffmpeg,"-nostdin","-v","error","-i",movie,"-map","0:a:0",
                                         "-f","f32le","pipe:1"]))
                assert len(master)==len(target), ("Exact allocated master stereo sample count",len(master)//2,len(target)//2)
                assert all(math.isfinite(v) for v in master), "Finite independently decoded master PCM"
                pcm24_error = max(abs(value-wanted/32768) for value,wanted in zip(master,target))
                assert pcm24_error <= 1/8388608, ("Picture transition changed A1 master PCM",pcm24_error)
                audition = root/(name+".wav")
                run([binary,"audio",audition,directory/"selected.air"],env)
                # `audio` audits from playhead through sequence end, whereas
                # master uses the selected half-open export range.
                sequence_end = max(item["start"]+item["length"] for item in doc["clips"])
                audition_target = pcm[first*2:sample(sequence_end,fps)*2]
                with wave.open(str(audition),"rb") as reader:
                    assert (reader.getnchannels(),reader.getsampwidth(),reader.getframerate())==(2,2,SR)
                    samples = array("h",reader.readframes(reader.getnframes()))
                # Legacy WAVE allocates ceil(duration), while the selected body
                # reference uses rounded absolute sample endpoints.
                assert len(samples) in (len(audition_target),len(audition_target)+2)
                assert not any(samples[len(audition_target):]), "Only exact zero allocation padding is allowed"
                pcm16_error = max(abs(value-wanted/32768*32767) for value,wanted in zip(samples,audition_target))
                assert pcm16_error <= 1, ("Picture transition changed A1 audition PCM",pcm16_error)
                result.update(passed=True,preview_max_error_codes8=preview_error,
                              removed_preview_max_error_codes8=removed_error,
                              master_max_error_codes16=error,master_frames=end-begin,
                              master_pcm_samples=len(target)//2,master_pcm24_error=pcm24_error,
                              rounded_absolute_range_samples=last-first,
                              encoder_extra_fractional_sample=master_count-(last-first),
                              preview_boundary_pixels=preview_boundaries,
                              preview_boundary_alternative_pixels=preview_alternatives,
                              master_boundary_pixels=master_boundaries,
                              master_boundary_alternative_pixels=master_alternatives,
                              audition_pcm16_error=pcm16_error,retained_rewind=True)
            except Exception as failure:
                result["error"] = repr(failure)
        report["immutable_inputs"] = all(sha(path)==value for path,value in immutable.items())
        assert report["immutable_inputs"]
        report["passed"] = len(report["cases"])==len(chosen) and all(case["passed"] for case in report["cases"])
    except Exception as failure:
        report["error"] = repr(failure)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open("x",encoding="utf-8") as output:
        json.dump(report,output,indent=2)
    print(json.dumps(dict(passed=report["passed"],cases=len(report["cases"]),report=str(args.report))))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
