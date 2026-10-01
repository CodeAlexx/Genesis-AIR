#!/usr/bin/env python3
"""Exercise Play/Pause in the actual X11 canvas with the fake media provider."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from tempfile import TemporaryDirectory

from Xlib import X, XK, display
from Xlib.ext import xtest


def windows_named(node, name):
    found = []
    try:
        if node.get_wm_name() == name:
            found.append(node)
        for child in node.query_tree().children:
            found.extend(windows_named(child, name))
    except Exception:
        pass
    return found


def capture(connection, window):
    connection.sync()
    extent = window.get_geometry()
    return window.get_image(0, 0, extent.width, extent.height,
                            X.ZPixmap, 0xFFFFFFFF).data


def press_space(connection, window):
    window.set_input_focus(X.RevertToParent, X.CurrentTime)
    code = connection.keysym_to_keycode(XK.string_to_keysym("space"))
    xtest.fake_input(connection, X.KeyPress, code)
    xtest.fake_input(connection, X.KeyRelease, code)
    connection.sync()


def player_children(parent_pid):
    children = Path(f"/proc/{parent_pid}/task/{parent_pid}/children")
    if not children.exists():
        return []
    found = []
    for item in children.read_text().split():
        name = Path(f"/proc/{item}/comm")
        if name.exists() and name.read_text().strip() in ("paplay", "aplay"):
            found.append(int(item))
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--stdlib", type=Path, required=True)
    parser.add_argument("--display", default=os.environ.get("DISPLAY"))
    parser.add_argument("--worker", type=Path,
                        help="exercise real timeline audio through gcompose")
    args = parser.parse_args()
    assert args.display, "an X11 display is required"
    binary = args.binary.resolve()
    stdlib = args.stdlib.resolve()
    connection = display.Display(args.display)
    try:
        root = connection.screen().root
        existing = {window.id for window in windows_named(root, "Genesis AIR")}
        with TemporaryDirectory(prefix="genesis-air-window-") as temporary:
            work = Path(temporary)
            env = dict(os.environ, DISPLAY=args.display, AIR_STDLIB=str(stdlib),
                       GENESIS_SCRATCH=str(work / "scratch"),
                       XDG_CACHE_HOME=str(work / "cache"))
            project = work / "demo.air"
            if args.worker:
                env.pop("GENESIS_FAKE_PROVIDER", None)
                env["GENESIS_GCOMPOSE"] = str(args.worker.resolve())
                source = work / "source.mp4"
                source_build = subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=red:s=320x180:r=30", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000", "-t", "4", "-c:v",
                    "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(source)], capture_output=True, text=True,
                    timeout=30)
                assert source_build.returncode == 0, source_build.stderr
                command = [binary, "probe", source, work / "probe.png", project]
            else:
                env["GENESIS_FAKE_PROVIDER"] = "1"
                command = [binary, "demo", work / "demo.png", project]
            made = subprocess.run(command,
                                  env=env, capture_output=True, text=True, timeout=30)
            assert made.returncode == 0, made.stdout + made.stderr
            if args.worker:
                document = json.loads(project.read_text())
                document["clips"][0]["length"] = 120
                project.write_text(json.dumps(document))
            child = subprocess.Popen([binary, "open", project], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                canvas = None
                for _ in range(50):
                    candidates = [window for window in windows_named(root, "Genesis AIR")
                                  if window.id not in existing]
                    if candidates:
                        # Mutter names both its decoration frame and the app canvas.
                        canvas = min(candidates, key=lambda window:
                                     window.get_geometry().width * window.get_geometry().height)
                        break
                    time.sleep(0.1)
                assert canvas is not None, "Genesis AIR window did not open"
                time.sleep(0.4)
                press_space(connection, canvas)
                if args.worker:
                    audio_children = []
                    for _ in range(30):
                        audio_children = player_children(child.pid)
                        if audio_children:
                            break
                        time.sleep(0.1)
                    assert audio_children, "Play did not start a timeline audio player"
                    press_space(connection, canvas)
                    for _ in range(30):
                        if not player_children(child.pid):
                            break
                        time.sleep(0.1)
                    assert not player_children(child.pid), "Pause left the audio player running"
                    print("X11 audio: Play started an audio player; Pause stopped it")
                    return
                time.sleep(0.6)
                moving_a = capture(connection, canvas)
                time.sleep(0.6)
                moving_b = capture(connection, canvas)
                press_space(connection, canvas)
                time.sleep(0.4)
                paused_a = capture(connection, canvas)
                time.sleep(0.6)
                paused_b = capture(connection, canvas)
                moving_bytes = sum(a != b for a, b in zip(moving_a, moving_b))
                paused_bytes = sum(a != b for a, b in zip(paused_a, paused_b))
                assert moving_bytes > 1000, f"Play did not change the canvas ({moving_bytes} bytes)"
                assert paused_bytes < 100, f"Pause did not hold the canvas ({paused_bytes} bytes)"
                print(f"X11 playback: {moving_bytes} changed bytes while playing, "
                      f"{paused_bytes} after pause")
            finally:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
