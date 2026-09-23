#!/usr/bin/env python3
"""Exercise file selection, timeline insertion, and ruler scrubbing in X11."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from tempfile import TemporaryDirectory

from Xlib import X, display, protocol
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


def wait_for(check, description, attempts=100):
    for _ in range(attempts):
        if check():
            return
        time.sleep(0.1)
    raise AssertionError(description)


def click(connection, root, window, x, y):
    root.send_event(protocol.event.ClientMessage(
        window=window, client_type=connection.intern_atom("_NET_ACTIVE_WINDOW"),
        data=(32, [1, X.CurrentTime, 0, 0, 0])),
        event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
    connection.sync()
    time.sleep(0.1)
    origin = root.translate_coords(window, 0, 0)
    xtest.fake_input(connection, X.MotionNotify, x=origin.x + x, y=origin.y + y)
    xtest.fake_input(connection, X.ButtonPress, 1)
    xtest.fake_input(connection, X.ButtonRelease, 1)
    connection.sync()


def drag(connection, root, window, from_x, to_x, y):
    origin = root.translate_coords(window, 0, 0)
    xtest.fake_input(connection, X.MotionNotify, x=origin.x + from_x,
                     y=origin.y + y)
    xtest.fake_input(connection, X.ButtonPress, 1)
    connection.sync()
    time.sleep(0.1)
    xtest.fake_input(connection, X.MotionNotify, x=origin.x + to_x,
                     y=origin.y + y)
    connection.sync()
    time.sleep(0.1)
    xtest.fake_input(connection, X.ButtonRelease, 1)
    connection.sync()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--stdlib", type=Path, required=True)
    parser.add_argument("--display", default=os.environ.get("DISPLAY"))
    parser.add_argument("--maximized", action="store_true")
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    assert args.display, "an X11 display is required"

    with TemporaryDirectory(prefix="genesis-picker-") as temporary:
        work = Path(temporary)
        media = work / "selected-media.mp4"
        if args.worker:
            made = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "color=c=red:s=320x180:r=30", "-t", "1", "-c:v",
                "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                str(media)], capture_output=True, text=True, timeout=30)
            assert made.returncode == 0, made.stderr
        else:
            media.write_bytes(b"fake provider fixture")
        project = work / "selected-project.air"
        calls = work / "picker-calls"
        picker = work / "zenity"
        picker.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$*" >> "$PICKER_CALLS"\n'
            'case "$*" in\n'
            '  *"Add media"*) printf "%s\\n" "$PICKER_MEDIA";;\n'
            '  *"Save project"*) printf "%s\\n" "$PICKER_PROJECT";;\n'
            '  *) exit 1;;\n'
            'esac\n'
            '# The path arrives before exit; the editor must wait before closing us.\n'
            'sleep 0.2\n'
        )
        picker.chmod(0o755)
        env = dict(os.environ, DISPLAY=args.display,
                   AIR_STDLIB=str(args.stdlib.resolve()),
                   XDG_CACHE_HOME=str(work / "cache"),
                   GENESIS_SCRATCH=str(work / "scratch"),
                   PICKER_CALLS=str(calls), PICKER_MEDIA=str(media),
                   PICKER_PROJECT=str(project),
                   PATH=str(work) + os.pathsep + os.environ.get("PATH", ""))
        if args.worker:
            env.pop("GENESIS_FAKE_PROVIDER", None)
            env["GENESIS_GCOMPOSE"] = str(args.worker.resolve())
        else:
            env["GENESIS_FAKE_PROVIDER"] = "1"

        connection = display.Display(args.display)
        try:
            root = connection.screen().root
            existing = {window.id for window in windows_named(root, "Genesis AIR")}
            child = subprocess.Popen([args.binary.resolve(), "new"], env=env,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            try:
                canvas = None
                for _ in range(50):
                    candidates = [window for window in windows_named(root, "Genesis AIR")
                                  if window.id not in existing]
                    if candidates:
                        canvas = min(candidates, key=lambda window:
                                     window.get_geometry().height)
                        break
                    time.sleep(0.1)
                assert canvas is not None, "editor window did not open"
                if args.maximized:
                    state = connection.intern_atom("_NET_WM_STATE")
                    vertical = connection.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT")
                    horizontal = connection.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ")
                    root.send_event(protocol.event.ClientMessage(
                        window=canvas, client_type=state,
                        data=(32, [1, vertical, horizontal, 1, 0])),
                        event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                    connection.flush()
                    wait_for(lambda: canvas.get_geometry().width >= 3200,
                             "editor window did not maximize")
                scale = 2 if args.maximized else 1
                if args.maximized:
                    assert canvas.get_geometry().height >= 1600, "test display is not 4K sized"
                else:
                    assert canvas.get_geometry().width == 1600, "unexpected test window size"
                def painted():
                    try:
                        pixel = canvas.get_image(10, 10, 1, 1, X.ZPixmap,
                                                 0xFFFFFFFF).data
                        return bool(pixel) and pixel[0] < 128
                    except Exception:
                        return False
                wait_for(painted, "editor did not paint its window", attempts=300)

                click(connection, root, canvas, 35 * scale, 43 * scale)  # Add
                wait_for(lambda: calls.exists() and "Add media" in calls.read_text(),
                         "Add did not open the picker", attempts=300)
                time.sleep(0.5)
                click(connection, root, canvas, 100 * scale, 100 * scale)  # Select imported source
                click(connection, root, canvas, 90 * scale, 450 * scale)  # Add clip
                time.sleep(0.5)
                ruler_y = (514 if args.maximized else 519) * scale
                drag(connection, root, canvas, 212 * scale,
                     248 * scale, ruler_y)  # frame 5 to frame 20
                time.sleep(0.5)
                click(connection, root, canvas, 130 * scale, 43 * scale)  # Save as
                wait_for(lambda: calls.exists() and "Save project" in calls.read_text(),
                         "Save did not open the picker")
                wait_for(project.exists, "Save did not use the chosen project path")
                saved = json.loads(project.read_text())
                assert any(media.name in str(source)
                           for source in saved.get("sources", [])), \
                    "the chosen media was not imported into the saved project"
                assert saved.get("clips"), "Add clip left the timeline empty"
                v1 = next(track for track in saved["tracks"] if track["name"] == "V1")
                assert saved["clips"][0]["track"] == v1["id"], "clip landed outside V1"
                assert saved["clips"][0]["selected"], "added clip is not selected"
                assert saved["program"]["frame"] == 20, \
                    f"ruler drag stopped at frame {saved['program']['frame']} instead of 20"
                print("X11 editor: media imported, clip selected on V1, ruler scrubbed to frame 20")
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
