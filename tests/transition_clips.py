"""Transitions combine independently graded/faded clips in preview and export."""

from media_runtime import tool as _media_tool
import argparse
from array import array
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image
from playback_timing import run, FLAGS
from preview_fit import fitted

KINDS = ("crossfade", "wipe_lr", "wipe_rl", "wipe_up", "wipe_down", "slide_lr",
         "zoom", "dissolve", "iris", "clock", "barn_door")
SIZE = (320, 180)
COLORS = ((231, 31, 47), (21, 61, 219), (30, 191, 41))


def clamp(value):
    return min(1.0, max(0.0, value))


def weight(kind, x, y, progress, outgoing):
    width, height = SIZE
    if kind == "crossfade":
        return progress
    if kind in ("wipe_lr", "wipe_rl", "wipe_up", "wipe_down"):
        horizontal = kind in ("wipe_lr", "wipe_rl")
        extent = width if horizontal else height
        coordinate = x if horizontal else y
        if kind in ("wipe_rl", "wipe_up"):
            coordinate = extent - 1 - coordinate
        return clamp((progress * extent - coordinate) / 36 + .5)
    if kind == "slide_lr":
        return int(0 <= int(x - (1-progress) * width + .5) < width)
    if kind == "zoom":
        scale = .25 + .75 * progress
        sx = int(width/2 + (x-width/2)/scale + .5)
        sy = int(height/2 + (y-height/2)/scale + .5)
        return int(0 <= sx < width and 0 <= sy < height)
    if kind == "dissolve":
        luma = sum(channel * factor for channel, factor in zip(outgoing, (.299, .587, .114)))
        return clamp((progress * 1.25 - luma) * 4)
    nx, ny = x / width - .5, y / height - .5
    if kind == "iris":
        return int(math.hypot(nx, ny) <= progress * .72)
    if kind == "clock":
        angle = (math.atan2(nx, -ny) + math.pi) / (2 * math.pi)
        # A hard angular threshold can select either neighbour at a floating-
        # point tie. Check both whole colours there, while retaining pixel-exact
        # preview/master agreement everywhere, including the threshold itself.
        return None if abs(angle-progress) < 1e-6 else int(angle <= progress)
    if kind == "barn_door":
        return int(abs(nx) <= progress * .5)
    raise AssertionError(kind)


def opacity(settings, local, length):
    value = settings.get("opacity", 1.0) * settings.get("filter_opacity", 1.0)
    if "keys" in settings:
        first, last = settings["keys"]
        value *= first + (last-first) * clamp(local/(length-1))
    fade = 1.0
    if settings.get("fade_in", 0) and local < settings["fade_in"]:
        fade = local / settings["fade_in"]
    if settings.get("fade_out", 0) and length-local <= settings["fade_out"]:
        fade = min(fade, (length-local) / settings["fade_out"])
    return clamp(value * fade)


def color(rgb, settings, local, length):
    brightness = settings.get("brightness", 1.0) - 1
    contrast = settings.get("contrast", 1.0)
    gain = opacity(settings, local, length)
    return tuple(clamp((clamp(channel/255 + brightness) - .5) * contrast + .5) * gain
                 for channel in rgb)


