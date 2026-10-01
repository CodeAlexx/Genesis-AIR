# Genesis AIR

A native non-linear video and audio editor written in AIR. The Windows build uses Win32,
Direct2D and Windows audio output. GTK is forbidden in the Windows build configuration.

Built with **AIR**, a native compiler designed for agent-assisted development: [air-lang.pages.dev](https://air-lang.pages.dev/)

![Genesis AIR main editor](genesis-air-main.png)

Genesis AIR **uses** AIR; it is not part of it. The application lives here, the language,
compiler and toolkit live in their own repository, and no AIR source is copied into this
project — [`air-sdk.conf`](air-sdk.conf) records which AIR commit it is built against and
[`build.sh`](build.sh) discovers the toolchain from there.

```
Genesis AIR application     this repository
        |
        v
AIR portable toolkit        std.widgets, std.draw, std.gui, std.timeline, std.media_*
        |
        v
AIR editor/NLE toolkit      std.editor, std.editor_io, std.editor_view
        |
        v
AIR stdlib
```

## What it is

An AIR-native editing application with a tested project and control layer. Its media
renderer covers the paths listed below; [the control acceptance ledger](docs/CONTROL_COVERAGE.md)
tracks every exposed control and its remaining media gate.

```
menu
toolbar        Add  Open  Save  New  Render  Undo  Redo  Razor all tracks
               Start Prev Play Next End  Reload            worker readout
+-----------+-------------------+-------------------+-------------------+
| MEDIA     | SOURCE monitor    | PROGRAM monitor   | Properties        |
|  bins,    |  own transport,   |  own transport,   | Filters           |
|  Relink   |  in/out marks     |  in/out marks     | Scopes            |
|  Add clip |                   |                   | Audio             |
|  Source   |                   |                   |                   |
+-----------+-------------------+-------------------+                   |
| Split Razor Lift Ripple  Cut Copy Paste  Append Overwrite Insert       |
| Marker Transition Group Snap                    Zoom out  Fit  Zoom in |
+-----------+------------------------------------------------+          |
| V2 eye L M S x |                                            |          |
| V1 eye L M S x |  clips, transitions, fades, markers,       |          |
| A1 eye L M S x |  waveforms, ruler, playhead                |          |
| A2 eye L M S x |                                            |          |
| +V  +A         |                                            |          |
+----------------+--------------------------------------------+---------+
status / prompt line
```

The right-hand dock has four tabs:

- **Properties** — everything about the selected clip in one scrolling column: name, source
  and timeline ranges, size/position/rotate (PiP X, Y, W, H, rotation, opacity), blend mode,
  fades, speed, audio gain, a three-band EQ with pan, dynamics (compress, gate, normalize,
  limiter), thirteen audio effects (reverb, delay and delay decay, pitch, low pass, high
  pass, tremolo, bass, treble, notch, chorus, flanger, phaser), a ten-band graphic EQ, and
  clip grade. Every parameter has a decrement, a click-anywhere bar, an increment and a
  keyframe button. Slider drags update live, clamp on release outside the control, and
  form one undo step; Escape restores the previous value. A parameter whose filter does not exist yet is still shown; touching it
  creates the filter. Some keyframe actions are refused while their media automation path
  is unfinished; the [control ledger](docs/CONTROL_COVERAGE.md) tracks those gaps.
- **Filters** — the stack on the selected clip (enable, reorder, remove, and the selected
  filter's own parameters) above a library of **51 filter kinds**, 31 video and 20 audio.
  Text has an editable content field and LUT3D has a `.cube` path field. These strings
  persist in revision 2 projects; revision 1 projects still load.
- **Scopes** — histogram, RGB parade and luma waveform, read off the program frame that was
  already fetched for the monitor.
- **Audio** — live stereo output meters in dBFS after the complete mix. Tracks with sound,
  including embedded audio on video tracks, expose gain, pan, mute and solo. Selected clips
  expose their own gain, pan, EQ and audio effects. Waveforms also cover embedded video audio.

Mouse gestures on the timeline: click a clip to select it, drag a clip to move it between
lanes or along time, and drag within seven pixels of a clip edge to trim it. Each monitor has Start, Previous frame, Play/Pause, Stop, Next frame and End buttons,
plus a draggable seek bar. Seeking pauses the transport so its clock cannot override the
requested frame. Drag the ruler
above the lanes to scrub the program preview; click it to seek once. A clip move or trim is
one undo step — nothing is written until the pointer is released — and drops snap to
neighbouring cuts when Snap is on.

The right inspector scrolls under the pointer with the mouse wheel. Its scrollbar supports
track clicks for page movement and direct thumb dragging; it does not depend on prior focus.

All of it is driven by project state, saved to and loaded from the AIR editor project schema.

The rule the whole application is built around:

```
user input  ->  editor command  ->  project state changes  ->  UI redraw
```

`std.editor.Document` is the only place a project fact lives. A widget never holds a second
copy of a clip, a track or a transport position; the view reads the document at paint time.
[`src/commands.ai`](src/commands.ai) is the single path to a mutation. Each undoable action
captures one snapshot, then applies its toolkit operations. **There is no edit arithmetic
in this application** — split, trim, ripple, slip, roll, slide, grouping, undo/redo,
transitions, keyframes, the media pool, subtitles, the mixer and the transport model all come
from AIR's reusable NLE toolkit, which was itself derived from Genesis.

## Source map

| file | what it owns |
|---|---|
| `src/app.ai` | application state. The document is authoritative; everything else here is view state — focus, viewport, dock tab, snapping, clipboard, the in-flight pointer gesture, the prompt. |
| `src/layout.ai` | panel geometry. One function computes where every panel sits, so painting and hit testing cannot disagree about which pixels belong to which panel. |
| `src/chrome.ai` | every clickable control, built once as a list carrying its own rectangle, label and state — plus the filter library and its parameter schemas. The view paints this list; the input layer hit-tests the same list. Neither computes a rectangle. |
| `src/view.ai` | painting. Reads project state and caches TrueType glyphs; media work stays outside paint. |
| `src/input.ai` | which command a click, drag or key means. Never edits the document. |
| `src/commands.ai` | the only path to a mutation: capture once for undo, then apply toolkit operations. No edit arithmetic. |
| `src/provider.ai` | the media seam: source probe, frame and waveform retrieval, and the worker transport. |
| `src/timeline_media.ai` | resolves AIR editor clips into the worker's preview, encode, and audio commands. |
| `src/transport_clock.ai` | elapsed-time transport fallback; native Windows playback uses the audio device sample clock. |
| `src/native_audio.ai`, `windows/native_audio.cpp` | typed C ABI adapter for Windows audio queues, sample clock and stereo output levels. |
| `src/preview.ai` | asynchronous latest-request preview and waveform mailbox. |
| `src/ui_text.ai` | cached, proportional system TrueType UI text through `std.font`. |
| `src/main.ai` | the verbs and the window loop. |

## Build and run

```sh
cd Genesis-AIR
./build.sh                       # -> build/genesis-air

# Build the separate media worker from CodeAlexx/Genesis- (FFmpeg/OpenCL prerequisites
# are described in that repository), then point Genesis AIR at it:
cd ../Genesis
git switch codex/air-raw-transition # RAW transition partners and Stabilize source frames
cargo build --release -p gcompose
export GENESIS_GCOMPOSE="$PWD/target/release/gcompose"
cd ../Genesis-AIR
```

On Windows, use PowerShell 7, Visual Studio 2022 C++ Build Tools (including CMake),
Git, and WSL Ubuntu with a compatible AIR compiler. The compiler emits C in WSL;
MSVC builds the Windows application. The installed editor runs directly as a Windows GUI
executable, and its redirected media subprocesses do not open console windows.

```powershell
.\setup-windows.ps1
.\build-windows.ps1 -RunTests -LinuxCompiler /path/to/airc
.\Genesis-AIR.exe open .\project.air
```

Both setup and build default to the repository root. The output includes
`Genesis-AIR.exe`, the native host/audio DLLs, `genesis-gcompose.exe`, FFmpeg DLLs and
executables, `OpenCL.dll`, `fonts/` and dependency `licenses/`. Keep these together.
The default compiler path is `/root/AIR-win-port-build/bin/airc`; override it with
`-LinuxCompiler` and the distribution with `-Distro` when needed.

Setup creates isolated SDK and compositor checkouts under `build-windows/`, applies the
tracked compositor patch, and builds the native media dependencies. Existing checkouts
at a different revision are preserved and reported. `-AirSdk` or `AIR_HOME` overrides SDK
discovery. `-Destination` stages a build elsewhere; run setup with the same destination
when preparing a complete package. `-Launch` opens the editor after building.

The SDK is pinned in [air-sdk.conf](air-sdk.conf). The compositor, OpenCL and Rust revisions
are in [windows/source-pins.json](windows/source-pins.json); FFmpeg and font downloads have
pinned digests. Windows compositor changes, including FP32 intermediates, 16-bit decoding
and encoding, HDR conversion and arbitrary preview dimensions, live in
[windows/gcompose-windows.patch](windows/gcompose-windows.patch).

```sh
# headless: paint one frame of a project
build/genesis-air render OUT.png [PROJECT.air]

# headless: build a small project, edit it, save it, paint it
build/genesis-air demo OUT.png [PROJECT.air]

# inspect source media, optionally saving a short test project
build/genesis-air probe MEDIA.mp4 OUT.png [PROJECT.air]

# compose the saved project's playhead frame, or encode its export range
build/genesis-air preview OUT.png PROJECT.air
build/genesis-air export OUT.mp4 PROJECT.air
build/genesis-air audio OUT.wav PROJECT.air   # mix audio from the playhead

# windowed (needs a display)
build/genesis-air open PROJECT.air
build/genesis-air new [--appearance dark|light|system]
```

The window enlarges the editor canvas, text, controls, and pointer targets to 1.5× on
large displays (at least 2400×1250) and 2× on 4K sized windows (at least
3200×1600). Smaller windows retain the original 1× layout. This changes only the
editor interface; project dimensions and exported video resolution stay as set in
the project.

The application first finds `genesis-gcompose.exe` beside its executable, then checks
sibling source builds and PATH. `GENESIS_GCOMPOSE` overrides worker discovery. FFmpeg and
FFprobe are also discovered beside the executable. `GENESIS_FAKE_PROVIDER=1` selects the
deterministic test provider; real preview and export require the compositor.
`GENESIS_SCRATCH` overrides state storage, which defaults to `%LOCALAPPDATA%/GenesisAIR`
on Windows. This holds autosave, preview mailboxes, export progress and `errors.jsonl`.
Coded `[GA_*]` errors appear in the status line and local structured diagnostics;
Help > Show error details reports the diagnostics path.

The UI uses system Segoe UI through `std.font`, with proportional metrics and cached
antialiased glyphs. Colors come from `std.application_theme` and `std.desktop_styles`;
View selects the shared palettes. Titles and captions use installed TrueType faces and
the bundled Noto Sans JP fallback. `GENESIS_FONT` lists additional title faces, separated
by semicolons on Windows and colons on Unix. Add, Open, Save as, Export and Relink use
native Windows file pickers. On Linux they use `zenity` when available, with a keyboard
path prompt as fallback.

Export uses the sequence dimensions and rate, including fractional rates; a 4K sequence
is composed at 3840x2160 rather than an enlarged preview. File offers these profiles:

| Profile | Container | Picture | Audio |
|---|---|---|---|
| H.264 SDR | MP4 | 8-bit YUV | AAC |
| HEVC SDR | MP4 | 10-bit YUV | AAC |
| ProRes SDR | MOV | 10-bit YUV | 24-bit PCM |
| Lossless SDR master | MKV | FFV1 16-bit RGB | 24-bit PCM |
| HEVC HDR | MP4 | 10-bit PQ / BT.2020 | AAC |
| Lossless HDR master | MKV | FFV1 16-bit PQ / BT.2020 RGB | 24-bit PCM |

Media decode retains 16-bit precision and composition/intermediate passes use FP32.
The encoded format determines the final quantization. HDR sources are tone mapped to
Rec.709 for the ordinary SDR preview; HDR masters retain PQ / BT.2020. This is not a
calibrated HDR display or a scene-linear grading pipeline.

The headless `export` command selects H.264 for `.mp4`, ProRes for `.mov`, and the
16-bit SDR master for `.mkv`. `--hevc` selects HEVC SDR and `--hdr` selects an HDR
MP4 or MKV. The `render` command writes an editor-canvas PNG. Existing export files are
refused. Export runs from a project snapshot in a background task; the status reports
progress and Escape cancels between frames. Incomplete output is removed.
`export.progress` and `export.cancel` in the scratch directory expose the same scriptable
progress and cancellation path.

Windows playback prepares bounded five-second WAV chunks in the background and queues
native audio buffers. The device's sample clock drives the source/program playhead.
Pause, Stop and seek immediately reset output; gain, pan, mute, solo and audio-effect
edits invalidate queued sound. Picture-only edits preserve it. The meters read the PCM
at the device cursor after mixing. Preview decoding runs on a separate thread; rapid
seeks publish the newest requested frame. Waveform completion is published independently
so an early image result cannot hide a later audio envelope.

The `audio` command writes the program mix from the current playhead for inspection.

## Keys

| | |
|---|---|
| Space | play / pause |
| `s` | split at the playhead |
| Delete / Shift+Delete | lift / ripple delete |
| Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y | undo, redo |
| Left / Right | frame step |
| Home / End | start / end |
| `i` / `o` | mark in / out |
| `m` | marker at the playhead |
| `g` | group the selection |
| `+` / `-`, Ctrl+wheel | zoom |
| Ctrl+C / Ctrl+X / Ctrl+V | copy / cut / paste |
| Ctrl+A | razor every track at the playhead |
| `t` | transition at the selected clip's cut |
| `n` | snapping on / off |
| Tab | next inspector tab |
| Page Up / Page Down, wheel over the dock | scroll the inspector |

Text values and the file chooser fallback use a centered prompt: type the value, Enter to
accept, Escape to cancel.

To put a video on the timeline, use toolbar **Add** to choose and import the file, select its
row in **MEDIA**, then choose **Add clip** at the bottom of that panel. Import alone does not
place a clip. **Add clip** appends it to V1, selects it, and reports the added filename in the
status line. The ruler above the tracks controls the program playhead; drag it to scrub the
preview or click it to seek once. Use **Save** to write the project; the first save opens a
file chooser.

## The media provider seam

Genesis AIR never learns where a frame came from.

```
Genesis AIR
    |
    +-- editor model (std.editor)
    |
    +-- MediaProvider            src/provider.ai
            |
            +-- gcompose         the existing Genesis worker, in its own process
            +-- fake             deterministic, no FFmpeg/OpenCL/GPU
```

The provider handles probe, thumbnail, source frame, waveform and program frame requests.
`timeline_media.ai` resolves visible clips from `std.editor.Document` and builds the donor's
103-field `PREVIEW`/`ENC` wire. Preview and export use the same resolver. Export holds one
piped worker through `OPEN`, the frame and audio commands, and `CLOSE`.

**Process isolation is preserved.** Genesis measured NVIDIA OpenCL initialization crashing
intermittently against a UI GL/GLX stack, so the compositor stays out of this process. The
provider keeps one `gcompose --serve` process open for probes, thumbnails, waveforms and
previews, so OpenCL starts once and decoders stay open between requests. A worker that exits
or crashes is replaced once and the request retried. Reload and Relink restart it so changed
files are read again. Export runs its own worker.

`gcompose` is selected automatically when its worker is present; otherwise the fake provider
is used for editing and headless checks. Preview and export explicitly require the real worker.

## Playback and seeking on Windows

Each monitor has Start, Previous frame, Play/Pause, Stop, Next frame and End, plus
**Full** for fullscreen playback. F11 opens the focused monitor; Esc or **Exit full**
restores the editor. Transport buttons and the draggable seek bar remain available
in fullscreen. Fullscreen uses a 1280x720 monitor surface; the editor uses 480x270
surfaces. Export resolution comes from the sequence. Space plays or pauses.
Ctrl+O opens a project and Ctrl+S saves it;
Ctrl+Shift+S opens Save as.

Drag the timeline ruler or the playhead line to change program time and preview.
The line takes precedence over a clip underneath it, so seeking cannot move or
trim that clip. Video/audio lane crossing is refused with `GA_TRACK_KIND`. Cached
frame bitmaps appear on visible video clips after paused background extraction;
waveforms also appear on video clips that contain audio.

Both monitors reuse unchanged pictures. Source transport changes keep the program
picture, while timeline edits refresh it. Reload, Relink and opening a project
invalidate the background media cache, including LUTs replaced at the same path.
Timeline thumbnails and waveforms wait until both transports are paused.

The worker keeps decoder image buffers between frames, composes in FP32, and packs
the final preview on the GPU before downloading it. FLOAT intermediates and master
exports retain their precision. Windows uses D3D11 decoding when supported and prefers
a discrete OpenCL GPU on hybrid PCs. Software decoding remains available with
`GENESIS_SOFTWARE_DECODE=1`; `GENESIS_OPENCL_DEVICE` selects a GPU by name substring.
`GENESIS_MEDIA_PROFILE=1` emits colour, RGB conversion and preview phase timings.

A 120-sample measurement of consecutive frames on the supplied 4K/59.94 AV1/PQ clip
and RTX 5080 reached 59.49 worker previews per second at a 1280x720 working canvas,
with identical frame-zero pixels after rewind. This excludes Windows canvas painting,
mailbox conversion and audio; sustained 60 fps in the editor and long-run
synchronization are still acceptance work. The diagnostic defaults to 120 consecutive
frames; `--frame-step 2 --samples 30` reproduces the older sampling pattern.

```powershell
python tests/preview_performance.py --worker .\genesis-gcompose.exe --source 'C:\path\to\clip.mp4'
```

## Tests

Windows acceptance checks:

```powershell
.\build-windows.ps1 -RunTests -NativeBuild .\build-windows\native-pro
$env:GENESIS_WORKER_WRAPPER = (Resolve-Path .\build-windows\native-pro\bin\Release\genesis-worker-wrapper.exe).Path
python tests/real_media.py --binary .\Genesis-AIR.exe --worker .\genesis-gcompose.exe --stdlib .\build-windows\AIR-SDK\stdlib
python tests/pro_media.py --binary .\Genesis-AIR.exe --worker .\genesis-gcompose.exe
python tests/precision_media.py --binary .\Genesis-AIR.exe --worker .\genesis-gcompose.exe
```

The Windows gate verifies 152 saved application facts, three native file-drop facts,
749 control clicks with overlap checks, 65 native media/project checks and 58 focused
inspector/transport/audio checks. Native device tests verify queueing, advancing sample
clock, stereo output levels and immediate Stop. The asynchronous preview test measures
red/blue pixels after rapid seeking, unchanged source caching, rewind to frame zero,
timeline bitmaps and embedded audio waveform delivery.
The generated-media suite covers effects, transitions, captions, Unicode, audio-only
projects, worker crash recovery and export cancellation/cleanup.

The pro-media suite measures 4K detail, fractional rate, ProRes/24-bit PCM, portrait
preview/export aspect ratio and exact multicam cuts. The precision suite measures 1024
distinct values through a filtered three-layer 16-bit master and audible samples after
181 seconds. It also verifies 100-nit HDR title white and HEVC 10-bit PQ/BT.2020
output. Its optional `--hdr-source PATH` checks a supplied 4K PQ source against a
lossless master and FFmpeg's floating-point SDR tone-map reference. See the
[control acceptance ledger](docs/CONTROL_COVERAGE.md) for scope and remaining work.

The following Unix/X11 checks are historical reproduction commands. The current native
Windows audio adapter has not been validated on Linux:


```sh
# Deterministic command, UI-control, and canvas checks.
python3 tests/run_tests.py --airc /path/to/AIR/build-gcc15/bin/airc \
  --stdlib /path/to/AIR/stdlib --binary build/genesis-air

# Bounded worker probe, preview, and MP4 check, with a small existing media fixture.
GENESIS_GCOMPOSE=/path/to/gcompose python3 tests/run_tests.py \
  --airc /path/to/AIR/build-gcc15/bin/airc --stdlib /path/to/AIR/stdlib \
  --binary build/genesis-air --media /path/to/fixture.mp4

# Generated red/blue and mixed-rate video plus tone: compares pixels and audible AAC.
python3 tests/real_media.py --binary build/genesis-air \
  --worker /path/to/gcompose --stdlib /path/to/AIR/stdlib

# Optional X11 Play/Pause canvas check (requires python-xlib and an X display).
python3 tests/window_playback.py --binary build/genesis-air \
  --stdlib /path/to/AIR/stdlib

# Optional X11 import, timeline placement, ruler scrub, and save check.
python3 tests/window_file_picker.py --binary build/genesis-air \
  --stdlib /path/to/AIR/stdlib

# Exercise the same path at 4K with a generated video and the real worker.
python3 tests/window_file_picker.py --binary build/genesis-air \
  --stdlib /path/to/AIR/stdlib --maximized --worker /path/to/gcompose

```

- **152 application facts** through the command layer with the fake provider: startup,
  project create/save/load, media import, every timeline edit, selection, grouping,
  transitions, fades, keyframes, markers, subtitles, the filter stack, the mixer including
  solo-wins, both transports, elapsed-time playback, reverse sampling at mixed frame
  rates, panel focus and pool/ruler clicks, keyboard commands, and
  undo/redo compared exactly in both directions — plus the chrome: every toolbar, timeline
  toolbar, dock tab, track header and inspector control is clicked at the centre of the
  rectangle it was BUILT with, which is what proves painting and dispatch share one geometry
  rather than two that happen to agree. The drag gesture is asserted to land as a single
  undo step, and the prompt is asserted to route a committed line to the action that opened
  it.
- **749 control clicks** across the four inspector tabs. Every control the chrome builds is
  clicked at the centre of the rectangle it was built with, and the resulting document and
  application state is diffed against a baseline. Two properties are asserted, and both catch
  bugs that a screenshot cannot show: **no two enabled controls in a panel may overlap** — an
  overlapped control is unreachable and the click silently runs the one on top of it — and
  **every control must report an outcome**, so a button drawn but wired to nothing shows up.
  Rows below the fold are scrolled into view first, the way a person would.
- **Canvas smoke**: `build/genesis-air demo OUT.png PROJECT.air` paints a 1600×980 frame
  and saves its project.
- **Real media**: the worker probe reads frame count, size, frame rate and audio presence;
  the preview and MP4 paths compose three colored clips in track order, add a timed caption,
  apply all eleven transition kinds across a touching cut, plus overlapping and
  short-gap crossfades, and check gamma, sepia, vignette, levels, crop,
  keyed overlay pixels, Text and Timer previews and exports,
  Stabilize on a synthetic shaky clip with keyed Strength and an upper-lane export,
  export an audio-only timeline, verify a 24 fps source across a full 30 fps sequence
  second, write an audible playback WAV (including a spaced output
  path), export a nine-frame 24 fps sequence with audio,
  retime and reverse a rising tone, keep freeze-frame
  audio silent, mix and pan a tone, apply picture and audio filters
  to the same clip, and reject an unsupported
  effect instead of silently dropping it.

## Known gaps

- Audio filter state is recreated for each playback chunk. Stateful effects and clip-wide
  normalization need continuous processing and boundary measurements before their live
  playback can be treated as equivalent to a whole-clip export.
- Nested sequence rendering, audio automation, animated speed and some filter combinations
  remain unsupported and are refused explicitly. The library has mappings for 31 video and
  20 audio effects; representative output checks do not establish every parameter value,
  ordering combination or keyframe behavior.
- The source/program transport uses a Windows audio sample clock, but sustained preview
  throughput and long-timeline synchronization still need measured acceptance on larger
  projects. Scrubbing updates pictures while paused; it does not audition audio continuously.
- HDR preview is SDR tone mapped, and scopes describe that preview. The HDR master path
  preserves PQ precision and color tags, but reference-monitor output and scene-linear
  compositing are not implemented.
- Text uses per-scalar TrueType glyphs. Complex shaping and right-to-left layout need more
  work. Captions use a fixed lower-third position. Uncovered glyphs are refused with their
  Unicode code point.
- Stabilize estimates translation within 24 output pixels. Rotation, perspective and long
  camera-path smoothing are not implemented.
- Worker exchanges have bounded deadlines and preview runs outside the window thread.
  Reload or Relink is needed after replacing source media or a LUT file in place.
- Export cancellation takes effect between frames; a slow frame finishes first. Output
  destinations are created only when absent, and partial output is cleaned after failure.
