#!/usr/bin/env python3
"""Genesis AIR test runner.

Stage 1 is headless and uses the FakeMediaProvider, so it needs no FFmpeg, OpenCL or GPU.
Stage 2 is a bounded real-media smoke test against the existing gcompose worker; it is
BLOCKED, not passed, when the worker or a fixture is missing.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import shlex
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
    "title_plan_stages": "true",
    "title_unicode_planned": "true",
    "title_missing_glyph_refused": "true",
    "title_grade_once": "true",
    "outgoing_title_at_cut": "true",
    "incoming_title_at_cut": "true",
    "incoming_opacity_prepared": "true",
    "incoming_opacity_wire_refused": "true",
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
        contexts = [(clip, clip["audio_context"]) for clip in stored["clips"]
                    if "audio_context" in clip]
        assert stored["revision"] == (3 if contexts else 2), stored["revision"]
        for clip, context in contexts:
            sample = lambda frame: math.floor(frame * 48000 / context["fps"] + 0.5)
            assert 0 <= context["offset"] <= context["length"] - clip["length"]
            assert context["crop_start"] == sample(context["origin"] + context["offset"]) - sample(context["origin"])
            assert context["output_frames"] == sample(context["origin"] + context["length"]) - sample(context["origin"])
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

    with TemporaryDirectory(prefix="genesis-channel-read-first-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "channel_read_first.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "channel-read-first-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  channel terminal delivery: {report['checks']} shared transport checks")
    for source, report_name, label in (
        ("standalone_endpoint_controller_lifecycle.ai", "controller-tests.json", "standalone endpoint controller"),
        ("standalone_endpoint_preview.ai", "preview-endpoint-tests.json", "standalone endpoint preview"),
    ):
        with TemporaryDirectory(prefix="genesis-standalone-endpoint-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
            done = run([airc, "run", HERE / source, "--mode", "release", "--", temporary], env)
            assert done.returncode == 0, done.stdout + done.stderr
            report = json.loads((Path(temporary) / report_name).read_text())["payload"]
            assert report["status"] == "pass", report
            print(f"  {label}: {report['checks']} shared lifecycle checks")
    # Compile the remaining native clients without implying actor/device execution.
    with TemporaryDirectory(prefix="genesis-endpoint-clients-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        for name in ("media", "actor_lifecycle", "cancel", "timing"):
            done = run([airc, "build", HERE / f"standalone_endpoint_{name}.ai",
                        "--mode", "release", "-o", Path(temporary) / name], env)
            assert done.returncode == 0, done.stdout + done.stderr
        print("  standalone endpoint clients: media/actor/cancel/timing compiled; worker execution gates below require --worker")
    with TemporaryDirectory(prefix="genesis-audio-context-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "audio_context.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "audio-context-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  audio context: {report['checks']} shared model/codec checks")
    with TemporaryDirectory(prefix="genesis-audio-tail-context-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "audio_tail_context.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "audio-tail-context-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  audio tail context: {report['checks']} shared model/codec checks")
    with TemporaryDirectory(prefix="genesis-keyframe-controls-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "keyframe_controls.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "keyframe-controls-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  keyframe controls: {report['checks']} shared UI/controller checks")
    with TemporaryDirectory(prefix="genesis-snap-controls-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "snap_controls.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "snap-controls-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  snap controls: {report['checks']} shared pointer/transaction checks")
    with TemporaryDirectory(prefix="genesis-transition-controls-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "transition_controls.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "transition-controls-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  transition controls: {report['checks']} shared pointer/transaction checks")
    with TemporaryDirectory(prefix="genesis-picture-memory-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "picture_memory.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "picture-memory-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  picture memory: {report['checks']} immutable input and last-use checks")
    with TemporaryDirectory(prefix="genesis-filter-transactions-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "filter_transactions.ai", "--mode", "release", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "filter-transactions-tests.json").read_text())["payload"]
        assert report["status"] == "pass", report
        print(f"  filter transactions: {report['checks']} actual command/history checks")
    with TemporaryDirectory(prefix="genesis-waveform-visual-") as temporary:
        env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
        done = run([airc, "run", HERE / "waveform_visual.ai", "--mode", "release",
                    "--provider", "hash.sha256=portable", "--", temporary], env)
        assert done.returncode == 0, done.stdout + done.stderr
        report = json.loads((Path(temporary) / "waveform-visual-tests.json").read_text(encoding="utf-8"))["payload"]
        assert report["status"] == "pass" and report["cases"] == dict(total=11, passed=11, failed=0, skipped=0) and report["checks"] == 100, report
        print("  visual waveforms: 11 cases / 100 identity, actual strip-task, budget and pixel checks")
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
        with TemporaryDirectory(prefix="genesis-waveform-reference-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib))
            client = Path(temporary) / "genesis-waveform-visual-media"
            done = run([airc, "build", HERE / "waveform_visual_media.ai", "--mode", "release",
                        "--provider", "hash.sha256=portable", "-o", client], env)
            assert done.returncode == 0, done.stdout + done.stderr
            report = Path(temporary) / "waveform-visual.json"
            done = run([sys.executable, HERE / "waveform_visual.py", "--client", client,
                        "--worker", worker.resolve(), "--report", report], env)
            assert done.returncode == 0, done.stdout + done.stderr
            proof = json.loads(report.read_text(encoding="utf-8"))
            assert proof["schema"] == "genesis.waveform-visual.v1" and proof["passed"] and not proof["failures"], proof
            assert len(proof["cases"]) == proof["client_cases"] == 8 and proof["client_checks"] == 64, proof
            assert proof["numeric_peak_values"] == 320 and proof["independent_pcm_values"] == 3072000, proof
            assert proof["peak_tolerance"] == 2e-6 and not proof["normalization"], proof
            assert proof["client_joined"] and proof["observed_worker_pids_joined"] and not proof["owned_caches"], proof
            assert proof["client_sha256"] == hashlib.sha256(client.read_bytes()).hexdigest(), proof
            assert proof["worker_sha256"] == hashlib.sha256(worker.read_bytes()).hexdigest(), proof
            print("  display references: 8 real cases, independent processed peaks and owned joins")
        with TemporaryDirectory(prefix="genesis-nested-edit-context-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib))
            client = Path(temporary) / "genesis-audio-nested-edit-context"
            done = run([airc, "build", HERE / "audio_nested_edit_context.ai",
                        "--mode", "release", "-o", client], env)
            assert done.returncode == 0, done.stdout + done.stderr
            done = run([sys.executable, HERE / "audio_nested_edit_context.py",
                        "--client", client, "--worker", worker.resolve(),
                        "--report", Path(temporary) / "audio-nested-edit-context.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  nested edit context: 16 PCM and waveform cases")
        with TemporaryDirectory(prefix="genesis-context-retime-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib))
            client = Path(temporary) / "genesis-audio-context-retime"
            done = run([airc, "build", HERE / "audio_context_retime.ai",
                        "--mode", "release", "-o", client], env)
            assert done.returncode == 0, done.stdout + done.stderr
            done = run([sys.executable, HERE / "audio_context_retime.py",
                        "--client", client, "--worker", worker.resolve(),
                        "--report", Path(temporary) / "audio-context-retime.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  forward audio retime: independent original-origin PCM, peaks and export")
        with TemporaryDirectory(prefix="genesis-audio-tail-history-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib))
            client = Path(temporary) / "genesis-audio-tail-history"
            done = run([airc, "build", HERE / "audio_tail_history.ai",
                        "--mode", "release", "-o", client], env)
            assert done.returncode == 0, done.stdout + done.stderr
            helper = binary.resolve().parent / "air-file-publish"
            assert helper.is_file(), "Build the shared atomic export helper before the tail master gate"
            shutil.copy2(helper, Path(temporary) / "air-file-publish")
            done = run([sys.executable, HERE / "audio_tail_history.py",
                        "--client", client, "--worker", worker.resolve(),
                        "--report", Path(temporary) / "audio-tail-history.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  audio tail history: 32 edited graphs, actual EOF, cancellation and 20 lossless masters")
            done = run([sys.executable, HERE / "audio_tail_protocol.py",
                        "--worker", worker.resolve(), "--report", Path(temporary) / "audio-tail-protocol.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  audio tail protocol: independent EOF, capacity, cache identity and malformed requests")
            done = run([sys.executable, HERE / "audio_eof_query.py",
                        "--worker", worker.resolve(), "--report", Path(temporary) / "audio-eof-query.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  audio EOF query: committed actual endpoint, generation and read-only refusal")
            done = run([sys.executable, HERE / "audio_tail_phase.py",
                        "--worker", worker.resolve(), "--report", Path(temporary) / "audio-tail-phase.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  audio native phase: original-owner samples, actual EOF, cache identity and true tail capacity")
        with TemporaryDirectory(prefix="genesis-standalone-endpoint-media-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
            client = Path(temporary) / "genesis-standalone-endpoint-media"
            done = run([airc, "build", HERE / "standalone_endpoint_media.ai",
                        "--mode", "release", "-o", client], env)
            assert done.returncode == 0, done.stdout + done.stderr
            helper_name = "air-file-publish.exe" if os.name == "nt" else "air-file-publish"
            helper = binary.resolve().parent / helper_name
            assert helper.is_file(), "Build the shared atomic publisher before the endpoint export gate"
            shutil.copy2(helper, client.parent / helper_name)
            references = Path(temporary) / "pcm"
            done = run([sys.executable, HERE / "standalone_endpoint_media.py",
                        "--client", client, "--worker", worker.resolve(), "--work", references,
                        "--report", Path(temporary) / "standalone-endpoint-media.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  standalone endpoint PCM: independent ordered DSP actual EOF, no carrier, crop and Save/Open")
            done = run([sys.executable, HERE / "standalone_endpoint_export.py",
                        "--client", client, "--worker", worker.resolve(), "--references", references,
                        "--work", Path(temporary) / "export",
                        "--report", Path(temporary) / "standalone-endpoint-export.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  standalone endpoint export: exact PCM count, marked crop and black postbody pictures")
            actor = Path(temporary) / "genesis-standalone-endpoint-actor"
            cancel = Path(temporary) / "genesis-standalone-endpoint-cancel"
            for source, target in (("standalone_endpoint_actor_lifecycle.ai", actor),
                                   ("standalone_endpoint_cancel.ai", cancel)):
                done = run([airc, "build", HERE / source, "--mode", "release", "-o", target], env)
                assert done.returncode == 0, done.stdout + done.stderr
            actor_report = Path(temporary) / "standalone-endpoint-actor.json"
            done = run([sys.executable, HERE / "standalone_endpoint_actor.py",
                        "--client", actor, "--worker", worker.resolve(), "--cancel-client", cancel,
                        "--work", Path(temporary) / "actor", "--report", actor_report], env)
            assert done.returncode == 0, done.stdout + done.stderr
            proof = json.loads(actor_report.read_text())
            assert proof["passed"] and not proof["failures"], proof
            assert (proof["requests"], proof["pcm_values"]) == (26, 1393786), proof
            assert proof["max_error_codes"] <= 1 and proof["cache_cleanup"] and proof["actor"]["actor_joined"], proof
            cold = proof["cold_cancel"]
            assert cold["executed"] and cold["passed"] and cold["actor_joined"] and cold["cache_cleanup"], cold
            assert cold["recovery_pcm_values"] == 225600 and cold["recovery_max_error_codes"] <= 1, cold
            assert 0 < cold["acknowledgement_ns"] <= 2000000000, cold
            assert proof["worker_sha256"] == hashlib.sha256(worker.resolve().read_bytes()).hexdigest(), proof
            assert proof["client_sha256"] == hashlib.sha256(actor.read_bytes()).hexdigest(), proof
            assert cold["client_sha256"] == hashlib.sha256(cancel.read_bytes()).hexdigest(), cold
            print("  standalone endpoint actor:26 requests, independent PCM/Source, joined workers and observed cold cancellation")
        with TemporaryDirectory(prefix="genesis-program-picture-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib), XDG_CACHE_HOME=str(Path(temporary) / "cache"))
            clients = {}
            for kind in ("persistent", "protocol", "control", "epoch", "profile"):
                clients[kind] = Path(temporary) / ("genesis-program-picture-" + kind)
                done = run([airc, "build", HERE / f"program_picture_{kind}.ai",
                            "--mode", "release", "-o", clients[kind]], env)
                assert done.returncode == 0, done.stdout + done.stderr
            mock = Path(temporary) / "genesis-program-picture-mock"
            cc = shlex.split(os.environ.get("CC", "cc"))
            done = run([*cc, "-std=c11", "-D_DEFAULT_SOURCE", "-O2", "-Wall", "-Wextra",
                        HERE / "program_picture_mock.c", "-o", mock,
                        *(["-lws2_32"] if os.name == "nt" else [])], env)
            assert done.returncode == 0, done.stdout + done.stderr
            helper = HERE / "program_picture_transport.py"
            report = Path(temporary) / "program-picture-transport.json"
            done = run([sys.executable, helper, "--protocol-client", clients["protocol"],
                        "--control-client", clients["control"], "--mock", mock,
                        "--persistent-client", clients["persistent"], "--epoch-client", clients["epoch"],
                        "--worker", worker.resolve(), "--report", report], env)
            assert done.returncode == 0, done.stdout + done.stderr
            proof = json.loads(report.read_text())
            assert proof["schema"] == "genesis.program-picture-transport.v2" and proof["passed"], proof
            assert (len(proof["cases"]), proof["protocol_cases"], proof["control_cases"],
                    proof["real_pictures_each"], proof["real_epoch_windows"]) == (24, 17, 5, 8193, 7), proof
            assert (proof["real_metadata_workers"], proof["real_render_epochs"]) == (1,5), proof
            expected_inputs = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in [clients["protocol"], clients["control"], mock, helper, worker.resolve(),
                                         clients["persistent"], clients["epoch"]]}
            assert proof["inputs"] == expected_inputs, proof
            for case in proof["cases"]:
                assert case["passed"] and case["exit"] == 0 and case["client_joined"] and case["all_owned_exited"], case
                assert case["owned_pids"] and not any(case.get(k) for k in ("failure", "final_observation_error", "parent_cleanup_error")), case
                kind = ("protocol" if case["name"].startswith("protocol-") else
                        "control" if case["name"].startswith("control-") else
                        "persistent" if case["name"] == "sustained" else "epoch" if case["name"] == "epochs" else None)
                assert kind, case
                engine = mock if kind in ("protocol", "control") else worker.resolve()
                assert case["client_sha256"] == expected_inputs[str(clients[kind].resolve())], case
                assert case["worker_sha256"] == expected_inputs[str(engine.resolve())], case
            sustained = [c for c in proof["cases"] if c["name"] == "sustained"]
            epochs = [c for c in proof["cases"] if c["name"] == "epochs"]
            assert len(sustained) == len(epochs) == 1, proof
            assert len(sustained[0]["observed_worker_pids"]) == len(sustained[0]["owned_pids"]) == 2, sustained
            assert len(epochs[0]["observed_worker_pids"]) == len(epochs[0]["owned_pids"]) == 6, epochs
            print("  Program picture transport:24 cases,16386 pictures,7 windows,5 picture epochs+1 metadata worker; profile compiled only")
        with TemporaryDirectory(prefix="genesis-transition-media-") as temporary:
            env = dict(os.environ, AIR_STDLIB=str(stdlib))
            client = Path(temporary) / "genesis-transition-controls-media"
            done = run([airc, "build", HERE / "transition_controls_media.ai",
                        "--mode", "release", "-o", client], env)
            assert done.returncode == 0, done.stdout + done.stderr
            done = run([sys.executable, HERE / "transition_controls_media.py",
                        "--client", client, "--binary", binary.resolve(), "--worker", worker.resolve(),
                        "--report", Path(temporary) / "transition-controls-media-tests.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  transition media: independent preview/master pixels and unchanged audio")
            done = run([sys.executable, HERE / "upper_transition_protocol.py",
                        "--worker", worker.resolve(), "--report", Path(temporary) / "upper-transition-protocol.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  upper transition protocol: alpha, independent side blends, lifecycle and malformed input refusal")
            done = run([sys.executable, HERE / "upper_transition_media.py",
                        "--binary", binary.resolve(), "--worker", worker.resolve(),
                        "--report", Path(temporary) / "upper-transition-media.json"], env)
            assert done.returncode == 0, done.stdout + done.stderr
            print("  upper transition media: complete lower-gap masters and ordered side previews")

    print("genesis-air: tests complete")
    return 1 if args.media and real_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
