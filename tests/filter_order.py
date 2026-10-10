"""Audit visible filter-stack ordering against independent sequential RGB math.

One constant, lossless frame removes decode, resizing and spatial effects from
the comparison. Reversed noncommutative filters must change preview and master;
repeated brightness filters must both execute, rather than overwrite a field.
"""

import argparse
import copy
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from PIL import Image
from media_runtime import tool


def run(argv, env=None):
    completed = subprocess.run([str(value) for value in argv], env=env,
                               capture_output=True, timeout=90,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert completed.returncode == 0, (argv, completed.stdout[-2000:], completed.stderr[-2000:])
    return completed.stdout


def sequential(pixel, filters, x=32, y=32):
    current = list(pixel)
    for kind, level in filters:
        if kind == "brightness":
            current = [value + level - 1 for value in current]
        elif kind == "contrast":
            current = [(value - .5) * level + .5 for value in current]
        elif x < 64 * level.get("left", 0):
            current = [0, 0, 0]
        current = [max(0, min(1, value)) for value in current]
    return current


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg, ffprobe = tool(worker, "ffmpeg"), tool(worker, "ffprobe")
    pixel = (80, 110, 140)
    cases = {
        "plain": [],
        "brightness": [("brightness", 1.08)],
        "contrast": [("contrast", 1.3)],
        "brightness_then_contrast": [("brightness", 1.08), ("contrast", 1.3)],
        "contrast_then_brightness": [("contrast", 1.3), ("brightness", 1.08)],
        "brightness_twice": [("brightness", 1.08), ("brightness", 1.06)],
        "brightness_twice_reversed": [("brightness", 1.06), ("brightness", 1.08)],
        "brightness_clip_then_dark": [("brightness", 1.8), ("brightness", .4)],
        "brightness_dark_then_clip": [("brightness", .4), ("brightness", 1.8)],
        "crop_then_brightness": [("crop", {"left": .25}), ("brightness", 1.08)],
        "brightness_then_crop": [("brightness", 1.08), ("crop", {"left": .25})],
    }
    entries = []
    with tempfile.TemporaryDirectory(prefix="genesis-filter-order-") as temporary:
        root = Path(temporary)
        raw, source = root / "source.rgb", root / "source.mkv"
        raw.write_bytes(bytes(pixel) * (64 * 64))
        run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", "64x64", "-r", "30", "-i", raw, "-frames:v", "1", "-c:v", "ffv1",
             "-pix_fmt", "bgr0", source])
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        project = root / "stack.air"
        run([binary, "probe", source, root / "ui.png", project], env)
        document = json.loads(project.read_text(encoding="utf-8"))
        document["sequences"][0].update(width=64, height=64, fps=30)
        document["clips"][0].update(length=1)
        clip = document["clips"][0]["id"]
        baseline = None
        for name, filters in cases.items():
            current = copy.deepcopy(document)
            current.update(filters=[], filter_params=[], filter_text_params=[], keys=[])
            for order, (kind, level) in enumerate(filters):
                # Stable instances retain their ids/parameters across Up/Down;
                # storage remains id order while only stack-order fields change.
                fid = 82 if kind == "crop" else 81 if kind == "contrast" or level in (1.06, .4) else 80
                current["filters"].append(dict(id=fid, clip=clip, kind=kind, order=order, enabled=True))
                params = level if isinstance(level, dict) else {"level": level}
                current["filter_params"].extend(dict(filter=fid, name=key, value=value)
                                                for key, value in params.items())
            current["filters"].sort(key=lambda value: value["id"])
            current["next_id"] = max([79]+[value["id"] for value in current["filters"]]) + 1
            project.write_text(json.dumps(current), encoding="utf-8")
            picture, master = root / f"{name}.png", root / f"{name}.mkv"
            run([binary, "preview", picture, project], env)
            run([binary, "export", master, project], env)
            info = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-of", "json", master]))
            video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
            assert (video["width"], video["height"], video["codec_name"], video["pix_fmt"]) == (64, 64, "ffv1", "gbrp16le"), video
            decoded = run([ffmpeg, "-nostdin", "-v", "error", "-i", master, "-frames:v", "1",
                           "-f", "rawvideo", "-pix_fmt", "rgba64le", "pipe:1"])
            assert len(decoded) == 64*64*8
            actual_master = [value / 65535 for value in struct.unpack_from("<4H", decoded)[:3]]
            if not any(kind == "crop" for kind, _ in filters):
                assert len(set(decoded[index:index+8] for index in range(0, len(decoded), 8))) == 1, "constant master is not uniform"
            with Image.open(picture) as image:
                assert image.size == (640, 360)
                actual_preview = [value / 255 for value in image.convert("RGB").getpixel((320, 180))]
                edge_preview = [value / 255 for value in image.convert("RGB").getpixel((185, 180))]
            # Measure the no-effect decode once, then apply independent operator
            # math to that signal. This separates source conversion/quantization
            # bias from actual stack semantics; it cannot hide a missed filter.
            if name == "plain":
                baseline = actual_master
                expected = [value/255 for value in pixel]
            else:
                expected = sequential(baseline, filters, 0, 0)
            center_expected = sequential(baseline, filters)
            edge_expected = sequential(baseline, filters, 8, 32)
            preview_error = max(abs(a-b) for a, b in zip(actual_preview, center_expected))
            edge_error = max(abs(a-b) for a, b in zip(edge_preview, edge_expected))
            master_error = max(abs(a-b) for a, b in zip(actual_master, expected))
            if name != "plain":
                master_error = max(abs(value/65535-expected_value)
                                   for position in range(64*64)
                                   for value, expected_value in zip(struct.unpack_from("<4H", decoded, position*8)[:3],
                                     sequential(baseline, filters, position%64, position//64)))
            entry = dict(case=name, stack=filters, expected_rgb=expected, preview_rgb=actual_preview,
                         master_rgb=actual_master, preview_error=preview_error, master_error=master_error,
                         edge_preview_rgb=edge_preview, edge_expected_rgb=edge_expected, edge_error=edge_error,
                         passed=preview_error <= 1.1/255 and edge_error <= 1.1/255 and
                         master_error <= (1/255 if name == "plain" else 3/65535))
            entries.append(entry)
            print(json.dumps(entry), flush=True)
        # A changing source with trim, fractional fps, speed, placement and fades
        # proves that ordered passes consume the resolved source once and apply
        # clip properties once, rather than addressing/regrading each stage.
        colors = [(48+frame*5, 60+frame*4, 80+frame*3) for frame in range(24)]
        raw.write_bytes(b"".join(bytes(color)*(64*64) for color in colors))
        timed_source=root/"retimed-source.mkv"
        run([ffmpeg,"-nostdin","-v","error","-f","rawvideo","-pix_fmt","rgb24",
             "-s","64x64","-r","24000/1001","-i",raw,"-c:v","ffv1","-pix_fmt","bgr0",timed_source])
        timed_project=root/"retimed.air"
        run([binary,"probe",timed_source,root/"retimed-ui.png",timed_project],env)
        timed=json.loads(timed_project.read_text(encoding="utf-8"))
        timed["sequences"][0].update(width=64,height=64,fps=30000/1001)
        timed["clips"][0].update(start=3,source_in=2,length=12,speed=1.25,fade_in=0,fade_out=0)
        timed.update(filters=[],filter_params=[],filter_text_params=[],keys=[])
        timed_project.write_text(json.dumps(timed),encoding="utf-8")
        plain_master=root/"retimed-plain.mkv"
        run([binary,"export",plain_master,timed_project],env)
        plain_frames=run([ffmpeg,"-nostdin","-v","error","-i",plain_master,"-f","rawvideo",
                          "-pix_fmt","rgb48le","pipe:1"])
        size=64*64*6
        assert len(plain_frames)==15*size
        timed["clips"][0].update(fade_in=8,fade_out=8)
        clip=timed["clips"][0]["id"]
        timed["filters"]=[dict(id=80,clip=clip,kind="brightness",order=0,enabled=True),
                          dict(id=81,clip=clip,kind="contrast",order=1,enabled=True)]
        timed["filter_params"]=[dict(filter=80,name="level",value=1.08),dict(filter=81,name="level",value=1.3)]
        timed["next_id"]=82
        timed_project.write_text(json.dumps(timed),encoding="utf-8")
        filtered_master=root/"retimed-stack.mkv"
        run([binary,"export",filtered_master,timed_project],env)
        filtered_frames=run([ffmpeg,"-nostdin","-v","error","-i",filtered_master,"-f","rawvideo",
                             "-pix_fmt","rgb48le","pipe:1"])
        assert len(filtered_frames)==15*size
        timed_worst=0
        wanted=[]
        for at in range(15):
            signal=[value/65535 for value in struct.unpack_from("<3H",plain_frames,at*size)]
            if at<3:
                assert signal==[0,0,0]
                expected=[0,0,0]
            else:
                local=at-3
                source_at=math.floor((2+local*1.25)*.8)
                assert max(abs(a-b/255) for a,b in zip(signal,colors[source_at]))<1/255, (at,source_at,signal)
                factor=min(1,local/8,(12-local)/8)
                expected=[value*factor for value in sequential(signal,[("brightness",1.08),("contrast",1.3)])]
            wanted.append(expected)
            frame=filtered_frames[at*size:(at+1)*size]
            assert len(set(frame[offset:offset+6] for offset in range(0,len(frame),6)))==1
            timed_worst=max(timed_worst,max(abs(a/65535-b) for a,b in zip(struct.unpack_from("<3H",frame),expected)))
        rewind=[]
        for index,at in enumerate((3,7,11,14,3)):
            timed["program"]["frame"]=at
            timed_project.write_text(json.dumps(timed),encoding="utf-8")
            shown=root/f"retimed-{index}.png"
            run([binary,"preview",shown,timed_project],env)
            with Image.open(shown) as image:
                actual=[value/255 for value in image.convert("RGB").getpixel((320,180))]
            assert max(abs(a-b) for a,b in zip(actual,wanted[at]))<=1.1/255,(at,actual,wanted[at])
            rewind.append(shown.read_bytes())
        assert rewind[0]==rewind[-1],"ordered stack rewind changed the same resolved source picture"
        assert timed_worst<=4/65535,timed_worst
        entries.append(dict(case="retimed_stack",passed=True,frames=15,previews=5,master_error=timed_worst,
                            source_fps=24000/1001,sequence_fps=30000/1001,source_in=2,start=3,speed=1.25,fade_in=8,fade_out=8))
        print(f"Ordered stack:15 native16-bit frames and5 previews preserve fractional source mapping, placement, trim, speed, fades once and exact rewind; maximum formula error {timed_worst:.8f}",flush=True)
    results = {entry["case"]: entry for entry in entries}
    order_delta = max(abs(a-b) for a, b in zip(results["brightness_then_contrast"]["master_rgb"],
                                             results["contrast_then_brightness"]["master_rgb"]))
    duplicate_delta = max(abs(a-b) for a, b in zip(results["brightness_twice"]["master_rgb"],
                                                 results["brightness_twice_reversed"]["master_rgb"]))
    report = dict(schema="genesis.filter_order", source_rgb=pixel, results=entries,
                  observed_reorder_delta=order_delta, expected_reorder_delta=.024,
                  observed_duplicate_reorder_delta=duplicate_delta,
                  failures=sum(not entry["passed"] for entry in entries))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert not report["failures"], f"{report['failures']} sequential filter-stack outcomes failed; see measured report"
    assert abs(order_delta-.024) < 1/255 and duplicate_delta < .6/255, report
    print("Filter stack:11 static cases plus15 retimed frames/5 previews passed order, duplicate, clipping, spatial/grade and source/property assertions")


if __name__ == "__main__":
    main()
