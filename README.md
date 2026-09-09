# Genesis AIR

A native non-linear video editor written in AIR.

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

A real editor, not a showcase.

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
  keyframe button. A parameter whose filter does not exist yet is still shown; touching it
  creates the filter.
- **Filters** — the stack on the selected clip (enable, reorder, remove, and the selected
  filter's own parameters) above a library of **51 filter kinds**, 31 video and 20 audio.
- **Scopes** — histogram, RGB parade and luma waveform, read off the program frame that was
  already fetched for the monitor.
- **Audio** — per-track meters driven by the peak cache, and a strip per audio track with
  gain, pan, mute and solo.

Mouse gestures on the timeline: click to select, drag to move a clip between lanes and along
time, drag within seven pixels of a clip edge to trim it. A whole drag is one undo step —
nothing is written until the pointer is released — and drops snap to neighbouring cuts when
Snap is on.

All of it is driven by project state, saved to and loaded from the AIR editor project schema.

The rule the whole application is built around:

```
user input  ->  editor command  ->  project state changes  ->  UI redraw
```

`std.editor.Document` is the only place a project fact lives. A widget never holds a second
copy of a clip, a track or a transport position; the view reads the document at paint time.
[`src/commands.ai`](src/commands.ai) is the single path to a mutation, and every function in
it is a snapshot capture followed by exactly one toolkit call. **There is no edit arithmetic
in this application** — split, trim, ripple, slip, roll, slide, grouping, undo/redo,
transitions, keyframes, the media pool, subtitles, the mixer and the transport model all come
from AIR's reusable NLE toolkit, which was itself derived from Genesis.

## Source map

| file | what it owns |
|---|---|
| `src/app.ai` | application state. The document is authoritative; everything else here is view state — focus, viewport, dock tab, snapping, clipboard, the in-flight pointer gesture, the prompt. |
| `src/layout.ai` | panel geometry. One function computes where every panel sits, so painting and hit testing cannot disagree about which pixels belong to which panel. |
| `src/chrome.ai` | every clickable control, built once as a list carrying its own rectangle, label and state — plus the filter library and its parameter schemas. The view paints this list; the input layer hit-tests the same list. Neither computes a rectangle. |
| `src/view.ai` | painting. Holds no project state and mutates nothing. |
| `src/input.ai` | which command a click, drag or key means. Never edits the document. |
| `src/commands.ai` | the only path to a mutation: capture for undo, then one toolkit call. No edit arithmetic. |
| `src/provider.ai` | the media seam. Genesis AIR never learns where a frame came from. |
| `src/main.ai` | the verbs and the window loop. |

## Build and run

```sh
cd /home/alex/genesis-air
./build.sh                       # -> build/genesis-air
```

```sh
# headless: paint one frame of a project
build/genesis-air render OUT.png [PROJECT.air]

# headless: build a small project, edit it, save it, paint it
build/genesis-air demo OUT.png [PROJECT.air]

# bounded real-media check through the provider
build/genesis-air probe MEDIA.mp4 OUT.png

# windowed (needs a display)
build/genesis-air open PROJECT.air
build/genesis-air new
```

Environment: `AIRC` / `AIR_HOME` override the toolchain, `GENESIS_GCOMPOSE` points at the
media worker, `GENESIS_FAKE_PROVIDER=1` forces the deterministic provider, `GENESIS_SCRATCH`
sets the provider's scratch directory.

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

Actions that need a path — Add, Open, Save-as, Render, Relink — open a prompt on the status
line: type the path, Enter to accept, Escape to cancel. The canvas window has no file dialog.

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

Five operations: `probe`, `thumbnail`, `source_frame`, `program_frame`, `envelope`. The
donor's wire — one `ENC` line of 103 positional fields — stops inside `provider.ai`.

**Process isolation is preserved.** Genesis measured NVIDIA OpenCL initialization crashing
intermittently against a UI GL/GLX stack, so the compositor stays out of this process. The
provider drives `gcompose --serve` as a separate process and reads its `DONE`/`ERR` reply.

`gcompose` is selected automatically when its worker is present; otherwise the fake provider
is used, so the application always runs.

## Tests

```sh
python3 tests/run_tests.py                                  # headless, no GPU needed
python3 tests/run_tests.py --media SMALL_CLIP.mp4           # adds the real gcompose smoke
```

- **101 application facts** through the command layer with the fake provider: startup,
  project create/save/load, media import, every timeline edit, selection, grouping,
  transitions, fades, keyframes, markers, subtitles, the filter stack, the mixer including
  solo-wins, both transports, panel focus and pool/ruler clicks, keyboard commands, and
  undo/redo compared exactly in both directions — plus the chrome: every toolbar, timeline
  toolbar, dock tab, track header and inspector control is clicked at the centre of the
  rectangle it was BUILT with, which is what proves painting and dispatch share one geometry
  rather than two that happen to agree. The drag gesture is asserted to land as a single
  undo step, and the prompt is asserted to route a committed line to the action that opened
  it.
- **453 control clicks** across the four inspector tabs. Every control the chrome builds is
  clicked at the centre of the rectangle it was built with, and the resulting document and
  application state is diffed against a baseline. Two properties are asserted, and both catch
  bugs that a screenshot cannot show: **no two enabled controls in a panel may overlap** — an
  overlapped control is unreachable and the click silently runs the one on top of it — and
  **every control must report an outcome**, so a button drawn but wired to nothing shows up.
  Rows below the fold are scrolled into view first, the way a person would.
- **Render smoke**: the demo project paints a 1600×980 frame and saves its project.
- **gcompose smoke** (bounded): open one real file, read its real frame count, place a short
  clip, decode one source frame, paint, exit — with no worker left behind.

A missing worker or fixture is reported **BLOCKED**, never passed.

## Known gaps

Gaps in AIR itself — things this application wanted and the language or toolkit could not
express — are recorded in [`docs/AIR_GAPS.md`](docs/AIR_GAPS.md) with the smallest fix, the
file it belongs in and a reproducer. Each was recorded and worked around visibly BEFORE it
was fixed; all three have since been closed in AIR, on the commit `air-sdk.conf` pins:
`std.editor` gained `set_clip_speed`, `set_clip_reverse` and `reorder_track`, and
`std.vector_font` was redrawn — all 95 printable ASCII glyphs, at the right proportions.

Gaps in this application:

- **The media worker is still invoked once per request.** `gcompose --serve` is designed to
  be driven over a long-lived pipe. When this project started AIR had no primitive for that;
  it now does (`std.process.spawn_piped` and friends, on AIR `main`), but `air-sdk.conf`
  still pins the pre-merge NLE commit, so the provider has not adopted it yet. Doing so
  means repointing the pin and rebuilding the compiler for the new opcodes — a separate
  change from the UI. Until then each request re-initialises the decoder, which is correct
  and safe but slower than it needs to be.
- Program preview is the topmost clip under the playhead, not a composite. Compositing needs
  the donor's `ENC` path; the seam is ready for it (`program_frame` already receives every
  visible source).
- Filter parameters are stored and keyframed, but nothing renders them yet: the provider
  returns source frames, so a brightness value is recorded on the clip and not yet applied
  to the picture. The inspector is honest about this only in the sense that the program
  monitor does not change — closing it is the compositing work above.
- No export. `Render` writes the window's own frame (`gui.screenshot`), which is a still of
  the editor, not an encode of the timeline.
- Zoom and pan live in this application (`app.Viewport`) because the AIR NLE toolkit records
  viewport policy as deliberately unported. If it proves generic it should be upstreamed.
- The menu bar is drawn but not interactive; everything it would hold is on the toolbar, the
  timeline toolbar or a key.

## Provenance

Behavior oracle: [`CodeAlexx/Genesis-`](https://github.com/CodeAlexx/Genesis-) at
`b732f1c246493f029b531d3941e759b8d912bda1`, read-only and unmodified. The reusable editor
behavior was already ported into AIR; this application consumes it rather than reimplementing
it. `CodeAlexx/dif-inference` was consulted only for the `gcompose` wire; none of its server,
browser, model-capability, job-queue or Comfy-compatibility code is here.
