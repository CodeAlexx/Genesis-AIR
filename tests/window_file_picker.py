#!/usr/bin/env python3
"""Check that desktop picker paths reach Add and Save in the X11 window."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from tempfile import TemporaryDirectory

from Xlib import X, display
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


def wait_for(check, description):
    for _ in range(100):
        if check():
            return
        time.sleep(0.1)
    raise AssertionError(description)


def click(connection, root, window, x, y):
    origin = root.translate_coords(window, 0, 0)
    xtest.fake_input(connection, X.MotionNotify, x=origin.x + x, y=origin.y + y)
    xtest.fake_input(connection, X.ButtonPress, 1)
    xtest.fake_input(connection, X.ButtonRelease, 1)
    connection.sync()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--stdlib", type=Path, required=True)
    parser.add_argument("--display", default=os.environ.get("DISPLAY"))
    args = parser.parse_args()
    assert args.display, "an X11 display is required"

    with TemporaryDirectory(prefix="genesis-picker-") as temporary:
        work = Path(temporary)
        media = work / "selected-media.mp4"
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
                   GENESIS_FAKE_PROVIDER="1",
                   XDG_CACHE_HOME=str(work / "cache"),
                   GENESIS_SCRATCH=str(work / "scratch"),
                   PICKER_CALLS=str(calls), PICKER_MEDIA=str(media),
                   PICKER_PROJECT=str(project),
                   PATH=str(work) + os.pathsep + os.environ.get("PATH", ""))

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
                assert canvas.get_geometry().width == 1600, "unexpected test window size"

                click(connection, root, canvas, 35, 43)  # Add
                wait_for(lambda: calls.exists() and "Add media" in calls.read_text(),
                         "Add did not open the picker")
                time.sleep(0.5)
                click(connection, root, canvas, 130, 43)  # Save as
                wait_for(lambda: calls.exists() and "Save project" in calls.read_text(),
                         "Save did not open the picker")
                wait_for(project.exists, "Save did not use the chosen project path")
                saved = json.loads(project.read_text())
                assert any(media.name in str(source)
                           for source in saved.get("sources", [])), \
                    "the chosen media was not imported into the saved project"
                print("X11 picker: Add imported selected media; Save wrote selected project")
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
