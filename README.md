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

A real editor shell, not a showcase: a media pool, source and program monitors with
independent transports, a filter stack, a properties panel, a mixer, and a multi-track
timeline with clips, transitions, waveforms, markers, a ruler and a playhead — all of it
driven by project state, saved to and loaded from the AIR editor project schema.

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

- **79 application facts** through the command layer with the fake provider: startup,
  project create/save/load, media import, every timeline edit, selection, grouping,
  transitions, fades, keyframes, markers, subtitles, the filter stack, the mixer including
  solo-wins, both transports, panel focus and pool/ruler clicks, keyboard commands, and
  undo/redo compared exactly in both directions.
- **Render smoke**: the demo project paints a 1600×980 frame and saves its project.
- **gcompose smoke** (bounded): open one real file, read its real frame count, place a short
  clip, decode one source frame, paint, exit — with no worker left behind.

A missing worker or fixture is reported **BLOCKED**, never passed.

## Known gaps

- **A persistent media worker is not possible in AIR today.** `gcompose --serve` is designed
  to be driven over a long-lived pipe, but AIR exposes no primitive that hands back a
  writable stdin: `process.exec` inherits stdio and waits, and `process.run` redirects to a
  file. The provider therefore makes one bounded worker invocation per request, which is
  correct and safe but re-initialises the decoder each time. *Smallest fix:* a
  `process.pipe`-style op returning writable-stdin and readable-stdout handles, in AIR's
  `stdlib/process.ai` plus the runtime op that backs it. *Reproducer:* `printf 'NFRAMES f\n'
  | gcompose --serve` answers in one round trip; keeping that process alive for a second
  request cannot be expressed. AIR was **not** modified for this.
- Program preview is the topmost clip under the playhead, not a composite. Compositing needs
  the donor's `ENC` path; the seam is ready for it (`program_frame` already receives every
  visible source).
- No export/render yet. The provider seam has the shape for it; it is deliberately out of
  scope here.
- Zoom and pan live in this application (`app.Viewport`) because the AIR NLE toolkit records
  viewport policy as deliberately unported. If it proves generic it should be upstreamed.
- Drag-to-move clips and edge-trim by mouse are not wired; the commands exist
  (`move_clip`, `trim_start`, `trim_end`) and are covered by tests, but the pointer gestures
  that would call them are not. Clicking selects, the ruler scrubs.
- The menu bar is drawn but not interactive; commands are reachable from the keyboard.

## Provenance

Behavior oracle: [`CodeAlexx/Genesis-`](https://github.com/CodeAlexx/Genesis-) at
`b732f1c246493f029b531d3941e759b8d912bda1`, read-only and unmodified. The reusable editor
behavior was already ported into AIR; this application consumes it rather than reimplementing
it. `CodeAlexx/dif-inference` was consulted only for the `gcompose` wire; none of its server,
browser, model-capability, job-queue or Comfy-compatibility code is here.
