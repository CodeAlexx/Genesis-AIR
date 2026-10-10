"""Ordered title/grade pixels and unique per-camera title scratch preparation."""

import argparse
from array import array
import copy
from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile

from filter_order import run
from media_runtime import tool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    width = height = 256
    if args.diagnostics:
        args.diagnostics.mkdir(parents=True, exist_ok=True)
    context = nullcontext(str(args.diagnostics.resolve())) if args.diagnostics else tempfile.TemporaryDirectory(prefix="genesis-ordered-title-")
    with context as temporary:
        root = Path(temporary)
        raw, source = root / "source.rgb", root / "source.mkv"
        raw.write_bytes(bytes((80, 110, 140))*(width*height))
        run([ffmpeg,"-nostdin","-v","error","-f","rawvideo","-pix_fmt","rgb24",
             "-s","256x256","-r","30","-i",raw,"-frames:v","1","-c:v","ffv1",
             "-pix_fmt","bgr0",source])
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root/"scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        project = root/"sequence.air"
        run([binary,"probe",source,root/"ui.png",project],env)
        document = json.loads(project.read_text(encoding="utf-8"))
        document["sequences"][0].update(width=width,height=height,fps=30)
        document["clips"][0].update(length=1)
        base_clip = document["clips"][0]

        def render(doc, name):
            project.write_text(json.dumps(doc),encoding="utf-8")
            master, preview = root/f"{name}.mkv", root/f"{name}.png"
            run([binary,"preview",preview,project],env)
            run([binary,"export",master,project],env)
            decoded = run([ffmpeg,"-nostdin","-v","error","-i",master,"-frames:v","1",
                           "-f","rawvideo","-pix_fmt","rgb48le","pipe:1"])
            assert len(decoded)==width*height*6
            values=array("H");values.frombytes(decoded)
            # Independently decode and apply the specified integer nearest fit:
            # native pixel floor(x*256/360), with opaque black aspect bars.
            native=run([ffmpeg,"-nostdin","-v","error","-i",master,"-frames:v","1",
                        "-f","rawvideo","-pix_fmt","rgb24","pipe:1"])
            fitted=bytearray(640*360*3)
            for y in range(360):
                for x in range(360):
                    start=((y*256//360)*256+x*256//360)*3
                    target=(y*640+140+x)*3
                    fitted[target:target+3]=native[start:start+3]
            shown=run([ffmpeg,"-nostdin","-v","error","-i",preview,"-frames:v","1",
                       "-f","rawvideo","-pix_fmt","rgb24","pipe:1"])
            assert len(shown)==len(fitted)==640*360*3
            assert max(abs(a-b) for a,b in zip(shown,fitted))<=2, name
            assert not list(root.rglob("*.ordered-title*")), "ordered title rasters leaked"
            assert not list(root.rglob("*.prepared-count")), "prepared-slot count leaked"
            return values

        images={}
        for name, order in (("plain",()),("title",("text",)),
                            ("title_then_dark",("text","brightness")),
                            ("dark_then_title",("brightness","text"))):
            doc=copy.deepcopy(document)
            doc.update(filters=[],filter_params=[],filter_text_params=[],keys=[])
            for at,kind in enumerate(order):
                fid=80 if kind=="text" else 81
                doc["filters"].append(dict(id=fid,clip=base_clip["id"],kind=kind,order=at,enabled=True))
                doc["filter_params"].append(dict(filter=fid,name="size" if kind=="text" else "level",
                                                  value=200.0 if kind=="text" else .5))
                if kind=="text":doc["filter_text_params"].append(dict(filter=fid,name="content",value="AIR"))
            doc["filters"].sort(key=lambda value:value["id"])
            doc["next_id"]=82
            images[name]=render(doc,name)
        assert max(images["title"])>65000 and max(images["title_then_dark"])<33000
        assert max(images["dark_then_title"])>65000
        # Ink includes opaque dark outline/antialias pixels; two independent
        # source controls recover its premultiplied color and coverage without
        # assuming every covered pixel is white.
        controls={}
        for name,pixel in (("black",0),("white",255)):
            control_raw,control_source=root/f"{name}.rgb",root/f"{name}-source.mkv"
            control_raw.write_bytes(bytes((pixel,pixel,pixel))*(width*height))
            run([ffmpeg,"-nostdin","-v","error","-f","rawvideo","-pix_fmt","rgb24",
                 "-s","256x256","-r","30","-i",control_raw,"-frames:v","1","-c:v","ffv1",
                 "-pix_fmt","bgr0",control_source])
            doc=copy.deepcopy(document)
            doc["sources"][0]["path"]=str(control_source)
            doc.update(filters=[],filter_params=[],filter_text_params=[],keys=[])
            controls[name]=render(doc,name)
            doc["filters"]=[dict(id=80,clip=base_clip["id"],kind="text",order=0,enabled=True)]
            doc["filter_params"]=[dict(filter=80,name="size",value=200.0)]
            doc["filter_text_params"]=[dict(filter=80,name="content",value="AIR")]
            doc["next_id"]=81
            controls[name+"_title"]=render(doc,name+"_title")
        worst=0
        for base,title,after,before,black,white,black_title,white_title in zip(images["plain"],images["title"],
                                         images["title_then_dark"],images["dark_then_title"],
                                         controls["black"],controls["white"],controls["black_title"],controls["white_title"]):
            transmission=max(0,min(1,(white_title-black_title)/(white-black)))
            premultiplied=(black_title-transmission*black)/65535
            expected_after=max(0,title/65535-.5)
            expected_before=transmission*max(0,base/65535-.5)+premultiplied
            worst=max(worst,abs(after/65535-expected_after),abs(before/65535-expected_before))
        assert worst<=4/65535, worst
        print(f"Ordered titles: every native16-bit RGB sample matches independent title/grade formulas within {worst:.8f}; both full previews match fitted masters")

        full=copy.deepcopy(document)
        full.update(filters=[],filter_params=[],filter_text_params=[],keys=[])
        track_template=next(track for track in full["tracks"] if track["id"]==base_clip["track"])
        cameras=[]
        # PiP uses normalized top-left coordinates (not title center offsets).
        for index,(letter,x,y) in enumerate((("A",.075,.075),("B",.575,.075),("C",.075,.575),("D",.575,.575))):
            track=dict(track_template,id=20+index,order=4+index,name=f"Camera {letter}")
            full["tracks"].append(track)
            clip=dict(base_clip,id=30+index,track=track["id"])
            full["clips"].append(clip)
            title_id,position_id=40+index*2,41+index*2
            full["filters"].extend((dict(id=title_id,clip=clip["id"],kind="text",order=0,enabled=True),
                                    dict(id=position_id,clip=clip["id"],kind="size_position",order=1,enabled=True)))
            full["filter_params"].append(dict(filter=title_id,name="size",value=200.0))
            full["filter_params"].extend(dict(filter=position_id,name=name,value=value)
                                         for name,value in dict(x=x,y=y,w=.35,h=.35).items())
            full["filter_text_params"].append(dict(filter=title_id,name="content",value=letter))
            cameras.append((clip["id"],index))
        full["next_id"]=60
        combined=render(full,"four-cameras")
        camera_worst=0
        for clip_id,index in cameras:
            solo=copy.deepcopy(full)
            solo["clips"]=[clip for clip in solo["clips"] if clip["id"] in (base_clip["id"],clip_id)]
            solo["filters"]=[effect for effect in solo["filters"] if effect["clip"]==clip_id]
            isolated=render(solo,f"isolated-camera-{index}")
            x0,y0=(index%2)*128,(index//2)*128
            region=[]
            for y in range(y0,y0+128):
                for x in range(x0,x0+128):
                    offset=(y*width+x)*3
                    region.extend(isolated[offset:offset+3])
                    camera_worst=max(camera_worst,max(abs(a-b) for a,b in zip(combined[offset:offset+3],isolated[offset:offset+3])))
            assert max(region)>65000, (index,"camera title is absent")
        assert camera_worst<=2,camera_worst
        print(f"Four separately positioned camera titles match independent isolated-camera masters within {camera_worst}/65535; unique raster scratch cleanup passed")


if __name__=="__main__":main()
