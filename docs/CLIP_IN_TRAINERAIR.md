# Genesis Clip in TrainerAir: integration plan

Status: design only, written 2026-11-02. Nothing was changed anywhere. AIR (`C:\AIR`, HEAD
`6b631f7e`, plus its other refs read through `git show`/`ls-tree`) and TrainerAir
(`C:\TrainerAIR`, refs `main`, `ltx25-native`, `audio`, ...) are on the merge HOLD and were read
strictly read-only (`git log`, `git show`, `git ls-files`, `git ls-tree`, `git grep`, file reads).
Genesis Clip was read from `C:\Genesis-AIR-clip` (branch `genesis-clip`).

References are `path:line` or `ref:path`. Statements marked **(unverified)** were not checked in
source and must be confirmed before work starts.

---------------------------------------------------------------------------------------

## 1. What was found

### 1.1 Genesis Clip today (C:\Genesis-AIR-clip)

| File | Lines | Role |
|---|---|---|
| `src/clip_model.ai` | 282 | pure segment list, half-open `[start,end)` frame ranges, sorted, non-overlapping, JSON sidecar (`<video>.clip.json`) |
| `src/clip_export.ai` | 418 | pure argv builders + runner: one FFmpeg child per output, `-progress pipe:1`, cancel-file, half-frame lead-in seek, `atrim` audio, odd-side pad, PNG every-Nth with renumber, empty `.txt` captions (PNG only) |
| `src/clip_state.ai` | 111 | one `Clip` record (provider, ffmpeg path, worker path, transport, marks, export state) |
| `src/clip_ui.ai` | 452 | `std.draw` painting: monitor, filmstrip, waveform, segment bar, controls |
| `src/clip_main.ai` | 980 | window loop on `std.gui` + `std.widgets`; CLI: `Genesis-Clip.exe [VIDEO]`, `--paint OUT.png`, `--export OUTDIR VIDEO LIST.json [--mp4] [--png N] [--captions]` |
| `tests/clip_logic.ai`, `windows/clip.cmake` | 167 / 23 | headless logic test; second exe `Genesis-Clip.exe` linked beside `Genesis-AIR.exe` (`/SUBSYSTEM:WINDOWS`, `windows-app.manifest`) |

Genesis modules it imports (all from `src/`): `provider.ai` (1393 lines, the media seam: fake,
gcompose worker, native FFmpeg providers; probe, source_frame, thumbnail, envelope),
`ffmpeg.ai` (148), `media_runtime.ai` (25), `native_audio.ai` (44, C ABI to
`genesis-native-audio.dll`, source `windows/native_audio.cpp`), `native_dialogs.ai` (141, C ABI to
`air-native-dialogs.dll`), `layout.ai` (130), `typeface.ai` (231), `ui_text.ai` (87), and
transitively `preview_link.ai` (provider.ai imports it). `genesis-media-runtime.txt` is a 3-line
file written by the installer (line 1 = FFmpeg `bin` dir, lines 2 and 3 = `ffmpeg.exe` and
`ffprobe.exe` in MM-Air; `media_runtime.ai:9-24` falls back to a sibling exe, then to PATH).

Important facts for the plan:

