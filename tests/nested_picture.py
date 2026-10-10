"""Authored compound pictures must preserve time, transparent buses and outer effects.

Expected pixels come from authored, independently decoded lossless source frames
and a small rational-time/straight-alpha oracle. Genesis output is never an
oracle input. --expect-refusal records the unsupported baseline explicitly.
"""
import argparse
from array import array
import copy
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

from media_runtime import tool

SIZE = (64, 36)
BACKGROUND = (21, 47, 83)
SOURCE_FRAMES = 96
SR = 48000
FLAGS = 0x08000000 if os.name == "nt" else 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, env=None, accepted=True):
    result = subprocess.run(list(map(str, argv)), env=env, capture_output=True,
                            timeout=120, creationflags=FLAGS)
    if accepted:
        assert result.returncode == 0, (argv, result.returncode,
                                      result.stdout[-4000:], result.stderr[-4000:])
    return result


def rational(value):
    if abs(value-60000/1001) < 1e-8:
        return Fraction(60000, 1001)
    return Fraction(str(value))


def sample(frame, fps):
    return math.floor(Fraction(frame)*SR/rational(fps)+Fraction(1, 2))


def coded(frame):
    return (64+frame, 64+(frame*17)%160, 96+(frame*31)%128)


def source(root, ffmpeg, fps, label, color=None, sound=False, pattern=None):
    # NUT preserves exact PCM packet time bases for the A/V boundary oracle;
    # Matroska's millisecond packet timestamps quantize native source seeks.
    path = root / (label+(".nut" if sound else ".mkv"))
    raw = root / (label+".rgb48")
    values = array("H")
    for frame in range(SOURCE_FRAMES):
        if pattern is not None:
            values.extend(pattern)
        else:
            rgb = color if color is not None else coded(frame)
            values.extend(array("H", [value*257 for value in rgb])*(SIZE[0]*SIZE[1]))
    raw.write_bytes(values.tobytes())
    args = [ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo",
            "-pix_fmt", "rgb48le", "-s", f"{SIZE[0]}x{SIZE[1]}",
            "-r", str(rational(fps)), "-i", raw]
    if sound:
        audio = root / (label+".wav")
        pcm = array("h")
        for frame in range(SOURCE_FRAMES):
            pcm.extend(array("h", [1000+frame*20, -1500-frame*17])*
                       (sample(frame+1, fps)-sample(frame, fps)))
        with wave.open(str(audio), "wb") as output:
            output.setparams((2, 2, SR, 0, "NONE", "not compressed"))
            output.writeframes(pcm.tobytes())
        args += ["-i", audio, "-c:a", "pcm_s16le"]
    args += ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "gbrp16le", path]
    run(args)
    decoded = run([ffmpeg, "-nostdin", "-v", "error", "-i", path,
                   "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb48le", "pipe:1"]).stdout
    assert decoded == values.tobytes(), "Independent source decode must preserve every authored16-bit code"
    if sound:
        decoded_pcm=run([ffmpeg,"-nostdin","-v","error","-i",path,"-map","0:a:0",
                         "-f","s16le","pipe:1"]).stdout
        assert decoded_pcm==pcm.tobytes(), "Independent source decode must preserve every authored PCM sample"
    return dict(path=path, fps=fps, color=color, sound=sound, pattern=pattern,
                ffmpeg=ffmpeg,fitted={})


def track(ident, owner, order):
    return dict(id=ident, owner=owner, kind=0, name=f"V{ident}", order=order,
                hidden=False, muted=False, locked=False, solo=False, gain=1, pan=0, height=54)


def clip(ident, owner, lane, source=0, nested=0, start=0, length=16, source_in=0):
    return dict(id=ident, owner=owner, source=source, nested=nested, source_in=source_in,
                length=length, start=start, track=lane, group=0, enabled=True,
                selected=False, fade_in=0, fade_out=0, gain=1, pan=0, speed=1, reverse=False)


