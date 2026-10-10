"""Compare ordinary monitor geometry and spatial effects with native 16-bit masters.

The effect checks measure physical image features, rather than relaxing a whole-
image error bound when a smaller working canvas changes Blur or Sharpen's radius.
This gate intentionally also detects incorrect spatial semantics in older builds.
"""

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from media_runtime import tool
from PIL import Image

MONITOR = (480, 270)
SHAPES = {"landscape": (3840, 2160), "portrait": (2160, 3840)}


def run(argv, env=None, timeout=180):
    completed = subprocess.run([str(item) for item in argv], env=env, capture_output=True,
                               timeout=timeout,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert completed.returncode == 0, (argv, completed.stdout[-3000:], completed.stderr[-3000:])
    return completed.stdout


def fitted_shape(width, height):
    scale = min(MONITOR[0]/width, MONITOR[1]/height)
    fw, fh = round(width*scale), round(height*scale)
    return fw, fh, (MONITOR[0]-fw)//2, (MONITOR[1]-fh)//2


def fit_master(ffmpeg, movie, width, height):
    fw, fh, left, top = fitted_shape(width, height)
    raw = run([ffmpeg, "-nostdin", "-v", "error", "-i", movie, "-frames:v", "1",
               "-vf", f"scale={fw}:{fh}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    assert len(raw) == fw*fh*3
    canvas = Image.new("RGB", MONITOR)
    canvas.paste(Image.frombytes("RGB", (fw, fh), raw), (left, top))
    return canvas


def profile_picture(binary, project, scratch, report, env):
    # This is the production preview task at its ordinary 480x270 monitor size.
    # One sample plus three warmups leaves a committed frame in its diagnostic
    # mailbox. A one-frame clip stays at frame zero through every request.
    current = dict(env, GENESIS_SCRATCH=str(scratch))
    run([binary, "profile-preview", report, project, "1600", "980", "1", "--file-pixels"], current)
    mailbox = scratch / "profile"
    generation = int((mailbox / "ready.id").read_text().strip())
    assert generation >= 4
    slot = generation % 2
    assert int((mailbox / f"frame{slot}.id").read_text().strip()) == generation
    assert tuple(map(int, (mailbox / f"size{slot}.rgba").read_text().split())) == MONITOR
    raw = (mailbox / f"program{slot}.rgba").read_bytes()
    assert len(raw) == MONITOR[0]*MONITOR[1]*4 and set(raw[3::4]) == {255}
    return Image.frombytes("RGBA", MONITOR, raw).convert("RGB")


def bounds(image, predicate):
    points = [(x, y) for y in range(image.height) for x in range(image.width)
              if predicate(image.getpixel((x, y)))]
    assert points, "expected visible feature is absent"
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs)+1, max(ys)+1


def profile_row(image, width, height, fraction):
    fw, fh, left, top = fitted_shape(width, height)
    y = top + round(fh*fraction)
    return [image.getpixel((left+x, y))[0] for x in range(fw)]


def edge_spread(values):
    # Linear crossings retain subpixel widths rather than hiding radius changes
    # through integer threshold rounding. The left/right plateaus are known.
    crossings = []
    for threshold in (56, 184):  # 10% and 90% of the independent 40..200 edge.
        found = None
        for index in range(len(values)-1):
            before, after = values[index:index+2]
            if before <= threshold < after:
                found = index + (threshold-before)/(after-before)
                break
        assert found is not None, (threshold, min(values), max(values))
        crossings.append(found)
    return crossings[1]-crossings[0]


def sine_amplitude(values, native_width):
    # Fit sine, cosine and offset, so permissible sampling phase changes cannot
    # conceal Sharpen using neighbours at the wrong physical pixel distance.
    # The fitted display period is >=6.75 pixels in both fixture orientations.
    count = len(values)
    omega = 2*math.pi*native_width/(96*count)
    first, last = math.ceil(count*.2), math.floor(count*.8)
    matrix = [[0.0]*4 for _ in range(3)]
    for x in range(first, last):
        row = (1.0, math.sin(omega*x), math.cos(omega*x))
        for i in range(3):
            for j in range(3):
                matrix[i][j] += row[i]*row[j]
            matrix[i][3] += row[i]*values[x]
    # Solve the three fitted coefficients without assuming an integer number of
    # wave periods inside the sampled region (especially important in portrait).
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(matrix[index][column]))
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        assert abs(divisor) > 1e-9
        matrix[column] = [item/divisor for item in matrix[column]]
        for index in range(3):
            if index != column:
                factor = matrix[index][column]
                matrix[index] = [a-factor*b for a, b in zip(matrix[index], matrix[column])]
    return math.hypot(matrix[1][3], matrix[2][3])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--shape", choices=SHAPES)
    parser.add_argument("--case", choices=("plain", "title", "blur", "sharpen"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    binary, worker = args.binary.resolve(), args.worker.resolve()
    inputs = {name: dict(path=str(value), sha256=hashlib.sha256(value.read_bytes()).hexdigest())
              for name, value in (("binary", binary), ("worker", worker))}
    ffmpeg, ffprobe = tool(worker, "ffmpeg"), tool(worker, "ffprobe")
    results, failures = [], []
    with tempfile.TemporaryDirectory(prefix="genesis-large-preview-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, GENESIS_GCOMPOSE=str(worker))
        env.pop("GENESIS_FAKE_PROVIDER", None)
        for shape, (width, height) in SHAPES.items():
            if args.shape and args.shape != shape:
                continue
            side = round(min(width, height)*.12)
            fixture = (f"nullsrc=s={width}x{height}:r=30,format=gbrp,"
                       "geq=r='if(between(Y,H*.6,H*.8),if(lt(X,W*.5),40,200),90+30*sin(2*PI*X/96))':"
                       "g='80+40*Y/H':b='100+30*X/W',"
                       f"drawbox=x={round(width*.12)}:y={round(height*.4)}:w={side}:h={side}:color=0x14d21e:t=fill")
            source = root / f"{shape}.mkv"
            run([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i", fixture,
                 "-frames:v", "1", "-c:v", "ffv1", "-pix_fmt", "bgr0", source])
            project = root / f"{shape}.air"
            run([binary, "probe", source, root / f"{shape}-ui.png", project], dict(env, GENESIS_SCRATCH=str(root / "probe")))
            document = json.loads(project.read_text(encoding="utf-8"))
            document["sequences"][0].update(width=width, height=height, fps=30)
            document["clips"][0].update(length=1)
            clip = document["clips"][0]["id"]
            sharpen_pair = None
            # Spatial metrics use each path's plain amplitude/geometry to remove
            # resampling phase. Always execute plain as the measured control.
            cases = ["plain"] + ([args.case] if args.case and args.case != "plain" else [] if args.case else ["title", "blur", "sharpen"])
            if "sharpen" in cases:
                cases.insert(cases.index("sharpen"), "sharpen_control")
            for case in cases:
                current = copy.deepcopy(document)
                current.update(filters=[], filter_params=[], filter_text_params=[], keys=[])
                if case != "plain":
                    kind = "text" if case == "title" else "sharpen" if case == "sharpen_control" else case
                    current["filters"] = [dict(id=80, clip=clip, kind=kind, order=0, enabled=True)]
                    params = {"size": 140.0, "x": .25, "y": -.35} if case == "title" else {"radius": 12.0} if case == "blur" else {"amount": 0.0 if case == "sharpen_control" else 2.0}
                    current["filter_params"] = [dict(filter=80, name=name, value=value) for name, value in params.items()]
                    if case == "title":
                        current["filter_text_params"] = [dict(filter=80, name="content", value="AIR")]
                    current["next_id"] = 81
                project.write_text(json.dumps(current), encoding="utf-8")
                scratch = root / f"{shape}-{case}"
                try:
                    shown = profile_picture(binary, project, scratch, root / f"{shape}-{case}-profile.json", env)
                except Exception as problem:
                    diagnostics = {}
                    if scratch.exists():
                        for filename in scratch.rglob("*"):
                            if filename.is_file() and filename.suffix in (".txt", ".id", ".json", ".air", ".log") and filename.stat().st_size <= 65536:
                                diagnostics[str(filename.relative_to(scratch))] = filename.read_text(encoding="utf-8", errors="replace")
                    failure = dict(shape=shape, case=case, execution_failure=True, error=str(problem),
                                   project=current, scratch_diagnostics=diagnostics)
                    # Preserve coded worker/transport errors and logs before the
                    # automatically cleaned fixture directory exits on failure.
                    if args.report:
                        args.report.parent.mkdir(parents=True, exist_ok=True)
                        args.report.write_text(json.dumps(dict(schema="genesis.large_preview", monitor=MONITOR,
                          inputs=inputs, results=results, failures=len(failures)+1, execution_error=failure), indent=2), encoding="utf-8")
                    print(json.dumps(failure), flush=True)
                    raise
                master = root / f"{shape}-{case}-master.mkv"
                run([binary, "export", master, project], dict(env, GENESIS_SCRATCH=str(scratch / "export")))
                info = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-of", "json", master]))
                video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
                assert (video["width"], video["height"], video["codec_name"], video["pix_fmt"]) == (width, height, "ffv1", "gbrp16le"), video
                expected = fit_master(ffmpeg, master, width, height)
                delta = [abs(a-b) for a, b in zip(shown.tobytes(), expected.tobytes())]
                entry = dict(shape=shape, case=case, width=width, height=height, monitor=MONITOR,
                             maximum=max(delta), mean=sum(delta)/len(delta))
                try:
                    fw, fh, left, top = fitted_shape(width, height)
                    if left:
                        assert max(shown.crop((0, 0, left, MONITOR[1])).tobytes()) == 0, "left aspect bars contain picture data"
                        assert max(shown.crop((left+fw, 0, MONITOR[0], MONITOR[1])).tobytes()) == 0, "right aspect bars contain picture data"
                    if case == "plain":
                        green = lambda pixel: pixel[1] > 180 and pixel[0] < 60 and pixel[2] < 60
                        actual_box, expected_box = bounds(shown, green), bounds(expected, green)
                        entry.update(actual_square=actual_box, expected_square=expected_box)
                        assert max(abs(a-b) for a, b in zip(actual_box, expected_box)) <= 1, entry
                        assert abs((actual_box[2]-actual_box[0])-(actual_box[3]-actual_box[1])) <= 1, entry
                        assert entry["mean"] < 2.5, entry
                    elif case == "title":
                        white = lambda pixel: min(pixel) > 220
                        actual_box, expected_box = bounds(shown, white), bounds(expected, white)
                        entry.update(actual_title=actual_box, expected_title=expected_box)
                        assert max(abs(a-b) for a, b in zip(actual_box, expected_box)) <= 2, entry
                    elif case == "blur":
                        actual_width = edge_spread(profile_row(shown, width, height, .7))
                        expected_width = edge_spread(profile_row(expected, width, height, .7))
                        entry.update(actual_edge_width=actual_width, expected_edge_width=expected_width)
                        assert expected_width > 1.5 and abs(actual_width-expected_width) <= 1.2, entry
                    elif case == "sharpen_control":
                        # An enabled zero-amount spatial filter exercises the
                        # same working-canvas policy as the active Sharpen. A
                        # lower-canvas plain picture is a different resampling
                        # control and would corrupt the physical gain ratio.
                        sharpen_pair = shown, expected
                        entry.update(actual_amplitude=sine_amplitude(profile_row(shown,width,height,.2),width),
                                     expected_amplitude=sine_amplitude(profile_row(expected,width,height,.2),width))
                        assert entry["actual_amplitude"] > 20 and entry["expected_amplitude"] > 20, entry
                    else:
                        actual_gain = sine_amplitude(profile_row(shown,width,height,.2),width)/sine_amplitude(profile_row(sharpen_pair[0],width,height,.2),width)
                        expected_gain = sine_amplitude(profile_row(expected,width,height,.2),width)/sine_amplitude(profile_row(sharpen_pair[1],width,height,.2),width)
                        entry.update(actual_sharpen_gain=actual_gain, expected_sharpen_gain=expected_gain)
                        assert abs(expected_gain-(1+8*math.sin(math.pi/96)**2)) < .025, entry
                        assert abs(actual_gain-expected_gain) <= .025, entry
                    entry["passed"] = True
                except AssertionError as problem:
                    entry.update(passed=False, error=str(problem))
                    failures.append(entry)
                results.append(entry)
                print(json.dumps(entry), flush=True)
    report = dict(schema="genesis.large_preview", monitor=MONITOR, inputs=inputs, results=results, failures=len(failures))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert not failures, f"{len(failures)} native-master geometry/spatial assertions failed; see measured report"
    print(f"Large preview: {len(results)} native 16-bit master geometry, title and physical-radius comparisons passed")


if __name__ == "__main__":
    main()
