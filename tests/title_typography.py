"""Title typography: family, bold/italic, colour, outline, shadow, box and alignment.

Every case renders a real 1280x720 title through `preview` and `export`; the
lossless master is decoded independently with the shared MM-AIR ffmpeg and
measured. The preview must equal the nearest-fitted master. Default styling is
compared against a separately rendered reference (optional --baseline binary)
so existing titles stay byte-identical.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from filter_order import run
from media_runtime import tool

W, H = 1280, 720
BG = (80, 110, 140)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="earlier Genesis-AIR.exe for default-title identity")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg = tool(worker, "ffmpeg")
    report = {"cases": {}}
    with tempfile.TemporaryDirectory(prefix="genesis-title-typography-") as temporary:
        root = Path(temporary)
        raw, source = root / "source.rgb", root / "source.mkv"
        raw.write_bytes(bytes(BG) * (W * H) * 11)
        run([ffmpeg, "-nostdin", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", "30", "-i", raw, "-frames:v", "11", "-c:v", "ffv1", "-pix_fmt", "bgr0", source])
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        project = root / "title.air"
        run([binary, "probe", source, root / "ui.png", project], env)
        base = json.loads(project.read_text(encoding="utf-8"))
        base["sequences"][0].update(width=W, height=H, fps=30)
        base["clips"][0].update(length=11)
        clip = base["clips"][0]["id"]

        def document(params, frame=0, content="AIR Title 2026", keys=()):
            doc = copy.deepcopy(base)
            doc.update(filters=[dict(id=80, clip=clip, kind="text", order=0, enabled=True)],
                       filter_params=[dict(filter=80, name=n, value=v) for n, v in
                                      dict(dict(size=72, x=0, y=0), **params).items()],
                       filter_text_params=[dict(filter=80, name="content", value=content)], keys=[])
            for name, points in keys:
                if name not in doc["names"]:
                    doc["names"].append(name)
                doc["keys"] += [dict(clip=clip, owner=doc["clips"][0]["owner"], param=doc["names"].index(name) + 1,
                                     frame=f, value=v, interp=2) for f, v in points]
            doc["program"]["frame"] = frame
            return doc

        def decode(path, frame=0):
            return run([ffmpeg, "-nostdin", "-v", "error", "-i", path, "-vf", f"select=eq(n\\,{frame})",
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])

        def render(name, params, frame=0, binary_path=binary, **extra):
            doc = document(params, frame, **extra)
            path = root / f"{name}.air"
            path.write_text(json.dumps(doc), encoding="utf-8")
            preview, master = root / f"{name}.png", root / f"{name}.mkv"
            run([binary_path, "preview", preview, path], env)
            run([binary_path, "export", master, path], env)
            pixels = decode(master, frame)
            assert len(pixels) == W * H * 3, name
            shown = run([ffmpeg, "-nostdin", "-v", "error", "-i", preview, "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
            assert len(shown) == 640 * 360 * 3, name
            fitted = bytearray(640 * 360 * 3)
            for y in range(360):
                for x in range(640):
                    start = ((y * H // 360) * W + x * W // 640) * 3
                    fitted[(y * 640 + x) * 3:(y * 640 + x) * 3 + 3] = pixels[start:start + 3]
            worst = max(abs(a - b) for a, b in zip(shown, fitted))
            assert worst <= 2, (name, "preview differs from master", worst)
            return pixels, preview

        def stats(pixels):
            white = dark = red = magenta = 0
            xs = []
            for i in range(0, len(pixels), 3):
                r, g, b = pixels[i], pixels[i + 1], pixels[i + 2]
                if r > 225 and g > 225 and b > 225: white += 1
                if r < 40 and g < 40 and b < 40: dark += 1
                if r > 200 and g < 70 and b < 70: red += 1
                if r > 200 and g < 70 and b > 200: magenta += 1
                if abs(r - BG[0]) + abs(g - BG[1]) + abs(b - BG[2]) > 60:
                    xs.append((i // 3) % W)
            return dict(white=white, dark=dark, red=red, magenta=magenta,
                        left=min(xs) if xs else None, right=max(xs) if xs else None)

        def case(name, condition, **values):
            report["cases"][name] = dict(passed=bool(condition), **values)
            assert condition, (name, values)

        default, default_png = render("default", {})
        d = stats(default)
        case("default-visible", d["white"] > 2000 and d["dark"] > 300, **d)
        explicit, _ = render("explicit-defaults", dict(font=0, bold=0, italic=0, align=0, color_r=1, color_g=1,
                                                      color_b=1, outline=0, shadow=1, box=0))
        case("explicit-defaults-identical", explicit == default)
        if args.baseline:
            old, old_png = render("baseline", {}, binary_path=args.baseline.resolve())
            case("default-matches-baseline", old == default and old_png.read_bytes() == default_png.read_bytes())

        red = stats(render("red", dict(color_r=1, color_g=0, color_b=0))[0])
        case("colour", red["red"] > 0.8 * d["white"] and red["white"] < 0.05 * d["white"], red=red["red"], white=red["white"])
        plain = stats(render("no-shadow", dict(shadow=0))[0])
        case("shadow-off", plain["dark"] < 0.1 * d["dark"], dark=plain["dark"], default_dark=d["dark"])
        outline = stats(render("outline", dict(shadow=0, outline=4))[0])
        case("outline", outline["dark"] > 3 * d["dark"] and outline["white"] > 0.8 * d["white"],
             dark=outline["dark"], white=outline["white"])

        boxed, _ = render("box", dict(box=0.6))
        b = stats(boxed)
        mid = H // 2 - 20
        x = d["left"] - 8
        pixel = boxed[(mid * W + x) * 3:(mid * W + x) * 3 + 3]
        expected = [round(c * 0.4) for c in BG]
        case("box", all(abs(p - e) <= 3 for p, e in zip(pixel, expected)) and b["left"] < d["left"] - 10,
             pixel=list(pixel), expected=expected)

        width = d["right"] - d["left"]
        case("align-center", abs((d["left"] + d["right"]) / 2 - W / 2) <= 6, left=d["left"], right=d["right"])
        left = stats(render("align-left", dict(align=1, shadow=0))[0])
        case("align-left", abs(left["left"] - W / 2) <= 8 and abs((left["right"] - left["left"]) - width) <= 6, **left)
        right = stats(render("align-right", dict(align=2, shadow=0))[0])
        case("align-right", abs(right["right"] - W / 2) <= 8, **right)

        regular = stats(render("regular", dict(shadow=0))[0])
        bold = stats(render("bold", dict(shadow=0, bold=1))[0])
        case("bold", bold["white"] > 1.15 * regular["white"], bold=bold["white"], regular=regular["white"])
        italic_pixels = render("italic", dict(shadow=0, italic=1))[0]
        regular_pixels = render("regular-again", dict(shadow=0))[0]
        case("italic", italic_pixels != regular_pixels)
        widths = {}
        for family in range(7):
            s = stats(render(f"family-{family}", dict(shadow=0, font=family))[0])
            widths[family] = s["right"] - s["left"]
        case("families-distinct", len(set(widths.values())) >= 6, widths=widths)

        keys = (("text.color_g", ((0, 1.0), (10, 0.0))),)
        first = stats(render("keyed-0", dict(shadow=0), frame=0, keys=keys)[0])
        last = stats(render("keyed-10", dict(shadow=0), frame=10, keys=keys)[0])
        case("keyed-colour", first["white"] > 0.8 * regular["white"] and last["magenta"] > 0.8 * regular["white"],
             first_white=first["white"], last_magenta=last["magenta"])

        for name, params, message in (("bad-font", dict(font=7), "text font is out of range"),
                                      ("bad-bold", dict(bold=0.5), "text bold must be 0 or 1"),
                                      ("bad-colour", dict(color_r=1.5), "text colour channels must be between 0 and 1"),
                                      ("bad-outline", dict(outline=20), "text outline is out of range")):
            path = root / f"{name}.air"
            path.write_text(json.dumps(document(params)), encoding="utf-8")
            done = subprocess.run([str(binary), "export", str(root / f"{name}.mkv"), str(path)], env=env,
                                  capture_output=True, text=True, timeout=90,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            case(name, done.returncode != 0 and message in done.stdout + done.stderr and
                 not (root / f"{name}.mkv").exists(), exit=done.returncode)
    report["passed"] = all(c["passed"] for c in report["cases"].values())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Title typography: {len(report['cases'])} cases passed")


if __name__ == "__main__":
    main()