def project(sources, parent_fps=30, child_fps=30, source_id=7):
    return dict(schema="air.editor.project", revision=2, active=2, source_bounds=0,
                monitor_source=source_id, next_id=100,
                program=dict(playing=False, frame=2, mark_in=-1, mark_out=-1, rate=1, looping=False),
                monitor=dict(playing=False, frame=0, mark_in=-1, mark_out=-1, rate=1, looping=False),
                bins=[dict(id=1, name="Media", parent=0)],
                sequences=[dict(id=2, name="Parent", fps=parent_fps, width=SIZE[0], height=SIZE[1]),
                           dict(id=10, name="Child", fps=child_fps, width=SIZE[0], height=SIZE[1])],
                sources=[dict(id=ident, path=str(info["path"]), name=info["path"].name,
                              bin=1, frames=SOURCE_FRAMES, fps=info["fps"], width=SIZE[0], height=SIZE[1],
                              has_video=True, has_audio=info["sound"], audio_rate=SR,
                              audio_channels=2, online=True) for ident, info in sources.items()],
                tracks=[track(3,2,0), track(4,2,1), track(11,10,0)],
                clips=[clip(20,2,3,source=8,length=16),
                       clip(30,2,4,nested=10,start=2,length=12,source_in=3),
                       clip(40,10,11,source=source_id,start=1,length=32,source_in=5)],
                transitions=[], keys=[], markers=[], subtitles=[], filters=[],
                filter_params=[], filter_text_params=[], names=[])


def keyed(doc, ident, owner, name, value):
    if name not in doc["names"]:
        doc["names"].append(name)
    doc["keys"].append(dict(clip=ident, owner=owner, param=doc["names"].index(name)+1,
                            frame=0, value=value, interp=4))


def effect(doc, ident, kind, params):
    effect_id = 1000+len(doc["filters"])
    doc["filters"].append(dict(id=effect_id, clip=ident, kind=kind,
                               order=sum(item["clip"]==ident for item in doc["filters"]), enabled=True))
    doc["filter_params"] += [dict(filter=effect_id, name=name, value=value) for name, value in params.items()]
    doc["next_id"] = max(doc["next_id"], effect_id+1)


def fit(image, size):
    width, height, pixels = image
    target_width, target_height = size
    scale = min(target_width/width, target_height/height)
    inner_width, inner_height = math.floor(width*scale+.5), math.floor(height*scale+.5)
    left, top = (target_width-inner_width)//2, (target_height-inner_height)//2
    out = []
    for y in range(target_height):
        for x in range(target_width):
            if left <= x < left+inner_width and top <= y < top+inner_height:
                sx, sy = (x-left)*width//inner_width, (y-top)*height//inner_height
                out.append(pixels[sy*width+sx])
            else:
                out.append((0.,0.,0.,0.))
    return target_width, target_height, out


def rgba_over(base, upper):
    alpha = upper[3]+base[3]*(1-upper[3])
    if not alpha:
        return (0.,0.,0.,0.)
    return tuple((upper[c]*upper[3]+base[c]*base[3]*(1-upper[3]))/alpha for c in range(3))+(alpha,)


def leaf_image(source, frame, size):
    if size==SIZE:
        if source["pattern"] is not None:
            values=source["pattern"]
            pixels=[tuple(value/65535 for value in values[n:n+3])+(1.,) for n in range(0,len(values),3)]
        else:
            rgb=source["color"] or coded(frame)
            pixels=[tuple(value/255 for value in rgb)+(1.,)]*(SIZE[0]*SIZE[1])
        return SIZE[0],SIZE[1],pixels
    # The existing native leaf decoder uses bicubic, accurate-rounding 16-bit
    # conversion into an even fitted rectangle. Independently decode that
    # source reference with shared FFmpeg, never with a Genesis output. The
    # completed child-to-parent FLOATDIM fit below remains nearest sampling.
    width,height=size
    if SIZE[0]*height>=width*SIZE[1]:
        inner_width,inner_height=width,width*SIZE[1]//SIZE[0]
    else:
        inner_width,inner_height=height*SIZE[0]//SIZE[1],height
    inner_width=max(2,inner_width)&~1
    inner_height=max(2,inner_height)&~1
    if size not in source["fitted"]:
        payload=run([source["ffmpeg"],"-nostdin","-v","error","-i",source["path"],
                     "-map","0:v:0","-vf",f"scale={inner_width}:{inner_height}:flags=bicubic+accurate_rnd",
                     "-f","rawvideo","-pix_fmt","rgba64le","pipe:1"]).stdout
        decoded=array("H");decoded.frombytes(payload)
        assert len(decoded)==SOURCE_FRAMES*inner_width*inner_height*4
        source["fitted"][size]=decoded
    data=source["fitted"][size]
    left,top=(width-inner_width)//2,(height-inner_height)//2
    pixels=[(0.,0.,0.,0.)]*(width*height)
    offset=frame*inner_width*inner_height*4
    for y in range(inner_height):
        for x in range(inner_width):
            at=offset+(y*inner_width+x)*4
            pixels[(y+top)*width+x+left]=tuple(data[at+c]/65535 for c in range(4))
    return width,height,pixels


