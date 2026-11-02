"""Rotated picture-in-picture: geometry, direction, keys, export and transition sides.

A blue 640x360 overlay is placed at x=y=0.3, w=h=0.4 over a red base on a
1280x720 sequence (rectangle 512x288 centred at 640,360). Independent geometry:
a 90 degree turn swaps which long-axis points are covered regardless of
direction, and a 30 degree turn proves positive angles turn clockwise on screen
(the base Rotate convention). The lossless master is decoded independently and
the preview must equal its nearest fit.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from filter_order import run
from media_runtime import tool

W, H = 1280, 720
RED, BLUE = (200, 40, 40), (40, 40, 200)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="earlier Genesis-AIR.exe for unrotated identity")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    report = {"cases": {}}
    with tempfile.TemporaryDirectory(prefix="genesis-pip-rotation-") as temporary:
        root = Path(temporary)
        paths = []
        for name, colour in (("base", RED), ("over", BLUE)):
            raw, media = root / f"{name}.rgb", root / f"{name}.mkv"
            raw.write_bytes(bytes(colour) * (640 * 360) * 24)
            run([ffmpeg, "-nostdin", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "640x360",
                 "-r", "30", "-i", raw, "-frames:v", "24", "-c:v", "ffv1", "-pix_fmt", "bgr0", media])
            paths.append(media)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        project = root / "pip.air"
        run([binary, "probe", paths[0], root / "ui.png", project], env)
        base = json.loads(project.read_text(encoding="utf-8"))
        base["sequences"][0].update(width=W, height=H, fps=30)
        source = base["sources"][0]
        source.update(frames=24)
        base["sources"].append(dict(source, id=90, path=str(paths[1]).replace("\\", "/"), name="over"))
        base["clips"][0].update(length=24)
        over_clip = dict(base["clips"][0], id=91, source=90, track=6)
        base["clips"].append(over_clip)
        base["next_id"] = max(base["next_id"], 200)

        def document(rotation, frame=0, keys=None, transition=False):
            doc = copy.deepcopy(base)
            clips = [91]
            if transition:
                doc["clips"][1].update(length=12)
                doc["clips"].append(dict(doc["clips"][1], id=92, start=12, source_in=12))
                doc["names"].append("crossfade")
                doc["transitions"] = [dict(id=95, owner=doc["active"], track=6, center=12, duration=6,
                                           kind=doc["names"].index("crossfade") + 1)]
                clips.append(92)
            doc["filters"], doc["filter_params"] = [], []
            for n, clip in enumerate(clips):
                fid = 100 + n
                doc["filters"].append(dict(id=fid, clip=clip, kind="size_position", order=0, enabled=True))
                doc["filter_params"] += [dict(filter=fid, name=k, value=v) for k, v in
                                         dict(x=0.3, y=0.3, w=0.4, h=0.4, rotation=rotation, opacity=1.0).items()]
            if keys:
                if "size_position.rotation" not in doc["names"]:
                    doc["names"].append("size_position.rotation")
                doc["keys"] = [dict(clip=91, owner=doc["active"], param=doc["names"].index("size_position.rotation") + 1,
                                    frame=f, value=v, interp=2) for f, v in keys]
            doc["program"]["frame"] = frame
            return doc

        def render(name, doc, frame=0, binary_path=binary):
            path = root / f"{name}.air"
            path.write_text(json.dumps(doc), encoding="utf-8")
            preview, master = root / f"{name}.png", root / f"{name}.mkv"
            run([binary_path, "preview", preview, path], env)
            run([binary_path, "export", master, path], env)
            pixels = run([ffmpeg, "-nostdin", "-v", "error", "-i", master, "-vf", f"select=eq(n\\,{frame})",
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
            assert len(pixels) == W * H * 3, name
            shown = run([ffmpeg, "-nostdin", "-v", "error", "-i", preview, "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
            fitted = bytearray(640 * 360 * 3)
            for y in range(360):
                for x in range(640):
                    s = ((y * H // 360) * W + x * W // 640) * 3
                    fitted[(y * 640 + x) * 3:(y * 640 + x) * 3 + 3] = pixels[s:s + 3]
            worst = max(abs(a - b) for a, b in zip(shown, fitted))
            assert worst <= 2, (name, "preview differs from master", worst)
            return pixels, preview

        def colour(pixels, x, y):
            at = (y * W + x) * 3
            return tuple(pixels[at:at + 3])

        def near(c, ref):
            return max(abs(a - b) for a, b in zip(c, ref)) <= 6

        def case(name, condition, **values):
            report["cases"][name] = dict(passed=bool(condition), **values)
            assert condition, (name, values)

        flat, flat_png = render("rot0", document(0))
        case("unrotated-placement", near(colour(flat, 400, 360), BLUE) and near(colour(flat, 640, 200), RED)
             and near(colour(flat, 380, 360), RED), inside=colour(flat, 400, 360))
        if args.baseline:
            old, old_png = render("rot0-baseline", document(0), binary_path=args.baseline.resolve())
            case("unrotated-matches-baseline", old == flat)
        turned, _ = render("rot90", document(90))
        case("ninety-swaps-axes", near(colour(turned, 640, 140), BLUE) and near(colour(turned, 400, 360), RED),
             top=colour(turned, 640, 140), side=colour(turned, 400, 360))
        thirty, _ = render("rot30", document(30))
        down = (round(640 + 230 * math.cos(math.radians(30))), round(360 + 230 * math.sin(math.radians(30))))
        up = (down[0], round(360 - 230 * math.sin(math.radians(30))))
        case("positive-is-clockwise", near(colour(thirty, *down), BLUE) and near(colour(thirty, *up), RED),
             down=colour(thirty, *down), up=colour(thirty, *up))
        keyed, _ = render("keyed", document(0, frame=10, keys=((0, 0.0), (10, 90.0))), frame=10)
        case("keyed-rotation", keyed == turned)
        full, _ = render("rot360", document(360))
        # A full turn may resample only pixels on the rectangle's border (float rounding of 2*pi).
        moved = [i // 3 for i in range(0, len(full), 3) if full[i:i + 3] != flat[i:i + 3]]
        off_edge = [p for p in moved if min(abs(p % W - 384), abs(p % W - 896), abs(p // W - 216), abs(p // W - 504)) > 1]
        case("full-turn-matches-unrotated", len(moved) <= 2 * (512 + 288) and not off_edge,
             border_pixels=len(moved), interior_pixels=len(off_edge))
        dissolve, _ = render("transition", document(45, frame=12, transition=True), frame=12)
        centre = colour(dissolve, 640, 360)
        corner = colour(dissolve, 390, 222)
        case("rotated-transition-side", near(centre, BLUE) and near(corner, RED), centre=centre, corner=corner)
        for name, value in (("too-large", 400.0),):
            path = root / f"{name}.air"
            path.write_text(json.dumps(document(value)), encoding="utf-8")
            done = subprocess.run([str(binary), "export", str(root / f"{name}.mkv"), str(path)], env=env,
                                  capture_output=True, text=True, timeout=90,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            case(name, done.returncode != 0 and not (root / f"{name}.mkv").exists(), exit=done.returncode)
    report["passed"] = all(c["passed"] for c in report["cases"].values())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PiP rotation: {len(report['cases'])} cases passed")


if __name__ == "__main__":
    main()
