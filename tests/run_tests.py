#!/usr/bin/env python3
"""Genesis AIR test runner.

Stage 1 is headless and uses the FakeMediaProvider, so it needs no FFmpeg, OpenCL or GPU.
Stage 2 is a bounded real-media smoke test against the existing gcompose worker; it is
BLOCKED, not passed, when the worker or a fixture is missing.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent


def sdk_config():
    values = {}
    for line in (PROJECT / "air-sdk.conf").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw = line.split("=", 1)
        if raw.startswith("${") and ":-" in raw:
            raw = raw.split(":-", 1)[1].rstrip("}")
        values[name.strip()] = raw.strip()
    return values


# Expected values, stated here from the application's documented behavior rather than read
# back from it. The provider is deterministic, so every one of these is reproducible.
EXPECTED = {
    "clock_first_frame": "true",
    "clock_fractional_frame": "true",
    "clock_paused": "true",
    "clock_stops_at_end": "true",
    "reverse_rate_start": "true",
    "reverse_rate_end": "true",
    "mixed_full_source_placed": "true",
    "mixed_last_native": "true",
    "mixed_inpoint_native": "true",
    "speed_filter_native_frame": "true",
    "dissolve_wire_kind": "true",
    "keyframed_opacity_start": "true",
    "keyframed_opacity_end": "true",
    "keyframed_brightness_start": "true",
    "keyframed_brightness_end": "true",
    "keyframed_fade_start": "true",
    "keyframed_fade_middle": "true",
    "keyframe_uses_local_frame": "true",
    "keyframe_creates_filter": "true",
    "unrendered_key_refused": "true",
    "keyframe_filter_one_undo": "true",
    "provider": "fake",
    "tracks_at_start": "4",
    "clips_at_start": "0",
    "status_at_start": "New project",
    "clean_at_start": "true",
    "sources": "3",
    "import_marks_dirty": "true",
    "length_known": "true",
    "bin_added": "true",
    "clips_after_append": "3",
    "duration": "280",
    # The toolkit's source-bounds contract still applies when the app asks for too much.
    "oversize_admitted": "true",
    "oversize_clamped": "true",
    "selection_size": "1",
    "selected_is_first": "true",
    "selection_after_add": "2",
    "selection_after_only": "1",
    "split": "split",
    "clips_after_split": "4",
    "trim": "trimmed tail",
    "ripple_trim": "ripple trimmed",
    "slip": "slipped",
    "nudge": "nudged",
    "group": "grouped",
    "group_members": "2",
    "move_group": "group moved",
    "ungroup": "ungrouped",
    "transition": "transition added",
    "transition_resize": "transition resized",
    "fades": "fades set",
    "keys": "2",
    "marker": "marker added",
    "subtitle": "subtitle added",
    "zero_span_subtitle": "false",
    "filters": "3",
    "filter_toggle": "filter disabled",
    "grain_disabled": "true",
    "grain_order": "0",
    "filters_after_remove": "2",
    "pan": "-0.5",
    # Solo is a mixer-wide policy: once A2 is soloed, A1 is not audible.
    "a1_audible_when_a2_solo": "false",
    "a2_audible_when_a2_solo": "true",
    "a1_muted": "true",
    "program_frame": "40",
    "source_frame": "2",
    "transports_independent": "true",
    "project_range": "range set",
    "pool_click": "Opened wide.mov",
    "focus_is_pool": "true",
    "pool_row": "0",
    "focus_is_dock": "true",
    "ruler_scrubbed": "true",
    "space_plays": "true",
    "space_pauses": "true",
    "home_rewinds": "0",
    "edits_changed_state": "true",
    "undo_1": "true",
    "undo_1_exact": "true",
    "undo_2_exact": "true",
    "redo_1_exact": "true",
    "redo_2_exact": "true",
    "saved": "true",
    "clean_after_save": "true",
    "opened": "true",
    "reload_exact": "true",
    "filter_text_set": "true",
    "reload_filter_text": "AIR title",
    "title_text_prompt": "true",
    "title_text_value": "AIR title",
    "lut_relative_path": "true",
    "lut_missing_refused": "true",
    "lut_path_preserved": "true",
    "reload_sources": "3",
    "reload_tracks": "4",
    "reload_transitions": "1",
    "reload_markers": "1",
    "reload_subtitles": "1",
    "missing_project_refused": "true",
    "provider_used": "true",
    "provider_failures": "0",
    "render_width": "1600",
    "render_height": "980",
    "paints": "1",
    # --- the chrome ---------------------------------------------------------
    # Every control is clicked at the centre of the rectangle it was BUILT with, so these
    # prove that painting and dispatch share one geometry rather than two that agree today.
    "toolbar_built": "true",
    "toolbar_has_undo": "true",
    "menu_headings_built": "true",
    "menu_opens_on_hover": "true",
    "menu_switches_on_hover": "true",
    "menu_item_hovers": "true",
    "menu_first_click_opens": "true",
    "menu_popup_has_about": "true",
    "menu_item_reports": "true",
    "menu_closes_after_item": "true",
    "dock_scrollbar_present": "true",
    "dock_wheel_uses_pointer": "true",
    "dock_wheel_scrolls_up": "true",
    "dock_thumb_press_starts_drag": "true",
    "dock_thumb_drag_scrolls": "true",
    "dock_thumb_release_stops_drag": "true",
    "dock_track_click_pages": "true",
    "tbar_has_split": "true",
    "tbar_has_snap": "true",
    "dock_tab_after_click": "1",          # chrome.tab_filters()
    "library_added_filter": "true",
    # The inspector shows every parameter of every offered filter, present or not: 172
    # controls for this project. A drop here means a section stopped being built.
    "properties_controls": "172",
    "slider_materialised_filter": "true",
    "slider_wrote_value": "true",
    "copied": "true",
    "clipboard_filled": "true",
    "pasted": "true",
    "paste_added_clip": "true",
    "razor_all": "true",
    "razor_cut_more_than_one": "true",
    "header_has_eye": "true",
    "header_has_add_video": "true",
    "drag_moved_clip": "true",
    # A whole drag is ONE undo step: nothing is written until the pointer is released.
    "drag_is_one_undo_step": "true",
    "prompt_open": "true",
    "prompt_takes_text": "true",
    "prompt_escapes": "true",
}

APPROX = {"filter_param": 0.4, "gain": 0.6}


def run(argv, env, timeout=900):
    done = subprocess.run([str(v) for v in argv], env=env, text=True,
                          capture_output=True, timeout=timeout)
    return done


def controls(airc, stdlib):
    """Click every control the chrome builds and check what it actually did.

    Two properties are asserted, and both catch a class of bug that is invisible in a
    screenshot: no two enabled controls in a panel may overlap — an overlapped control is
    unreachable, and the click silently runs the control on top of it — and every control
    must report an outcome, so a button that is drawn but wired to nothing shows up.
    """
    env = dict(os.environ, AIR_STDLIB=str(stdlib))
    overlaps = []
    dead = []
    seen = 0
    with TemporaryDirectory(prefix="genesis-air-controls-") as temporary:
        root = Path(temporary)
        env["XDG_CACHE_HOME"] = str(root / "cache")
        for tab in ("properties", "filters", "scopes", "audio"):
            argv = [airc, "run", HERE / "controls.ai", "--mode", "release", "--", str(root)]
            if tab != "properties":
                argv.append(tab)
            done = run(argv, env)
            assert done.returncode == 0, done.stdout + done.stderr
            rows = []
            boxes = []
            for line in done.stdout.splitlines():
                if not line.strip() or line.startswith("BASE"):
                    continue
                f = line.split("\t")
                if f[0] == "RECT":
                    boxes.append((f[1], f[2], *(int(v) for v in f[3].split(","))))
                    continue
                panel, label, kind, param = f[0], f[3], f[4], f[5]
                note = f[8] if len(f) > 8 else ""
                rows.append((panel, label or f"{kind}.{param}", note))
            seen += len(rows)
            for panel in {b[0] for b in boxes}:
                items = [b for b in boxes if b[0] == panel]
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        a, b = items[i], items[j]
                        wide = min(a[4], b[4]) - max(a[2], b[2])
                        tall = min(a[5], b[5]) - max(a[3], b[3])
                        if wide > 1 and tall > 1:
                            overlaps.append(f"{tab}/{panel}: {a[1]} over {b[1]} ({wide}x{tall}px)")
            dead += [f"{tab}/{r[0]}: {r[1]}" for r in rows if not r[2].strip()]
    assert not overlaps, "controls overlap, so a click runs the wrong one:\n  " + "\n  ".join(sorted(set(overlaps)))
    assert not dead, "controls that reported no outcome:\n  " + "\n  ".join(sorted(set(dead)))
    print(f"  controls: {seen} clicks across 4 tabs, no overlaps, every control reported")


def headless(airc, stdlib):
    env = dict(os.environ, AIR_STDLIB=str(stdlib))
    with TemporaryDirectory(prefix="genesis-air-") as temporary:
        root = Path(temporary)
        env["XDG_CACHE_HOME"] = str(root / "cache")
        done = run([airc, "run", HERE / "headless.ai", "--mode", "release", "--",
                    str(root), str(root / "project.air"), str(root / "frame.png")], env)
        assert done.returncode == 0, done.stdout + done.stderr
        rows = dict(line.split("\t", 1) for line in done.stdout.splitlines())

        missing = sorted(set(EXPECTED) - set(rows))
        assert not missing, f"the fixture did not report: {missing}"
        wrong = {k: {"expected": v, "actual": rows[k]} for k, v in EXPECTED.items()
                 if rows[k] != v}
        assert not wrong, "headless expectations disagree: " + json.dumps(wrong, indent=2)
        for name, want in APPROX.items():
            assert abs(float(rows[name]) - want) < 1e-9, (name, rows[name], want)

        # The saved project is the AIR editor schema, not a Genesis-only invention.
        stored = json.loads((root / "project.air").read_text())
        assert stored["schema"] == "air.editor.project", stored["schema"]
        assert stored["revision"] == 2, stored["revision"]
        assert len(stored["filter_text_params"]) == 1
        assert stored["filter_text_params"][0]["name"] == "caption"
        assert stored["filter_text_params"][0]["value"] == "AIR title"
        assert len(stored["tracks"]) == 4 and len(stored["sources"]) == 3, stored
        # Every stored clip stays inside the media it names.
        lengths = {s["id"]: s["frames"] for s in stored["sources"]}
        for clip in stored["clips"]:
            limit = lengths.get(clip["source"], 0)
            if limit:
                assert clip["source_in"] >= 0 and clip["source_in"] + clip["length"] <= limit, clip
        print(f"  headless: {len(rows)} application facts passed (fake provider)")
        return len(rows)


def render_smoke(binary, stdlib):
    env = dict(os.environ, AIR_STDLIB=str(stdlib), GENESIS_FAKE_PROVIDER="1")
    with TemporaryDirectory(prefix="genesis-air-render-") as temporary:
        root = Path(temporary)
        env["GENESIS_SCRATCH"] = str(root / "scratch")
        png = root / "frame.png"
        project = root / "demo.air"
        done = run([binary, "demo", str(png), str(project)], env)
        assert done.returncode == 0, done.stdout + done.stderr
        assert png.exists() and png.stat().st_size > 1000, "no frame was written"
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        stored = json.loads(project.read_text())
        assert stored["schema"] == "air.editor.project"
        assert len(stored["clips"]) == 3, stored["clips"]
        assert len(stored["transitions"]) == 1
        assert len(stored["filters"]) == 2
        print("  render: the demo project painted a 1600x980 frame and saved its project")


def live_workers(worker):
    """PIDs actually executing `worker`.

    `pgrep -x` cannot match a name longer than 15 characters and `pgrep -f` matches any
    command line that merely mentions the path — including this checker's own. Resolving
    /proc/<pid>/exe is the only form that answers the real question.
    """
    target = os.path.realpath(worker)
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or entry == str(os.getpid()):
            continue
        try:
            if os.path.realpath(os.path.join("/proc", entry, "exe")) == target:
                found.append(entry)
        except OSError:
            continue
    return found


def gcompose_smoke(airc, binary, stdlib, worker, fixture):
    """Bounded real-media smoke.

    One file: probe, preview and export a short timeline through the real worker.
    """
    env = dict(os.environ, AIR_STDLIB=str(stdlib), GENESIS_GCOMPOSE=str(worker))
    env.pop("GENESIS_FAKE_PROVIDER", None)
    with TemporaryDirectory(prefix="genesis-air-gcompose-") as temporary:
        root = Path(temporary)
        env["GENESIS_SCRATCH"] = str(root / "scratch")
        png = root / "frame.png"
        project = root / "project.air"
        done = run([binary, "probe", str(fixture), str(png), str(project)], env, timeout=300)
        assert done.returncode == 0, done.stdout + done.stderr
        rows = {}
        for line in done.stdout.splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                rows[parts[0]] = parts[1]
        assert rows.get("frames") and int(rows["frames"]) > 0, done.stdout
        assert rows.get("source_frame") == "ok", done.stdout
        assert rows.get("provider_failures") == "0", done.stdout
        assert done.stdout.splitlines()[0] == "gcompose", "the real provider was not selected"
        assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        preview = root / "program.png"
        done = run([binary, "preview", str(preview), str(project)], env, timeout=300)
        assert done.returncode == 0, done.stdout + done.stderr
        assert preview.exists() and preview.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        movie = root / "program.mp4"
        done = run([binary, "export", str(movie), str(project)], env, timeout=300)
        assert done.returncode == 0, done.stdout + done.stderr
        assert movie.exists() and movie.stat().st_size > 1000
        media = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_frames,width,height",
                                "-of", "json", str(movie)], capture_output=True, text=True)
        assert media.returncode == 0, media.stderr
        streams = json.loads(media.stdout)["streams"]
        assert streams and int(streams[0]["nb_frames"]) == min(int(rows["frames"]), 24), streams
        envelope = run([airc, "run", HERE / "provider_real.ai", "--mode", "release",
                        "--", worker, fixture, root / "env-scratch"], env, timeout=300)
        assert envelope.returncode == 0, envelope.stdout + envelope.stderr
        leftover = live_workers(worker)
        assert not leftover, f"a worker outlived the run: {leftover}"
        print(f"  gcompose: {rows['frames']} real frames probed, program preview and "
              f"{streams[0]['nb_frames']}-frame MP4 and waveform written, no worker left behind")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--airc")
    parser.add_argument("--stdlib")
    parser.add_argument("--binary")
    parser.add_argument("--media", help="a small media fixture for the gcompose smoke test")
    args = parser.parse_args()

    config = sdk_config()
    stdlib = Path(args.stdlib) if args.stdlib else (PROJECT / config["AIR_SDK"] / "stdlib").resolve()
    airc = Path(args.airc) if args.airc else (
        PROJECT / config["AIR_TOOLCHAIN"] / "build-dev/bin/airc").resolve()
    binary = Path(args.binary or (PROJECT / "build/genesis-air"))

    print(f"genesis-air tests   AIR {config['AIR_SDK_COMMIT'][:12]}   stdlib {stdlib}")
    if not airc.exists():
        print(f"BLOCKED: no AIR compiler at {airc}", file=sys.stderr)
        return 1
    if not (stdlib / "editor.ai").exists():
        print(f"BLOCKED: {stdlib} has no std.editor", file=sys.stderr)
        return 1

    headless(airc, stdlib)
    controls(airc, stdlib)

    if binary.exists():
        render_smoke(binary, stdlib)
    else:
        print(f"  BLOCKED render smoke: build it first ({binary})")

    worker = Path(os.environ.get("GENESIS_GCOMPOSE", "genesis-gcompose"))
    real_blocked = False
    if not binary.exists():
        print("  BLOCKED gcompose smoke: no application binary")
        real_blocked = True
    elif not worker.exists():
        print(f"  BLOCKED gcompose smoke: no worker at {worker}")
        real_blocked = True
    elif not args.media:
        print("  BLOCKED gcompose smoke: pass --media with a small fixture")
    elif not Path(args.media).exists():
        print(f"  BLOCKED gcompose smoke: no media fixture at {args.media}")
        real_blocked = True
    else:
        gcompose_smoke(airc, binary, stdlib, worker, Path(args.media))

    print("genesis-air: tests complete")
    return 1 if args.media and real_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