def oracle(doc, sources, ident, frame, ancestors=()):
    assert ident not in ancestors
    sequence = next(item for item in doc["sequences"] if item["id"]==ident)
    size = sequence["width"], sequence["height"]
    transitions = [value for value in doc["transitions"] if value["owner"]==ident and
                   value["center"]-value["duration"]//2 <= frame < value["center"]-value["duration"]//2+value["duration"]]
    if transitions:
        # The independently authored seam is one touching cut on one child lane.
        # Endpoints hold their nearest clip frame; alpha is weighted coverage,
        # while the RGB result stays straight for the enclosing parent.
        assert len(transitions)==1
        transition = transitions[0]
        assert doc["names"][transition["kind"]-1]=="crossfade"
        outgoing = next(value for value in doc["clips"] if value["owner"]==ident and value["track"]==transition["track"] and value["start"]+value["length"]==transition["center"])
        incoming = next(value for value in doc["clips"] if value["owner"]==ident and value["track"]==transition["track"] and value["start"]==transition["center"])
        images = []
        for item in (outgoing,incoming):
            one = copy.deepcopy(doc)
            one["transitions"] = []
            one["clips"] = [value for value in one["clips"] if value["owner"]!=ident or value["id"]==item["id"]]
            held = max(item["start"],min(item["start"]+item["length"]-1,frame))
            images.append(oracle(one,sources,ident,held,ancestors))
        progress = Fraction(frame-(transition["center"]-transition["duration"]//2),transition["duration"])
        mixed = []
        for left,right in zip(images[0][2],images[1][2]):
            alpha = left[3]*(1-progress)+right[3]*progress
            mixed.append(tuple(float((left[c]*left[3]*(1-progress)+right[c]*right[3]*progress)/alpha) if alpha else 0.
                               for c in range(3))+(float(alpha),))
        return size[0],size[1],mixed
    image = [tuple([0.]*4)]*(size[0]*size[1])
    # Saved track order increases from the bottom lane to the top lane.
    lanes = sorted((item for item in doc["tracks"] if item["owner"]==ident), key=lambda item:item["order"])
    for lane in lanes:
        if lane["hidden"]:
            continue
        for item in doc["clips"]:
            if item["owner"]!=ident or item["track"]!=lane["id"] or not item["enabled"] or not item["start"]<=frame<item["start"]+item["length"]:
                continue
            local = frame-item["start"]
            position = item["length"]-1-local if item["reverse"] else local
            owner_time = Fraction(item["source_in"])+position*rational(item["speed"])
            if item["nested"]:
                child = next(value for value in doc["sequences"] if value["id"]==item["nested"])
                child_frame = math.floor(owner_time*rational(child["fps"])/rational(sequence["fps"]))
                layer = oracle(doc,sources,item["nested"],child_frame,ancestors+(ident,))
            else:
                source = sources[item["source"]]
                source_frame = math.floor(owner_time*rational(source["fps"])/rational(sequence["fps"]))
                assert 0<=source_frame<SOURCE_FRAMES
                layer=leaf_image(source,source_frame,size)
            layer = fit(layer,size)
            pixels = list(layer[2])
            for operation in sorted((value for value in doc["filters"] if value["clip"]==item["id"] and value["enabled"]), key=lambda value:value["order"]):
                params = {value["name"]:value["value"] for value in doc["filter_params"] if value["filter"]==operation["id"]}
                if operation["kind"]=="brightness":
                    pixels = [tuple(max(0.,min(1.,value+params["level"]-1)) for value in pixel[:3])+(pixel[3],) for pixel in pixels]
                elif operation["kind"]=="contrast":
                    pixels = [tuple(max(0.,min(1.,(value-.5)*params["level"]+.5)) for value in pixel[:3])+(pixel[3],) for pixel in pixels]
                elif operation["kind"]=="crop":
                    pixels = [pixel if params.get("left",0)*size[0]<=n%size[0]<size[0]*(1-params.get("right",0)) and
                              params.get("top",0)*size[1]<=n//size[0]<size[1]*(1-params.get("bottom",0))
                              else pixel[:3]+(0.,) for n,pixel in enumerate(pixels)]
                elif operation["kind"]=="mask":
                    # A centered rectangle's feather is linear coverage of its
                    # Chebyshev-distance band. Applying it twice to RGB and
                    # alpha would fail this independent straight-alpha oracle.
                    masked = []
                    for n,pixel in enumerate(pixels):
                        dx = abs(2*(n%size[0]+.5)/size[0]-1)
                        dy = abs(2*(n//size[0]+.5)/size[1]-1)
                        coverage = max(0.,min(1.,(1-max(dx,dy))/max(params["feather"],.0001)))
                        if params.get("invert",0):
                            coverage=1-coverage
                        masked.append(pixel[:3]+(pixel[3]*coverage,))
                    pixels=masked
                elif operation["kind"]=="sharpen":
                    # Independent discrete Laplacian at the child's native
                    # one-pixel radius, including clamped image boundaries.
                    sharpened=[]
                    for n,pixel in enumerate(pixels):
                        x,y=n%size[0],n//size[0]
                        adjacent=(y*size[0]+max(0,x-1),y*size[0]+min(size[0]-1,x+1),
                                  max(0,y-1)*size[0]+x,min(size[1]-1,y+1)*size[0]+x)
                        sharpened.append(tuple(max(0.,min(1.,pixel[c]+params["amount"]*(4*pixel[c]-sum(pixels[p][c] for p in adjacent))))
                                               for c in range(3))+(pixel[3],))
                    pixels=sharpened
                else:
                    raise AssertionError(("No authored oracle for effect",operation))
            opacity = next((key["value"] for key in doc["keys"] if key["clip"]==item["id"] and doc["names"][key["param"]-1]=="opacity"),1.)
            fade = min(1., local/item["fade_in"]) if item["fade_in"] else 1.
            if item["fade_out"]:
                fade = min(fade,(item["length"]-local)/item["fade_out"])
            image = [rgba_over(base,pixel[:3]+(pixel[3]*opacity*fade,)) for base,pixel in zip(image,pixels)]
    return size[0],size[1],image


def cases(sources):
    result = []
    for name,parent,child,source_id in (("30-24-24",30,24,7),("24-30-5994",24,30,9),("5994-24-30",60000/1001,24,12)):
        result.append((name,project(sources,parent,child,source_id)))
    base = project(sources)
    base["clips"][-1]["source"] = 12
    result.append(("pcm-video-aligned",copy.deepcopy(base)))
    for name,reverse,speed in (("parent-reverse",True,1),("parent-speed2",False,2),("parent-half-speed",False,.5)):
        doc = copy.deepcopy(base)
        doc["clips"][1].update(reverse=reverse,speed=speed)
        result.append((name,doc))
    leaf_reverse = copy.deepcopy(base)
    leaf_reverse["clips"][-1].update(reverse=True)
    result.append(("child-reverse",leaf_reverse))
    trimmed=copy.deepcopy(base)
    trimmed["clips"][1].update(start=4,length=8,source_in=7)
    result.append(("parent-trim-and-source-in",trimmed))
    hierarchy=copy.deepcopy(base)
    hierarchy["sequences"].append(dict(id=50,name="Grandchild",fps=24,width=64,height=36))
    hierarchy["tracks"].append(track(51,50,0))
    hierarchy["clips"][-1].update(source=0,nested=50)
    hierarchy["clips"].append(clip(52,50,51,source=12,start=2,length=48,source_in=7))
    result.append(("two-compound-owner-fps-levels",hierarchy))
    opacity = copy.deepcopy(base)
    keyed(opacity,30,2,"opacity",.5)
    result.append(("parent-opacity",opacity))
    faded=copy.deepcopy(base)
    faded["clips"][1].update(fade_in=4,fade_out=4)
    result.append(("parent-alpha-fades",faded))
    empty=copy.deepcopy(base)
    empty["clips"]=[item for item in empty["clips"] if item["owner"]!=10]
    result.append(("empty-child-transparency",empty))
    disabled=copy.deepcopy(base)
    disabled["clips"][-1]["enabled"]=False
    result.append(("disabled-child-transparency",disabled))
    hidden=copy.deepcopy(base)
    hidden["tracks"][-1]["hidden"]=True
    result.append(("hidden-child-transparency",hidden))
    caption=copy.deepcopy(empty)
    caption["clips"][1].update(start=0,length=16,source_in=0)
    caption["sequences"][1].update(width=256,height=144)
    caption["subtitles"]=[dict(id=55,owner=10,start=5,finish=9,text="AIR")]
    keyed(caption,30,2,"opacity",.5)
    result.append(("title-only-child-timed-alpha",caption))
    gap = copy.deepcopy(base)
    gap["clips"][1].update(start=0,length=16,source_in=0)
    gap["clips"][-1].update(start=0,length=5,source_in=0)
    gap["clips"].append(dict(gap["clips"][-1],id=41,start=10,length=6,source_in=10))
    result.append(("transparent-child-gap",gap))
    crop = copy.deepcopy(base)
    effect(crop,30,"crop",dict(left=.25,right=.25,top=.25,bottom=.25))
    result.append(("parent-crop-matte",crop))
    for name,target in (("parent-mask-coverage",30),("bottom-child-mask-coverage",40)):
        masked=copy.deepcopy(base)
        keyed(masked,30,2,"opacity",.5)
        effect(masked,target,"mask",dict(feather=.25,invert=0))
        result.append((name,masked))
    aspect = copy.deepcopy(base)
    aspect["sequences"][1].update(width=32,height=64)
    result.append(("portrait-child-aspect",aspect))
    sharpen=copy.deepcopy(aspect)
    sharpen["clips"][-1]["source"]=15
    effect(sharpen,40,"sharpen",dict(amount=.5))
    result.append(("portrait-child-native-sharpen-radius",sharpen))
    group = copy.deepcopy(base)
    group["tracks"].append(track(13,10,1))
    group["clips"].append(clip(42,10,13,source=14,length=32))
    keyed(group,42,10,"opacity",.5)
    effect(group,30,"contrast",dict(level=2.))
    result.append(("nonlinear-parent-after-child-sum",group))
    repeated = copy.deepcopy(base)
    repeated["clips"][1].update(length=6,start=0,source_in=3)
    repeated["clips"].append(dict(repeated["clips"][1],id=31,start=8,source_in=11,reverse=True))
    result.append(("repeated-child-distinct-instances",repeated))
    edited = copy.deepcopy(repeated)
    effect(edited,40,"brightness",dict(level=1.125))
    result.append(("descendant-edit-repeated-instances",edited))
    seam=copy.deepcopy(base)
    seam["clips"][1].update(start=0,length=16,source_in=0)
    seam["clips"][-1].update(start=0,length=8,source_in=0)
    seam["clips"].append(dict(seam["clips"][-1],id=41,start=8,length=8,source_in=16))
    seam["names"].append("crossfade")
    seam["transitions"]=[dict(id=50,owner=10,track=11,center=8,duration=6,kind=len(seam["names"]))]
    keyed(seam,30,2,"opacity",.5)
    result.append(("child-crossfade-seam",seam))
    return result


def pixels(ffmpeg, path, size, master=False):
    args = [ffmpeg,"-nostdin","-v","error","-i",path,"-map","0:v:0"]
    if not master:
        args += ["-vf",f"scale={size[0]}:{size[1]}:flags=neighbor","-frames:v","1"]
    payload = run(args+["-f","rawvideo","-pix_fmt","rgb48le" if master else "rgb24","pipe:1"]).stdout
    values = array("H") if master else bytearray()
    if master:
        values.frombytes(payload)
    else:
        values.extend(payload)
    return values


def compare(values, expected, scale, label):
    wanted = [pixel[channel]*pixel[3] for pixel in expected[2] for channel in range(3)]
    assert len(values)==len(wanted),(label,len(values),len(wanted))
    errors = [abs(actual/scale-target) for actual,target in zip(values,wanted)]
    worst = max(errors)
    limit = 5/65535 if scale==65535 else 1.1/255
    at = errors.index(worst)
    assert worst <= limit,(label,worst,limit,dict(pixel=at//3,channel=at%3,actual=values[at]/scale,expected=wanted[at]))
    return worst


def compare_caption(values, scale, frame):
    """Test grayscale caption coverage without using Genesis's glyph raster.

    Authored white text/black shadow over a transparent child has grayscale
    straight RGB. Its outer opacity is .5. Three output channels independently
    determine coverage and gray intensity against the known blue background.
    Exact glyph shapes are intentionally outside this oracle's scope.
    """
    tolerance=5/65535 if scale==65535 else 1.1/255
    background=tuple(value/255 for value in BACKGROUND)
    active=5<=frame<9
    worst=0.
    changed=[]
    white=0
    for at in range(SIZE[0]*SIZE[1]):
        pixel=tuple(values[at*3+c]/scale for c in range(3))
        difference=max(abs(pixel[c]-background[c]) for c in range(3))
        if not active:
            worst=max(worst,difference)
            assert difference<=tolerance,("Timed title leaked outside child interval",frame,at,pixel)
            continue
        if difference<=tolerance:
            continue
        changed.append((at%SIZE[0],at//SIZE[0]))
        alpha=1-(pixel[2]-pixel[0])/(background[2]-background[0])
        premultiplied_gray=pixel[0]-background[0]*(1-alpha)
        error=abs(pixel[1]-(pixel[0]+(background[1]-background[0])*(1-alpha)))
        worst=max(worst,error)
        uncertainty=tolerance*4/(background[2]-background[0])
        assert -uncertainty<=alpha<=.5+uncertainty,("Child title lost parent alpha",frame,at,alpha)
        assert -uncertainty<=premultiplied_gray<=alpha+uncertainty,("Title is not grayscale coverage",frame,at,pixel)
        assert error<=tolerance,("Caption straight-alpha channel identity",frame,at,error)
        white+=pixel[0]>background[0]+.02
    if active:
        assert len(changed)>=2 and white>=1,("Empty child's timed caption did not render",frame,changed)
        assert all(4<=x<62 and 26<=y<36 for x,y in changed),("Caption moved outside lower title region",frame,changed)
    return worst


@contextmanager
def workspace(report):
    with tempfile.TemporaryDirectory(prefix="genesis-nested-picture-") as temporary:
        root=Path(temporary)
        try:
            yield root
        except BaseException:
            # Preserve bounded authored projects and mailbox diagnostics before
            # TemporaryDirectory removes the failing request's private files.
            diagnostics={}
            budget=524288
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix in (".air",".json",".jsonl",".txt",".id",".log",".tsv") and path.stat().st_size<=65536:
                    payload=path.read_bytes()
                    if len(payload)>budget:
                        continue
                    diagnostics[str(path.relative_to(root))]=payload.decode("utf-8",errors="replace")
                    budget-=len(payload)
            report["failure_diagnostics"]=diagnostics
            raise


def pcm_identity(ffmpeg, movie, doc):
    payload=run([ffmpeg,"-nostdin","-v","error","-i",movie,"-map","0:a:0",
                 "-ac","2","-ar",str(SR),"-f","f32le","pipe:1"]).stdout
    values=array("f")
    values.frombytes(payload)
    assert len(values)==sample(16,30)*2,("A/V exact endpoint",len(values))
    worst=0.
    worst_at=None
    for n in range(sample(16,30)):
        frame=n//1600
        selected=frame+5
        expected=(1000+selected*20,-1500-selected*17) if 2<=frame<14 else (0,0)
        for channel in (0,1):
            actual=values[n*2+channel]
            assert math.isfinite(actual)
            error=abs(actual-expected[channel]/32768)
            if error>worst:
                worst=error
                worst_at=dict(sample=n,channel=channel,actual=actual,expected=expected[channel]/32768)
    assert worst<=2/8388608,("Authored PCM and video share exact nested source/placement",worst,worst_at,
                          [list(values[sample(frame,30)*2:sample(frame,30)*2+2]) for frame in range(16)])
    return dict(sample_frames=len(values)//2,worst_float_error=worst,
                source_frame_for_active_picture="parent_frame+5",scope="saved lossless A/V identity; no device cadence claim")


def refusal_cases(base):
    result=[]
    cycle=copy.deepcopy(base)
    cycle["clips"][-1].update(source=0,nested=2)
    result.append(("cycle",cycle,"NESTED_CYCLE"))
    missing=copy.deepcopy(base)
    missing["clips"][1]["nested"]=999999
    # Export performs its existing nested-audio preflight before video; retain
    # both exact, subsystem-specific missing-sequence refusal contracts.
    result.append(("missing-sequence",missing,dict(preview="GA_VIDEO_NESTED_SOURCE",export="GA_AUDIO_NESTED_PROTOCOL")))
    source_missing=copy.deepcopy(base)
    source_missing["clips"][-1]["source"]=9
    next(value for value in source_missing["sources"] if value["id"]==9)["path"]+=".missing"
    result.append(("missing-online-picture-source",source_missing,"VIDEO_NESTED_SOURCE"))
    dimensions=copy.deepcopy(base)
    dimensions["sequences"][1]["width"]=8193
    result.append(("canvas-dimension-capacity",dimensions,"VIDEO_NESTED_PROTOCOL"))
    pixels=copy.deepcopy(base)
    pixels["sequences"][1].update(width=8192,height=4096)
    result.append(("canvas-pixel-capacity",pixels,"VIDEO_NESTED_CAPACITY"))
    history=copy.deepcopy(base)
    effect(history,30,"stabilize",dict(amount=1.))
    result.append(("parent-temporal-history",history,"VIDEO_NESTED_HISTORY"))
    deep=copy.deepcopy(base)
    previous=deep["clips"][-1]
    for n in range(16):
        sequence_id=100+n
        track_id=200+n
        deep["sequences"].append(dict(deep["sequences"][1],id=sequence_id,name=f"Deep{n}"))
        deep["tracks"].append(track(track_id,sequence_id,0))
        previous.update(source=0,nested=sequence_id,source_in=0,length=64,start=0)
        current=clip(300+n,sequence_id,track_id,source=12,length=64)
        deep["clips"].append(current)
        previous=current
    deep["next_id"]=1000
    result.append(("depth-capacity",deep,"NESTED_CAPACITY"))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary",type=Path,required=True)
    parser.add_argument("--worker",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--expect-refusal",action="store_true")
    parser.add_argument("--case",action="append",help="Run named positive cases for a bounded reproduction")
    parser.add_argument("--refusals-only",action="store_true",help="Run the coded refusal matrix without positive exports")
    parser.add_argument("--refusal",action="append",help="Select named refusal cases for a bounded reproduction")
    args = parser.parse_args()
    binary,worker = args.binary.resolve(),args.worker.resolve()
    ffmpeg = tool(worker,"ffmpeg")
    report = dict(schema="genesis.nested_picture.v1",passed=False,binary_sha256=sha(binary),worker_sha256=sha(worker),cases=[])
    try:
        with workspace(report) as root:
            pattern=array("H")
            for y in range(SIZE[1]):
                for x in range(SIZE[0]):
                    pattern.extend([32768+round(8192*math.sin(2*math.pi*x/8))]*3)
            sources = {7:source(root,ffmpeg,24,"coded24",sound=True),
                       8:source(root,ffmpeg,30,"background",BACKGROUND),
                       9:source(root,ffmpeg,60000/1001,"coded5994"),
                       12:source(root,ffmpeg,30,"coded30",sound=True),
                       14:source(root,ffmpeg,30,"overlay",(190,24,48)),
                       15:source(root,ffmpeg,30,"sine16",pattern=pattern)}
            source_hashes = {value["path"]:sha(value["path"]) for value in sources.values()}
            env = dict(os.environ,GENESIS_GCOMPOSE=str(worker),GENESIS_SCRATCH=str(root/"scratch Ω literal%20 space"))
            env.pop("GENESIS_FAKE_PROVIDER",None)
            # A known-flat source/control must pass the same exact16-bit oracle
            # before the unsupported baseline or any compound candidate runs.
            control=project(sources)
            control["clips"][1].update(source=12,nested=0)
            control_path=root/"flat-control.air"
            control_path.write_text(json.dumps(control),encoding="utf-8")
            control_movie=root/"flat-control.mkv"
            run([binary,"export",control_movie,control_path],env)
            control_data=pixels(ffmpeg,control_movie,SIZE,True)
            frame_size=SIZE[0]*SIZE[1]*3
            assert len(control_data)==16*frame_size
            control_worst=max(compare(control_data[n*frame_size:(n+1)*frame_size],oracle(control,sources,2,n),65535,("flatcontrol",n)) for n in range(16))
            report["flat_control"]=dict(master_frames=16,worst=control_worst)
            for name,doc in cases(sources):
                if args.refusals_only:
                    continue
                if args.case and name not in args.case:
                    continue
                project_path = root/(name+".air")
                project_path.write_text(json.dumps(doc),encoding="utf-8")
                original = sha(project_path)
                if args.expect_refusal:
                    outcomes = []
                    for verb,suffix in (("preview",".png"),("export",".mkv")):
                        output = root/(name+suffix)
                        done = run([binary,verb,output,project_path],env,accepted=False)
                        message = (done.stdout+done.stderr).decode("utf-8",errors="replace")
                        assert done.returncode!=0 and "nested sequences are not rendered yet" in message,(verb,done.returncode,message)
                        assert not output.exists() and not list(root.glob(output.name+".partial*")),("Refusal published output",output)
                        outcomes.append(dict(verb=verb,returncode=done.returncode,message=message.strip()))
                    assert sha(project_path)==original
                    report["cases"].append(dict(name=name,confirmed_refusal=True,outcomes=outcomes,project_unchanged=True))
                    break
                master = root/(name+".mkv")
                run([binary,"export",master,project_path],env)
                assert sha(project_path)==original,(name,"Export changed authored project")
                data = pixels(ffmpeg,master,SIZE,True)
                frame_size = SIZE[0]*SIZE[1]*3
                assert len(data)==16*frame_size,(name,"Exact master frame count",len(data)//frame_size)
                def accepted(values,scale,frame,kind):
                    if name=="title-only-child-timed-alpha":
                        return compare_caption(values,scale,frame)
                    return compare(values,oracle(doc,sources,2,frame),scale,(name,kind,frame))
                master_worst = max(accepted(data[n*frame_size:(n+1)*frame_size],65535,n,"master") for n in range(16))
                preview_worst = 0.
                first_preview = None
                for index,frame in enumerate((0,2,5,8,11,13,15,0)):
                    doc["program"]["frame"] = frame
                    project_path.write_text(json.dumps(doc),encoding="utf-8")
                    before_request=sha(project_path)
                    output = root/f"{name}-{index}.png"
                    run([binary,"preview",output,project_path],env)
                    assert sha(project_path)==before_request,(name,"Preview changed authored request")
                    preview_worst = max(preview_worst,accepted(pixels(ffmpeg,output,SIZE),255,frame,"preview"))
                    if first_preview is None:
                        first_preview = output.read_bytes()
                    elif index==7:
                        assert output.read_bytes()==first_preview,(name,"Rewind changed frame-zero image")
                row=dict(name=name,master_frames=16,preview_frames=8,master_worst=master_worst,preview_worst=preview_worst,exact_rewind=True,project_bytes_unchanged=True)
                if name=="pcm-video-aligned":
                    row["audio_identity"]=pcm_identity(ffmpeg,master,doc)
                if name=="nonlinear-parent-after-child-sum":
                    per_leaf=copy.deepcopy(doc)
                    per_leaf["filters"]=[]
                    per_leaf["filter_params"]=[]
                    for item in per_leaf["clips"]:
                        if item["owner"]==10:
                            effect(per_leaf,item["id"],"contrast",dict(level=2.))
                    correct=oracle(doc,sources,2,5)[2]
                    wrong=oracle(per_leaf,sources,2,5)[2]
                    separation=max(abs(a[c]-b[c]) for a,b in zip(correct,wrong) for c in range(3))
                    assert separation>.02,("Nonlinear parent oracle must distinguish per-leaf grade",separation)
                    row["independent_parent_vs_per_leaf_separation"]=separation
                report["cases"].append(row)
            if not args.expect_refusal and not args.case:
                report["refusals"]=[]
                for name,doc,code in refusal_cases(project(sources)):
                    if args.refusal and name not in args.refusal:
                        continue
                    request=root/("refused-"+name+".air")
                    request.write_text(json.dumps(doc),encoding="utf-8")
                    original=sha(request)
                    for verb,suffix in (("preview",".png"),("export",".mkv")):
                        output=root/("refused-"+name+suffix)
                        done=run([binary,verb,output,request],env,False)
                        message=(done.stdout+done.stderr).decode("utf-8",errors="replace")
                        expected_code=code[verb] if isinstance(code,dict) else code
                        assert done.returncode!=0 and expected_code in message,(name,verb,expected_code,done.returncode,message)
                        assert not output.exists() and not list(root.glob(output.name+".partial*"))
                        assert sha(request)==original
                    report["refusals"].append(dict(name=name,code=code,no_published_output=True,project_bytes_unchanged=True))
                assert not args.refusal or len(report["refusals"])==len(set(args.refusal)),("Unknown selected refusal",args.refusal)
            assert all(sha(path)==digest for path,digest in source_hashes.items())
            assert not args.case or len(report["cases"])==len(set(args.case)),("Unknown selected positive case",args.case)
            report.update(passed=True,source_bytes_unchanged=True,expected_baseline_refusal=args.expect_refusal,
                          path_edges="session scratch has spaces, Unicode Omega and literal percent20",
                          title_scope="timing, transparent background and grayscale straight-alpha coverage; glyph raster excluded")
    except BaseException as problem:
        report["failure"] = repr(problem)
        raise
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(dict(passed=True,cases=len(report["cases"]),baseline_refusal=args.expect_refusal)))


if __name__=="__main__":
    main()