- `clip_main.ai:65-74` (`make_engine`) picks the gcompose worker when `genesis-gcompose.exe`
  exists, else the **CPU-only native FFmpeg provider** ("one FFmpeg process per picture, slower,
  needs no GPU worker"). The gcompose worker is a Rust/OpenCL compositor child that Genesis keeps
  out-of-process because "NVIDIA OpenCL initialization and a UI GL/GLX stack crashed
  intermittently when combined" (`provider.ai` header). A dataset clipper needs none of
  compositing, so inside TrainerAir it must run on the native provider only.
- The export path is already correct for editing but is **not dataset-shaped**: it keeps source
  resolution and timing and pads odd sides by one black pixel (`clip_export.ai:56-66`), writes H.264
  CRF 18 with AAC, and the clip length is whatever the user marked.
- Output names come from `model.clip_name(stem, segment)` (`clip_model.ai:181`); PNG captions are
  empty `<frame>.txt` created with `write_new_text` (never overwrites).

### 1.2 TrainerAir

- Native AIR UI, `std.widgets` + `std.draw`, Win32/Direct2D on Windows. One project
  `ui/air.project.json` (`trainerair.ui`, bin targets `air-trainer` and `board-import`);
  ~8.3k lines in `ui/*.ai` plus `ui/board/` and `ui/viewer/`. README: the UI process holds no GPU
  context and links only libc/libm; all heavy work is child processes (`ui/README.md`).
- It builds through AIR's `tools/build-windows-app.ps1` (`ui/build-windows.ps1`), imports AIR code
  by relative path (`ui/main.ai:26` imports `../../AIR/toolkits/portable/dialogs.ai`), and stages
  `air-ui-host.dll` + `air-native-dialogs.dll` beside the exe.
- Tabs are strings in `view.ai` (`"Datasets"` at `view.ai:119` is a concept table; `"Tools"` at
  `view.ai:121` -> `tools_page`, `view.ai:553`). `tools_page` has one native tool, "Dataset
  statistics", and **six disabled placeholders including "Video clip and frame extraction"**
  ("Not available natively yet", `view.ai:560`). That placeholder is the natural landing spot.
- Tools and trainers run as owned child processes: `runner.command(label, argv, cwd, watch_dir,
  gpu)` (`runner.ai:63`), ordered `Run` of commands, `std.process` + `task.spawn` inside a
  `task.scope`, GPU-guard wrapping only for `gpu=true` commands (`runner.ai:178-202`). Dataset
  preparation already uses this: `dataset_inputs.ai:plan` appends a `runner.command(...,
  gpu=false)` that runs a runtime-configured program (`data.caption_program`, `data.parquet_program`).
  Programs are located through AIR Runtime keys in `runtime.json` (`settings.ai`,
  `backends.ai:rt_raw/rt`), edited on the AIR Runtime tab.
- Datasets: a concept (`std.trainers.core.settings`: `path` = "Folder of images with same-stem .txt
  captions", `text.prompt_source` sample|concept|filename, `include_subdirectories`; video-only
  fields `frames`/`length` exist for samples, `settings.ai:878-879`). The caption contract is
  `STEM.<media>` -> `STEM.txt` beside it (`std.trainers.core.data`, `captions`, `caption_batch`).
  `dataset_inputs.plan` passes plain TXT folders straight through and stages JSON/Parquet inputs
  into `<workspace>/data/<fnv1a identity>/`.
- Video training reality (**gating fact**): the LTX 2.5 native trainer's dataset index is
  image-only. `ltx25/image_dataset.ai:scan_bucketed` lists image suffixes with `.txt` sidecars;
  `ltx25/video_cache.ai` is "bounded synthetic ... Production cache remains closed"
  (`production_admitted() -> false`). Video-shaped constraints that do exist: LTX sample frames
  must satisfy `(frames-1)%8==0` and width/height `%32==0` (`ltx25/sample_config.ai:95`). H3 has
  video-tower settings (`h3.training.*`) but TrainerAir's H3 path is an image latent cache
  (`h3-cache-images`). So today a clipper's PNG-frame output feeds trainers immediately, and its
  MP4/clip output is for the video datasets the trainers are about to admit.
- AIR main side (recent, found via `git show 59aefb3b`/`09ca5782`/`399ddc0c`, not in the current
  checkout's working tree):
  - `stdlib/thumb_grid.ai` (603 lines): lazy scrolling thumbnail grid for images **and videos**
    (first frame via `std.media`/FFmpeg, work folder never beside media), worker-decoded ring,
    caption line from the sidecar. Doc says "TrainerAir's Dataset browser and Captioner use it".
  - `apps/air-caption` (`main.ai`, `prepare.ai`, README): batch Qwen3-VL captioner over a folder
    of images and videos, writes `STEM.txt`, modes skip|overwrite|generated, atomic commit,
    `.caption-backups/`, `.caption-run` journal, `--cancel-file`. TrainerAir's "Captioner screen
    (Datasets > Captioner...) runs this program".
  - `stdlib/trainers/core/caption_batch.ai`: `scan` (Media{file, rel, kind Image|Video, sidecar,
    has_caption, has_generated}), `is_video` = mp4/mov/mkv/webm/avi.
  - `toolkits/portable/file_picker.ai` + `dialogs.folder_in/open_in/save_in`: an AIR-drawn
    chooser that backs `dialogs.*` **on Linux**. Windows keeps the native dialog DLL.
  - `std.media` (probe/frame/playback; `frame` takes `position_ms`), `std.ffmpeg` (decode_to_wav,
    encode_frames, mux_av, probe_to_file), `std.video` (embedded GStreamer playback; Linux host),
    `std.audio` (WAV only, **no playback**).
  - The TrainerAir side of the captioner/grid (Captioner screen, dataset browser) is **not on the
    refs that carry the visible history** (`git grep thumb_grid|Captioner` over `main`,
    `ltx25-native`, `audio`, `anima-native`, `zimage-l2p-ui`, `hidream` found nothing). It lives on
    an unpublished/other branch or working tree **(unverified)**. Ask the owner which branch holds
    it before designing the Clip screen's layout, so Clip reuses its card and Datasets entry.

### 1.3 What Clip needs that TrainerAir does not have

| Need | In TrainerAir today | Gap |
|---|---|---|
| frame-accurate probe (frame count, fps, audio, WxH) | none (`std.media.probe` gives duration_ms only) | provider `probe` + `ffmpeg.ai` `Info` |
| frame-accurate still decode by frame number | none (`std.media.frame` by ms, one FFmpeg process per call) | provider `source_frame`; a persistent decoder would be much faster than one process per frame |
| scrub / filmstrip / waveform envelope | none | provider `thumbnail`, `envelope`, `ffmpeg.envelope` |
| FFmpeg/ffprobe location | not needed; `std.media` uses PATH | `genesis-media-runtime.txt` / `media_runtime.ai` |
| A/V playback with sample clock | `std.video` (GStreamer, Linux), sample viewer in `ui/viewer` | Clip uses `genesis-native-audio.dll` + sample clock to stay in sync (`heard_frame`) |
| frame-accurate cut + encode | none | `clip_export.ai` |
| native dialogs | `toolkits/portable/dialogs.ai` + `air-native-dialogs.dll` | none (Genesis `native_dialogs.ai` duplicates it) |
| fonts/typography | `appearance.ai` + `std.font` | Clip's `typeface.ai`/`ui_text.ai` are Genesis-specific |
| gcompose worker | not wanted | do not bring it (GPU/OpenCL, crash isolation, contends with training for the GPU) |

---------------------------------------------------------------------------------------

## 2. (a) Embed as a screen vs launch Genesis-Clip.exe

### Option A: launched tool (`Genesis-Clip.exe` as a child)

TrainerAir adds a button on Tools (replacing the disabled "Video clip and frame extraction") and
a "Clip..." action on a dataset concept row. It runs `Genesis-Clip.exe --dataset <folder> ...`
through the same `std.process` path as the other tools. Clip is a separate window and exe.

| Pros | Cons |
|---|---|
| Smallest TrainerAir diff: one Runtime key (`tools.clip_program`), one button, one manifest reader. Nothing in AIR changes, so it is compatible with the HOLD. | Two windows, two themes (mitigated: pass `--theme/--accent/--scale` from `ui.*` keys). |
| Keeps TrainerAir's invariant: "UI holds no GPU context, links only libc/libm". Clip's FFmpeg, audio DLL and decode threads stay out of the trainer UI process; a Clip crash cannot kill a running training UI (which owns the live run, Stop and resume). | A second exe to build and ship; a second instance lock/settings dir to think about (the README already warns about per-process `AIR_TRAINER_RUNTIME` for sibling windows). |
| Clip can ship and be tested independently (its `--paint`/`--export` headless modes already exist). | No shared selection: TrainerAir must learn the result by reading a manifest after exit (or polling), not by a function call. |
| Native audio DLL, FFmpeg runtime and gcompose-free provider stay in Genesis's release pipeline until they are promoted. | Cannot reuse TrainerAir's thumbnail grid/caption line for segment review (but Clip has its own filmstrip). |

### Option B: embedded TrainerAir screen

A "Clip" tab/page inside `air-trainer`, drawn on a `std.widgets` surface (the same way
`std.thumb_grid` draws on a surface widget), sharing the app's `Ui`, theme, runtime settings and
dataset concept list.

| Pros | Cons |
|---|---|
| One window; "Clip" sits next to Datasets/Captioner; destination and caption defaults come straight from the selected concept. | Pulls ~2.4k lines plus the decode seam, FFmpeg runner, audio C ABI and a 60 fps transport/clock loop into the trainer UI process. TrainerAir's main loop is event-driven around a run; playback timing and export progress polling compete with it (**unverified** headroom). |
| Same theme, zoom, fonts, file picker; no second settings directory. | Needs AIR-side modules that do not exist yet (frame-accurate decoder, audio out), so it **cannot land under the HOLD**. |
| Natural handoff to Captioner (same process, same grid). | Clip uses `std.draw` canvas painting driven by `std.gui` directly; TrainerAir uses retained widgets. The surface-widget port is real work (`clip_ui.ai` 452 lines, input routing, keyboard focus order). |
| | A bug in Clip's native audio ABI would take the training UI down mid-run. |

### Recommendation

Do both, in order, with one stable contract between them:

1. **Ship as a launched tool first (Option A).** It works under the HOLD (no AIR or TrainerAir core
   edits beyond one button) and fits how TrainerAir already treats tools (child processes,
   Runtime-keyed program paths, `dataset_inputs.plan` pattern).
2. Define the **handoff contract now** (section 4.5: `--dataset`, `--preset`, manifest) so the
   later embedded screen is just a different front end on the same engine.
3. After the HOLD lifts and the shared modules exist (section 3), build the embedded screen as a
   second front end over the same `clip_model` / `clip_export` / `std.video_clip` engine. Keep the
   exe available: it is also the crash-isolated fallback and the headless export used by tests.

---------------------------------------------------------------------------------------

## 3. (b) What moves into AIR's shared stdlib/toolkit vs stays copied

Principle: anything TrainerAir or the captioner would also need goes to AIR once (so nothing is
duplicated); Genesis-only editing concerns stay in Genesis. Under the HOLD, nothing here is
proposed as an AIR edit now; it is the ordered backlog to hand to the owner when the HOLD lifts.
Until then Clip keeps its copies and the table says how each copy disappears.

| Genesis module | Verdict | Target in AIR | Notes |
|---|---|---|---|
| `native_dialogs.ai` | **delete** | `toolkits/portable/dialogs.ai` | already duplicated; TrainerAir imports the toolkit one. Confirm both load the same DLL package name **(unverified)**; Genesis stage ships `air-native-dialogs.dll` (same file TrainerAir stages). Gains `folder_in/open_in` Look support from `399ddc0c`. |
| `media_runtime.ai` + `genesis-media-runtime.txt` | **replace** | two AIR Runtime keys `media.ffmpeg`, `media.ffprobe` (read by `std.media`/new module); Genesis keeps a 25-line shim that reads its txt file | removes the Genesis-only file format from the TrainerAir path. Default value for the owner's machine: `C:\MM-Air\ffmpeg.exe`, `C:\MM-Air\ffprobe.exe`, and the DLL dir `C:\MM-Air\share\media\ffmpeg-n9.0.2-...-win64-gpl-shared-9.0\bin` (the dir is needed on PATH for the shared build). Per `no-license-without-owner` and the no-bundle note in `clip_export.ai`, never bundle FFmpeg. |
| `ffmpeg.ai` (`Info`, `probe`, `frame`, `envelope`) | **promote and merge** | `std.media` (add `probe_video(...) -> {frames, fps, width, height, audio}`, `frame_at(frame_no)`) or a new `std.video_frames` | overlaps `std.media.probe` (no fps/frames) and `std.ffmpeg`. One owner for argv construction; frame accuracy rules (half-frame seek) live here. |
| `provider.ai` (seam subset: probe, source_frame, thumbnail, envelope, scratch, cancel/progress file paths) | **split** | the *native-FFmpeg* half becomes a **persistent decoder worker** in AIR (`std.video_frames`); the gcompose half and `fake` stay in Genesis | the part TrainerAir needs: sequential/random frame reads without a process per frame (one long-lived `ffmpeg ... -f rawvideo` child plus a small request channel, or `air-image`/`apps/media-tool` extended). The 1393-line file is mostly Genesis's compositor/program-stream/picture-queue protocol and must not move. `std.thumb_grid` already needs a worker-decoded first frame; the same module serves it. |
| `clip_export.ai` | **promote** (pure cut planning) | `std.trainers.core.video_clip` (argv builders, 8n+1 snapping, bucket sizing, sidecar writers, `renumber`) | pure and unit-tested; also useful to a future "auto-split long video" tool and to `air-caption`. Keep progress/cancel runner behind the same names. |
| `clip_model.ai` | **promote** | same module as above (or `std.trainers.core.video_segments`) | pure; no UI. Its `.clip.json` format becomes the cross-tool provenance format. |
| `native_audio.ai` + `native_audio.cpp` (`genesis-native-audio.dll`, `air_genesis_audio`) | **promote** | `toolkits/portable/audio_out.ai` (+ provider DLL beside `air-native-dialogs`) | `std.audio` has no playback; `std.video` is GStreamer/Linux. A sample-clock audio out is a general portable need (TrainerAir's Samples/Board audio Play, the audio trainers). Rename the symbol/package to host-neutral names as `native_dialogs.ai` did. |
| `layout.ai`, `typeface.ai`, `ui_text.ai` | **stay (Genesis)** or drop in the embed | embed uses `appearance.ai`/`std.font` | Genesis typography/bidi. The launched exe keeps them; the embedded screen replaces them with TrainerAir's theme. |
| `clip_ui.ai` | **stay**; port later | embedded version = surface-widget variant in TrainerAir `ui/clip/` | pure painting over `clip_state`; a thin adapter can drive both. |
| `clip_state.ai`, `clip_main.ai` | **stay (Genesis exe front end)** | | the engine does not depend on them. |
| transport (`play_ns`, `heard_frame`, `sample_clock_drives`) | **promote small** | `toolkits/portable/transport.ai` already holds frame/mark/loop state (`transport.ai:7-28`); add the audio-clock rule there | `clip_model.heard_frame`/`sample_clock_drives` are the only novel pieces. |

Do not move: gcompose worker, `preview_link.ai`, `picture_queue.ai`, program-stream code, anything
that serves the timeline editor.

---------------------------------------------------------------------------------------

## 4. (c) Dataset integration

### 4.1 Where output goes

Input to Clip from TrainerAir: the dataset concept's `path` (a folder; today "images with same-stem
.txt"). Output is written **directly into a TrainerAir dataset folder**:

```
<concept path>/                       (existing concept folder, or a new one the user names)
  <stem>_000123-000256.mp4            clip file  (or <stem>_000123.png for frame mode)
  <stem>_000123-000256.txt            caption sidecar, same stem
  .clip-manifest.json                 provenance (hidden, ignored by scanners)
```

- Same-stem `.txt` is the trainers' contract (`caption_batch`, `captions`, `image_dataset.scan`).
- Scanners skip unknown dotfiles (`.caption-backups`, `.caption-run` are the precedent); the Clip
  provenance file follows that, and carries `{source, source_sha256, start, end, fps, out_w, out_h,
  frames, preset, clip_json}`. `captions.restore`/`caption_batch.commit` stay untouched.
- Never write the source's `<video>.clip.json` into the dataset (it stays beside the source video,
  as today). If the dataset folder is also the source folder, exports go to a `clips/` subfolder
  that is a distinct concept with `include_subdirectories` off (avoids re-scanning sources).
- Name collisions: reuse `free_name` / `write_new_text` semantics: no overwrite. Re-export of the
  same segment list is idempotent via the manifest (skip when same `{source_sha256,start,end,preset}`).
- Frame (PNG) mode: Clip's every-Nth export already produces `<prefix>NNNNNN.png` + `.txt`; keep it
  as the "Image frames" preset, which is directly consumable today by every image trainer.

### 4.2 Caption sidecars

- Always create a sidecar (today only PNG mode does, empty). For clips, write it with a caption
  default, selectable: empty | trigger word | shared per-session text | copy of the previous clip.
  Mirrors `caption_batch` modes (never overwrite an existing non-empty caption).
- Do not caption inside Clip. After export, TrainerAir opens its **Captioner** (`air-caption`) on
  that folder; the captioner already handles `Kind.Video`, `skip` mode (leaves hand-written
  captions), and keeps the `.caption-run` journal. Clip only passes the folder and the "generated
  vs skip" choice.
- Trigger-word prefix: use the existing `captions` bulk prefix (idempotent) rather than a second
  implementation.

### 4.3 Bucket-friendly resolutions and frame counts

Add a **"Dataset preset"** to the export (a new `Output` shape; the current "Original" mode stays
for editing use):

| Preset field | Rule |
|---|---|
| Frame count | snap `end - start` **down** to `8n+1` (9, 17, 25, ... 121, 129). Never pad/duplicate frames; trim `end` (`end' = start + 8n + 1`). Segments shorter than 9 frames are refused with `[CLIP_TOO_SHORT]`. Cap by a max-frames setting (default 121 = LTX's 5 s at 24 fps). Long segments optionally auto-split into consecutive `8n+1` pieces of at most max-frames. |
| Frame rate | resample to a target fps (default 24 for LTX, 16/25/30 selectable) with `-fps_mode cfr`, *then* count frames. The half-open selection stays in source frames; the exported count is computed in target frames so `(frames-1)%8==0` holds on the file. |
| Resolution | scale+center-crop (never stretch) to a bucket: width and height multiples of **32** (LTX: `sample_config.ai:95` requires %32), chosen from a list (e.g. 768x512, 512x768, 640x384, 512x512, 960x544). Pick the bucket nearest the source aspect, same idea as the shared `core.data` bucket helpers (`stdlib/trainers/core/data.ai:113-162`); reuse that function with quantization 32 rather than a second table. Even sides then hold automatically, so the odd-side pad hack is unnecessary in this preset. |
| Frame count quantum | preset field `frame_step` = 8 (LTX), but the field is per preset so other models can set 4 (4n+1 for e.g. Wan-style VAEs) or 1. Presets are data, not code. |
| Audio | keep for audio-video models (LTX 2.5 is audiovisual, stereo AAC in the owner's runs); off for video-only models. Cut with the same `atrim` rule so audio length equals frames/fps. |
| Codec | H.264 CRF 18 yuv420p MP4 (matches today). Optionally PNG-sequence output for trainers that want frames. |
| Report | the dialog shows resulting `W x H x F @ fps`, duration, and warns when the clip would be dropped by a trainer's limits (e.g. LTX `max_items` 4096, `ltx25/dataset_run_config.ai`). |

All bucket/frame-count math is pure and goes into the promoted `video_clip` module with unit
tests in the style of `tests/clip_logic.ai` (snapping table, refusal cases, cut argv).

### 4.4 What trainers can consume, and when

- Now: **PNG frames + `.txt`** (image LoRA, including LTX 2.5's image-dataset path and Krea 2 /
  Z-Image / FLUX.2 / H3). This is the immediately useful output.
- Soon: **MP4 + `.txt`** once an AIR trainer admits a video dataset
  (`ltx25/video_cache.ai` production is closed today). Clip should therefore write the preset
  metadata into `.clip-manifest.json` so a future trainer index can verify frames/size/fps without
  decoding. The concept's video-only `frames`/`length` settings (`settings.ai:878-879`) are
  sample-side; do not repurpose them.
- Add a TrainerAir validation in `dataset_inputs.plan`/Start Training: when the model is a video
  model and the folder contains MP4s whose manifest says `frames % 8 != 1`, list them as problems
  (the existing `problems` array pattern, `dataset_inputs.ai:15-17`).

### 4.5 Handoff contract between TrainerAir and Clip (both options)

```
Genesis-Clip.exe [VIDEO ...]
  --dataset  <folder>        output folder (concept path); also the file-picker start
  --preset   <name|json>     dataset preset (4.3): "ltx25-24fps-768x512", "frames-every-8", ...
  --caption  empty|trigger|shared  [--caption-text TEXT]
  --manifest <file>          write {exported:[{file,caption,start,end,frames,w,h,fps}], state}
  --theme/--accent/--scale   from TrainerAir ui.* keys (launched exe matches the look)
  --export OUTDIR VIDEO LIST.json   (existing headless mode, same code path)
Exit code 0 = done (manifest written); 2 = cancelled; 1 = failed. Cancel file as today.
```

TrainerAir reads the manifest after the child exits (or polls it) and then refreshes the dataset
table/statistics and offers "Caption these clips" (opens the Captioner).

---------------------------------------------------------------------------------------

## 5. (d) Step-by-step plan

Phase tags: **G** = Genesis repo only (allowed now), **T** = TrainerAir change (needs the HOLD
lifted or an owner OK), **A** = AIR change (needs the HOLD lifted). No step below was done.

### Phase 0: Prepare in Genesis (no hold impact)

1. **G** `src/clip_export.ai`: add the pure dataset-preset functions: `snap_frames(len, step, max)`,
   `bucket_for(w, h, buckets, quantum)`, `fps_filter`, `dataset_mp4_argv(...)` (scale+crop to the
   bucket, `-fps_mode cfr`, `-frames:v` = snapped count). Keep `mp4_argv` for the Original mode.
2. **G** `src/clip_model.ai`: `[CLIP_TOO_SHORT]` refusal, auto-split helper, manifest encode
   (`manifest_json`), no UI.
3. **G** `src/clip_export.ai`: write `.txt` for MP4 outputs and a caption-default mode; write
   `.clip-manifest.json`; skip already-exported identical segments.
4. **G** `tests/clip_logic.ai`: cases for 8n+1 snapping (8, 9, 16, 17, 121, 130), bucket choice on
   odd/even sources, fps resampling count, manifest round trip, collision handling. Run with
   `GENESIS_CLIP_TESTS`.
5. **G** `src/clip_main.ai`: flags `--dataset --preset --caption --caption-text --manifest
   --theme --accent --scale`, force the native provider when `--dataset` is given
   (no gcompose, no GPU), exit codes as in 4.5, plus a "Dataset preset" panel (preset dropdown,
   resulting `WxHxF@fps`, caption mode).
6. **G** `windows/clip.cmake`: unchanged; package `Genesis-Clip.exe` with
   `genesis-native-audio.dll`, `air-native-dialogs.dll`, `genesis-media-runtime.txt` (already the
   stage set) so it can be unzipped beside TrainerAir. Document the stage layout.

### Phase 1: Launch from TrainerAir (needs T, no A)

7. **T** `ui/backends.ai` (Runtime catalog, near the `h3.*`/`ltx25.*` rows at `backends.ai:271`):
   add `Tools|1|P|tools.clip_program|Genesis Clip program|` (file). Default empty.
8. **T** new `ui/clip_link.ai` (about 150 lines): build the argv, `runner.command("Genesis Clip",
   argv, workspace, "", false)` (CPU, so no GPU guard), parse the manifest into a status string.
   Mirrors `dataset_inputs.ai`'s command construction.
9. **T** `ui/view.ai` `tools_page` (`view.ai:553`): replace the disabled "Video clip and frame
   extraction" with a live "Clip videos..." button plus a source-video picker; also a "Clip into
   this dataset" button on the selected concept row. `ui/main.ai`: key handling next to
   `pick_path`/`key_tool_stats`.
10. **T** `ui/state.ai`: one status field for the last Clip result; `ui/dataset_inputs.ai`: the
    8n+1/size validation for video models (4.4).
11. **T** after the child exits: refresh dataset statistics; offer "Caption these clips"
    (hands the folder to the Captioner, which is on the other TrainerAir branch, **owner to say
    which**).
12. **T/G** acceptance on Windows: launch from TrainerAir, mark three segments of a real 1080p 30 fps
    source, export "ltx25-24fps-768x512", check file frame counts with `ffprobe` (all `8n+1`, 768x512,
    24 fps, audio length == frames/fps), confirm `.txt` sidecars and manifest, run Dataset
    statistics, open Captioner on the folder, and confirm `std.thumb_grid` shows the new clips.

### Phase 2: Promote shared modules (needs A; after the HOLD lifts)

13. **A** `toolkits/portable/audio_out.ai` + provider DLL source (from `native_audio.cpp`, host-neutral
    names), plus staging in `tools/build-windows-app.ps1` and `toolkits/portable/CMakeLists.txt`
    beside `air_native_dialogs`; a gate like the other portable providers (`native_gate.py`).
14. **A** `stdlib/video_frames.ai` (or extend `std.media`): `probe_video`, `frame_at`, persistent
    decoder child with request/response channel, cancel, bounded scratch; gate
    `tests/stdlib/video_frames.ai` using a short synthetic clip (same style as
    `tests/stdlib/thumb_grid.ai`). `std.thumb_grid` switches its video first-frame path to it.
15. **A** `stdlib/trainers/core/video_clip.ai`: move `clip_model` + pure `clip_export` here
    (segments, cut argv, presets, 8n+1, buckets, manifest); `tests/trainers/video_clip.ai`
    (the current `tests/clip_logic.ai` ported). Add Runtime keys `media.ffmpeg`/`media.ffprobe`.
16. **A** `docs/stdlib` + `agent/maps/libraries.map` rows; update `toolkits/portable/README.md`.
17. **G** `src/clip_*.ai`: import `std.trainers.core.video_clip`, `std.video_frames`,
    `toolkit.portable.audio_out`, `toolkit.portable.dialogs`; delete `native_dialogs.ai`,
    `ffmpeg.ai`, `native_audio.ai`, the pure parts of `clip_export/clip_model`; keep a
    `media_runtime.ai` shim that fills the two Runtime keys from `genesis-media-runtime.txt`.
    Re-run Genesis's own gates (Genesis-AIR editor must still behave identically).

### Phase 3: Embedded screen (optional; needs T and A)

18. **T** `ui/clip/` (state, view, input): a surface-widget port of `clip_ui.ai` painting over the
    shared `video_clip` engine; page registered as `"Clip"` next to `"Datasets"`; transport via
    `toolkit.portable.transport` + the audio clock rule.
19. **T** replace the Phase 1 button with a tab switch; keep `Genesis-Clip.exe` as a
    crash-isolated fallback and for headless export in CI.
20. **T** ensure the playback/export tasks run inside `task.scope`s that never block the training
    event loop; add a "pause Clip while a run is active" guard (it must not take the GPU: native
    provider only).

### Open questions for the owner

- Which TrainerAir branch holds the Captioner screen and Dataset browser (not on `main`,
  `ltx25-native`, `audio`)? Clip's UI should reuse its card/grid.
- Target video model(s) first: LTX 2.5 (8n+1, %32) or others (4n+1)? Presets are data, so this is
  only the default.
- Are MP4 datasets expected to feed a trainer soon (LTX video cache production is closed)? That
  decides whether MP4 or PNG frames is the default output preset until then.
- Which preset sizes/fps are the owner's defaults (the LTX examples use 288x512/24 fps and
  576x1024 delivery; training buckets are not defined in the sources read)?
- OK to promote the native audio provider into AIR as `audio_out` (it is the only item that adds
  a new native DLL to the AIR build)?

### Risks

- Frame-accurate scrub with one FFmpeg process per picture is slow on long 4K sources; the
  persistent decoder (step 14) is the real fix, and Phase 1 should cap the monitor resolution.
- `8n+1` counted in target frames after fps resampling can differ from the user's marked source
  frames by up to one frame; the dialog must show the final count and the cut it applied.
- The HOLD: every **T** and **A** step above waits; Phase 0 and the Genesis half of Phase 1 are
  free to proceed.
- FFmpeg here is an external GPL shared build from MM-Air; Clip must keep referencing it by path
  and never bundle it.