def configure(document, clip, settings, next_id):
    clip.update(fade_in=settings.get("fade_in", 0), fade_out=settings.get("fade_out", 0))
    names = document["names"]
    for parameter, value in settings.items():
        if parameter in ("fade_in", "fade_out"):
            continue
        if parameter in ("opacity", "keys"):
            if "opacity" not in names:
                names.append("opacity")
            pairs = [(0, value)] if parameter == "opacity" else [(0, value[0]), (clip["length"]-1, value[1])]
            # Tests use a static opacity OR a curve, so one authoritative key set suffices.
            document["keys"].extend(dict(clip=clip["id"], owner=clip["owner"], param=names.index("opacity")+1,
                                         frame=frame, value=gain, interp=0) for frame, gain in pairs)
            continue
        kind = "opacity" if parameter == "filter_opacity" else parameter
        filter_id = next_id
        next_id += 1
        order = sum(filter["clip"] == clip["id"] for filter in document["filters"])
        document["filters"].append(dict(id=filter_id, clip=clip["id"], kind=kind,
                                        order=order, enabled=True))
        if parameter == "text":
            document["filter_text_params"].append(dict(filter=filter_id, name="content", value=value))
            document["filter_params"].extend([dict(filter=filter_id, name="size", value=110.0),
                                               dict(filter=filter_id, name="x", value=-.35 if clip["start"] == 0 else .35)])
        else:
            document["filter_params"].append(dict(filter=filter_id, name="level", value=value))
    return next_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--case", type=int, help="Reproduce one numbered case")
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    ffmpeg, ffprobe = _media_tool(worker, "ffmpeg"), _media_tool(worker, "ffprobe")
    cases = [(kind, dict(opacity=.4), dict(filter_opacity=.7), 12, False) for kind in KINDS]
    cases += [("crossfade", dict(keys=(.2, .8)), dict(keys=(.8, .2)), 12, False),
              ("crossfade", dict(fade_out=6), dict(fade_in=6), 12, False),
              ("crossfade", dict(contrast=1.8), dict(brightness=.75), 12, False),
              ("crossfade", dict(opacity=.4), dict(filter_opacity=.7), 8, True),
              ("crossfade", dict(fade_out=6), dict(fade_in=6), 16, False),
              ("crossfade", dict(opacity=.4, text="OUT"), dict(filter_opacity=.7, text="IN"), 12, True)]
    comparisons = 0
    assert args.case is None or 0 <= args.case < len(cases)
    with tempfile.TemporaryDirectory(prefix="genesis-transition-clips-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker), GENESIS_SCRATCH=str(root / "scratch"))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        sources = []
        for index, rgb in enumerate(COLORS):
            raw, media = root / f"source-{index}.rgb", root / f"source-{index}.mp4"
            raw.write_bytes(bytes(rgb) * (SIZE[0] * SIZE[1] * 36))
            run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", "320x180", "-r", "30", "-i", raw, "-f", "lavfi", "-i",
                 "sine=frequency=431:sample_rate=48000", "-t", "1.2", "-c:v", "libx264rgb",
                 "-crf", "0", "-preset", "fast", "-c:a", "aac", media])
            sources.append(media)
        project = root / "transition.air"
        run([binary, "probe", sources[0], root / "ui.png", project], env)
        base = json.loads(project.read_text(encoding="utf-8"))
        base["sequences"][0].update(width=SIZE[0], height=SIZE[1], fps=30)
        first = base["clips"][0]
        for index, (kind, outgoing, incoming, incoming_start, overlay) in enumerate(cases):
            if args.case is not None and index != args.case:
                continue
            document = copy.deepcopy(base)
            document.update(filters=[], filter_params=[], filter_text_params=[], keys=[])
            document["sources"].extend([dict(base["sources"][0], id=90+n, path=str(media))
                                         for n, media in enumerate(sources[1:])])
            document["clips"] = [dict(first, length=12), dict(first, id=92, source=90, start=incoming_start, length=12)]
            center = (12 + incoming_start) // 2 if incoming_start < 12 else 12
            document["names"].append(kind)
            document["transitions"] = [dict(id=93, owner=first["owner"], track=first["track"], center=center,
                                              duration=6, kind=len(document["names"]))]
            next_id = configure(document, document["clips"][0], outgoing, 100)
            next_id = configure(document, document["clips"][1], incoming, next_id)
            if overlay:
                track = next(track for track in document["tracks"] if track["kind"] == 0 and track["id"] != first["track"])
                upper = dict(first, id=94, source=91, track=track["id"], length=incoming_start+12)
                document["clips"].append(upper)
                next_id = configure(document, upper, dict(filter_opacity=.35), next_id)
            document["next_id"] = next_id
            master = root / f"master-{index}.mkv"
            project.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            run([binary, "export", master, project], env)
            metadata = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-of", "json", master]).stdout)
            video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
            assert (video["width"], video["height"], video["pix_fmt"]) == (*SIZE, "gbrp16le"), video
            assert any(stream["codec_type"] == "audio" for stream in metadata["streams"]), "program audio lost"
            audio = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(master), "-vn",
                                    "-ac", "2", "-ar", "48000", "-f", "f32le", "pipe:1"],
                                   capture_output=True, timeout=30, creationflags=FLAGS)
            samples = array("f")
            samples.frombytes(audio.stdout)
            assert audio.returncode == 0 and len(samples) == (incoming_start+12)*3200, (len(samples), audio.stderr)
            assert max(abs(value) for value in samples) > .005, "transition export audio was silent"
            decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-i", str(master), "-an",
                                      "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1"],
                                     capture_output=True, timeout=30, creationflags=FLAGS)
            assert decoded.returncode == 0 and len(decoded.stdout) == (incoming_start+12)*SIZE[0]*SIZE[1]*4, decoded.stderr
            frame_bytes = SIZE[0]*SIZE[1]*4
            for frame in (center-2, center, center+2):
                document["program"]["frame"] = frame
                project.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
                preview = root / "preview.png"
                run([binary, "preview", preview, project], env)
                master_frame = decoded.stdout[frame*frame_bytes:(frame+1)*frame_bytes]
                with Image.open(preview) as image:
                    shown = image.convert("RGBA").tobytes()
                assert len(shown) == 640*360*4
                expected = fitted(master_frame, *SIZE, 640, 360)
                assert max(abs(a-b) for a, b in zip(shown, expected)) <= 2, (kind, index, frame, "preview/export differed")
                if "text" not in outgoing:
                    out = color(COLORS[0], outgoing, frame, 12)
                    inc = color(COLORS[1], incoming, frame-incoming_start, 12)
                    progress = (frame-(center-3))/6
                    maximum = 0
                    mismatches = []
                    for y in range(SIZE[1]):
                        for x in range(SIZE[0]):
                            amount = weight(kind, x, y, progress, out)
                            offset = (y*SIZE[0]+x)*4
                            error = 256
                            for choice in ((0.0, 1.0) if amount is None else (amount,)):
                                rgb = tuple(a*(1-choice)+b*choice for a, b in zip(out, inc))
                                if overlay:
                                    rgb = tuple(a*.65+b/255*.35 for a, b in zip(rgb, COLORS[2]))
                                error = min(error, max(abs(master_frame[offset+c] - round(rgb[c]*255)) for c in range(3)))
                            maximum = max(maximum, error)
                            if error > 3 and len(mismatches) < 5:
                                mismatches.append((x, y, amount, tuple(master_frame[offset:offset+3]), rgb))
                    assert maximum <= 3, (kind, index, frame, "independent clip/transition formula", maximum, mismatches)
                else:
                    # Incoming and outgoing glyphs must survive their separate fades.
                    assert sum(master_frame[at+1] > 100 for at in range(0, len(master_frame), 4)) > 50, "faded title pixels absent"
                comparisons += 1
            print(f"Transition clips: {kind}, case {index}, start {incoming_start}, overlay={overlay}, preview/master/formula passed", flush=True)
        assert comparisons == (51 if args.case is None else 3)
        assert not list((root / "scratch").rglob("*.incoming-opacity.rgba")), "incoming preparation left behind"
        assert not list((root / "scratch").rglob("*.base-opacity.rgba")), "outgoing preparation left behind"
    print(f"Transition clips: {comparisons} native preview/master comparisons and exact audible master sample counts passed", flush=True)


if __name__ == "__main__":
    main()
