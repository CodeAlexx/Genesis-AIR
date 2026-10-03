# AIR gaps found by Genesis AIR

Genesis AIR uses AIR; it does not modify it casually. When building this application ran into
something AIR could not express, the gap was recorded here first — with the smallest fix, the
file it belonged in, and a reproducer — and the application worked around it in a way that
stayed visible to the person using it, rather than pretending the feature existed.

The AIR gaps below are closed in the compatible SDK checkout pinned by
`air-sdk.conf` (`genesis-pro-windows` at `65bc08d57537`). This file records
the original issues and their language-level fixes; current renderer acceptance
status lives in [the control ledger](CONTROL_COVERAGE.md).

---

## 1. `std.editor` could not write a clip's speed or reverse flag — CLOSED

**What was missing.** `editor.Clip` carried `speed: f64` and `reverse: bool`, `editor_io`
round-tripped both, and `editor.clip()` read them — but there was no setter. `set_clip_gain`,
`set_clip_enabled`, `set_fade_in` and `set_fade_out` all existed; speed and reverse had no
equivalent.

**Why it mattered.** The inspector's SPEED section could display a clip's rate and reverse
flag and could not change them. Modelling speed as a filter parameter instead was rejected:
`Clip.speed` already existed, and a second store for the same fact is exactly the
disagreement this codebase is built to avoid.

**Fixed by** `set_clip_speed` and `set_clip_reverse` in `stdlib/editor.ai`, beside
`set_clip_gain`. A negative rate is **refused** rather than clamped. Zero is accepted as a
held frame, matching `freeze_frame`; `reverse` remains the separate direction flag.

**Covered by** `stdlib_editor`, which checks rejected negative rates and accepted zero as
well as the writes — including that a refused write leaves the previous rate alone — against its independent Python oracle,
native and reference agreeing.

**In this application** the SPEED section is a rate slider and a reverse switch, like any
other parameter.

---

## 2. `std.editor` could not reorder tracks — CLOSED

**What was missing.** `add_track` appended with the next `order` and `remove_track` deleted;
nothing moved a track to a different lane. `editor_view.lanes` sorts by `Track.order`, so
lane position was entirely determined by creation order.

**Why it mattered.** The conventional layout is video above audio. Because the topmost lane
is the highest `order`, Genesis AIR had to CREATE its default tracks bottom-up to get
V2/V1/A1/A2 top-down — and a track added later with the `+A` button landed at the top of the
stack, above the video, with nothing able to move it down.

**Fixed by** `reorder_track` in `stdlib/editor.ai`, mirroring `reorder_filter`, which already
did exactly this for filter stacks. It renumbers the rest to keep a sequence's orders a dense
`0..n-1` run and clamps a position past the end to the last lane.

**Covered by** `stdlib_editor`: moving the last of four lanes to the front leaves 0..3 with
no hole and no duplicate, a position past the end clamps, and an unknown track is refused.

**In this application** `+A` places the new track below the video, and `+V` above it.

---

## 3. `std.vector_font` was not legible — CLOSED

**What was wrong.** Three things at once, and the first is the one that mattered most:

- **The glyphs were a third of their own advance.** The forms were drawn between x=1 and x=3
  on a 5×7 grid whose pen advanced 7 units. Text set in it read as thin marks separated by
  wide gaps, and at small sizes `a`, `e` and `o` were indistinguishable from `s`.
- **The pen advanced by `advance() + 2`.** The side bearings are part of the outlines, so
  those two units were counted twice, setting the text nearly half again as loose as it
  should have been.
- **The table covered only letters, digits, `+`, `-` and `.`.** Anything else drew as an
  empty box: a timecode lost its colons, a percentage its sign, a path its separators. A
  label made only of unsupported characters — the transport buttons were first labelled
  `|<` `<` `>` `>|` — came out blank.

Dots were a two-point segment 0.2 units long: a fifth of a pixel at ten-pixel type, which the
stroker rounds away, so `0.85` printed as `0 85`.

**Fixed by** redrawing the whole table in `stdlib/vector_font.ai`. All 95 printable ASCII
glyphs are present, drawn between x=0.6 and x=4.4 — nearly the full cell — with letterforms
chosen so the bowls stay open when the stroker fills them; the pen advances by `advance()`;
and a dot is a small closed square that carries area at every size the font is legible at.
`height()` and `advance()` are unchanged, so nothing that measures through
`text_vector_width` moved except in the direction of having more room than it asked for.

**Covered by** `stdlib_graphics_xml_extra`, whose pinned glyph counts and coordinates now
read from `std.vector_font`'s own table and stated metrics rather than from a frozen donor
table.

**Current Genesis UI.** Windows chrome now uses cached TrueType glyphs from
`std.font`, with Segoe UI proportional metrics and physical-resolution antialiasing.
The vector-font work remains useful to portable callers but does not describe the
current Genesis Windows appearance.

---

## Closed earlier

- **No long-lived subprocess with writable stdin.** Recorded here first, then fixed upstream:
  `stdlib/process.ai` gained `spawn_piped` / `write_stdin` / `read_stdout` / `poll` / `wait`,
  backed by `runtime/air_proc_pipe.c`. This project now pins a commit that carries it; the
  export and the interactive provider (probe, thumbnail, waveform, preview) now each keep a
  persistent worker.


## Windows and pro-editor SDK additions (2026-09-30)

- `std.editor.set_sequence_format` changes resolution while preserving existing frame units;
  it refuses a rate change on a populated sequence. Held multicam cuts preserve source sync.
- `std.editor.seek_monitor` uses native source frames and preserves transport state. The
  application explicitly pauses before interactive scrubbing.
- `std.editor.set_clip_pan` writes finite pan values in -1..1, clamps the endpoints and
  refuses missing clips. The SDK regression verifies that pan edits preserve source position
  and sequence duration; Genesis verifies the exposed control changes the mix plan.
- Windows redirected subprocesses and process pipes use `CREATE_NO_WINDOW`, preventing
  FFprobe and media workers from opening consoles. Ordinary unredirected process behavior
  remains available. Native process regressions cover redirected-child console absence.
- Genesis chrome uses `std.font` system TrueType faces with proportional metrics, cached
  antialiased glyphs and physical-resolution rasterization. The earlier vector-font fixes
  remain useful elsewhere; they are no longer the Windows application's typography path.

The application owns its typed Windows audio C ABI adapter and the patched compositor.
These are concrete candidates for reusable native packages, rather than compiler opcodes
that encode Genesis-specific application policy.


## Windows playback integration

The program and source monitors share AIR transport state and geometry for input and
painting. The red timeline playhead is a seek handle above clips; crossing video/audio
lane types is refused before an edit enters undo history. Fullscreen uses the SDK's
existing `ui.fullscreen` operation and keeps AIR-painted transport and seek controls.
The latest-request background renderer publishes frame bitmaps and embedded-audio
waveforms independently of the monitor image.

The compositor now keeps source thumbnails apart from program decoder state, caches
unchanged monitor pictures in AIR, resolves HDR preview colour at monitor dimensions,
and supports native D3D11 decode with software fallback. Decoder buffers are reused;
the FP32 compositor packs preview bytes on the GPU. OpenCL chooses a discrete GPU
on hybrid PCs. The supplied 4K clip measured 59.49 worker previews/second over 120
consecutive frames; mailbox conversion, actual window throughput and sustained 60 fps
need further work. Fullscreen requests a 1280x720 surface, with its dimensions carried
by the frame delivery protocol. A media revision reaches the background provider on Reload,
Relink and project open, so unchanged document JSON cannot retain replaced media or LUTs.


## Shared raster and native canvas costs

The actual Genesis painter, including glyphs and monitor scaling at physical client
resolution, was measured separately from worker throughput. Axis-aligned `std.draw`
rectangles now preserve fixed 4x4 coverage without polygon scans. Axis-aligned images
reuse column indices and skip blending opaque pixels. Rotation/skew use the generic paths.
The SDK regression checks 387 rectangle cases and 204 image cases byte for byte.

`std.gui.present_surface` borrows RGBA bytes directly. The host-neutral `ui.present`
contract admits either RGB24 or straight RGBA32; Windows and X11 use the same alpha
rounding. Windows converts to BGRA once before dispatching to Direct2D or GDI.
A headless MSVC regression checks all 65,536 channel/alpha pairs, row order and invalid
buffers. Existing RGB24 callers and non-black alpha compositing remain available.

At a 2560x1440 client size, median full-window CPU painting fell from 214.42 to 54.39 ms
in the supplied 4K clip diagnostic, and an intermediate RGB packing step measured at
23.82 ms was removed. These improvements still do not establish smooth interactive
4K60. `profile-preview` separates the mailbox, image loading, painter and borrowed
handoff. Its serial totals exclude audio, native presentation and asynchronous overlap.
The native window's sustained throughput and long audio runs remain open acceptance work.


## Nonblocking channel dispatch

A half-millisecond `recv_now` deadline became an approximately 11.55 ms Windows
scheduler wait whenever the preview drained an empty command queue. The SDK now
has explicit `net.tcp_accept_now` and `net.tcp_recv_now` operations on POSIX and
Winsock. Not-ready is code 3, preserving the handle; EOF is a successful empty
read. The existing expired-deadline operations still refuse available data.
`std.channel.recv_now` uses the true poll operations while retaining partial
greetings and frame payloads. Credit writes keep their bounded write deadline.

The retained SDK fixture runs through both native and reference backends, and
Windows has headless MSVC byte/EOF/idle-poll checks. Genesis's generation-bearing
profile records queue draining separately from snapshot decode, source monitor,
frame planning, program monitor and pixel publication. Final empty draining is
about 0.03 ms median. At the nonblocking checkpoint (`8203d66`), the editor serial diagnostic was
37.21 ms; fullscreen
is 60.54 ms, of which painting alone is 27.48 ms. These samples exclude audio,
native present and asynchronous overlap. Smooth sustained 4K60 remains acceptance
work. The continuous audio work described below supersedes this checkpoint's
per-chunk filter-state limitation.


## Bounded span copies and opaque row reuse

`array.copy_from` copies a plain-element view into an existing destination range;
`array.copy_within` uses one owner for overlapping ranges. Both retain length and
capacity, validate the complete range before stores, and preserve element bits.
The shared inline `view.slice` body keeps the exported runtime ABI and lets small
constant spans remain constant for the C optimizer. Native/reference tests cover
313 values/ranges, coded type and ownership refusals, and invalid or wrapping spans.

`std.draw` reuses consecutive nearest-neighbor rows only when their valid interior
is wholly opaque. It preserves fractional edge pixels outside the source and
blends transparent rows against each destination background. The independent
oracle now covers 204 image cases over varying background pixels, plus 387 rectangle
cases. Genesis's resampler reserves its byte length once, copies RGB spans and
preserves existing exact-RGBA versus resized-opaque behavior; Windows quadrant
fixtures cover up/down sampling, aspect bars, alpha and refused short/zero inputs.

The opaque-row/span-copy checkpoint (`d5a7d25`) 20-sample profile of the supplied
4K clip at 2560x1440 measured 6.12 ms editor painting and 22.54 ms fullscreen
painting, against 7.10/27.48 ms before this change.
Serial medians are 35.80/56.11 ms. These headless results exclude native presentation,
audio and asynchronous overlap; sustained smooth 4K60 and long-run audio/video
synchronization remain open.


## Retained monitor backgrounds and alpha

Each retained monitor paint restores the panel and picture backgrounds before
compositing its new image. Scanning both input images for alpha, and forcing a
complete window paint when either image is transparent, was therefore redundant.
Genesis now uses the retained path for fixed-size alpha transitions. The pixel
oracle passes 24 cases / 444 checks, including opaque, zero-alpha and mixed-alpha
frame transitions in the editor and both fullscreen monitors at three scales.

The supplied clip's 20-sample headless profile, after three warmups at 2560x1440,
measures 6.00/21.82 ms editor/fullscreen painting and 36.34/55.32 ms serial. These
results exclude native presentation, audio and asynchronous overlap; they do not
establish sustained interactive 4K60 or long-run audio/video synchronization.


## Continuous native playback audio

The previous playback task started a new compositor process for every five-second
WAV. That recreated the decoder, resampler and audio filter graph at each boundary,
resetting delay, modulation and dynamics history. One background owner now retains
the compositor pipe and per-clip graphs across requests. Affine process handles stay
on their creating thread; the window sends atomic snapshots and receives completion
events through a separate `std.channel` link. Seek, source and mix generations reset
the session and refuse stale results. Persisted Stop also closes an idle owner without
a wake. No SDK change was needed for this path.

Active playback previously used a single 120-second reply wait (and 30-second write
wait), so an in-flight decode could delay cancellation despite the idle Stop check.
Playback commands now retain partial pipe progress while checking the committed
request and Stop in 50 ms I/O steps. Their background owner terminates the old child,
closes its handles and removes incomplete output before servicing the next request.
Cancellation does not publish a stale failure. Missing/invalid marker reads instead
report `GA_AUDIO_STREAM_CONTROL`; other reply failures carry `GA_AUDIO_STREAM_REPLY`.

Six native headless cases deliberately block replies or 512 KiB stdin writes during
Stop, seek and a missing-marker fault. They confirm the blocked PID has exited, no
partial WAV remains, and recovered samples equal the normal compositor mix. The
latest run measured 166–169 ms active Stop joins, 315–317 ms seek recovery and
152–169 ms coded marker failure. The full Windows gate passes. This proves active
pipe cancellation; long-run A/V sync remains open. The later bounded reverse checkpoint
below supersedes this checkpoint's source-buffering limit.

`PLAYWAVE` specifies an exact 48 kHz output sample count; `AUDIOSTREAM` pulls from a
retained clip graph. Absolute sequence-frame endpoints determine chunk lengths instead
of rounding each chunk's duration independently. EOF pads the requested output range
with silence. Output windows are bounded to thirty seconds, normally five; FFmpeg's
`areverse` buffered the remaining clip range internally at this checkpoint. The bounded
reverse source path described below replaces it for playback.

The Windows gate compares four direct-worker cases and seventeen editor/source/rate
cases against whole-range WAV output. The generated 48 kHz PCM fixture has zero sample
differences across boundaries, including eleven effects, reverse, 2x speed, seek reset,
source audition and fractional rates. Coded filter failure recovers on a later request,
and idle Stop joins within the bounded test deadline. The supplied 4K clip's AAC track
produced nonzero audio in all seventeen cases; its seek-start comparison had a maximum
892 PCM-unit difference and a mean 3.05 units in signed 16-bit samples. These checks
establish retained processing history, not sample-identical seeking for every codec,
sustained interactive 4K60 or measured long-run A/V synchronization.


## Opaque backgrounds and rectangle interiors

Retained monitor painting restored the complete panel body and then immediately
overwrote its interior with the opaque picture background. It now restores only the
surrounding bands, retaining physical pixel clearing at fractional edges. The picture
background still clears transparent video correctly. The shared `std.draw.fill_rect`
path also reuses its first fully covered opaque interior row through bounded span
copies; fractional edges and transparent rows blend against their own destinations.

The independent polygon oracle passes 387 rectangle checks with different background
colors/alpha per row and column. That exposes an incorrectly copied partial edge.
The image oracle passes 204 checks, native pixel handoff passes all 65,536 channel/alpha
pairs, and the Windows retained painter passes all 24 cases / 444 exact byte checks.
The standard Windows acceptance gate, including continuous audio, passes.

On the supplied 4K/59.94 clip at 2560x1440, twenty headless samples after three warmups
measure 2.52/6.69 ms editor/fullscreen painting, versus the earlier 6.01/21.69 ms
baseline. Panel-band clearing alone measured 5.18/17.62 ms. Final serial medians are
33.28/39.59 ms, versus 40.01/58.37 ms before both changes. Serial request timing also
varied between runs; the isolated paint reduction is 58%/69%. These measurements
exclude native presentation, audio and asynchronous overlap and do not establish
sustained interactive 4K60 or long-run A/V synchronization.

## Export cancellation during process I/O

Export previously checked cancellation between frames while individual worker replies
could wait 120 seconds, writes 30 seconds, and the final child-exit wait 30 seconds.
It now shares the playback command parser and partial-pipe handling, checking export
cancellation in 50 ms I/O steps. Final process waiting also uses bounded steps, and
publication checks cancellation after the worker exits. The creating thread retains
the affine child and explicitly terminates/closes it on every session error before
the caller removes its owned partial output. No SDK change was needed.

The native CLI fault gate stalls OPEN, ENC, AUDIO, CLOSE and exit after a successful
CLOSE reply. Each cancellation must complete within 2.5 seconds, leave the recorded
PID exited, remove partial output and signals, and permit a same-path real export
with six red frames and audible audio. Pre-existing final and foreign partial files
are preserved with coded refusals. The latest full Windows gate measured 108–162 ms
for the five cancellations. These checks exercise pipe and process waits;
CPU-bound frame-plan work and encoder behavior under sustained load need separate
latency measurements.

## Monitor pixels over the task channel

The window now receives monitor pixels through the existing `std.channel` transport.
Four 256 KiB message credits stay within its 1 MiB transport bound. A frame header
declares dimensions, generation and byte counts; bounded reassembly accepts only a
complete matching frame. Source updates have their own retained generation, so
coalescing several program packets before painting cannot lose the source picture.
Unchanged sources skip both the provider read and pixel transfer. Media revision or
dimension changes invalidate that hold. Stop/seek retire a frame while credit waits
retry in 50 ms steps; a slow consumer can resume on the same channel. The file-slot
route remains an explicit headless diagnostic, selected with `--file-pixels`.

Nine native transport cases cover exact largest-preview RGBA bytes, slow consumers,
holding/clearing/coalescing, cancellation during backpressure and coded malformed
frame recovery. Generated-media requests verify independent source/program seeking,
dimension changes, rewind, Reload, a 32-request drag burst, no monitor frame files
and idle Stop. No SDK or compositor change was needed.

Three paired editor runs on the supplied 4K/59.94 AV1/PQ clip use 120 samples after
three warmups, alternating stream/file order at 2560x1440 with 480x270 monitors.
The median of per-run medians falls from 35.28 ms file delivery to 28.58 ms stream
delivery for the serial diagnostic, about 19%. Publication falls from 3.10 to
0.26 ms and image import from 4.10 to 0.07 ms. Program-monitor preparation remains
23.53/23.52 ms and painting 2.50/2.47 ms. Native presentation, audio and overlap
are excluded; sustained smooth 4K60 remains unfinished. Current performance work
targets ordinary editor playback; fullscreen 4K work is deferred at the user's request.

## GPU fitting of completed preview pixels

The program provider previously downloaded the full 1280x720 composition and used
an AIR per-pixel loop to fit it to the ordinary 480x270 monitor. `PREVIEWFIT` now
samples and packs the final GPU buffer to the requested display size before the
download. Composition resolution, spatial effects, final looks, full-precision
`FLOAT` intermediates and `ENC` output keep their existing semantics. The ordinary
program RGBA file falls from 3,686,400 bytes to 518,400 bytes. Each command carries
its own dimensions, so retries and worker restarts need no retained size negotiation.
Cached program files record their actual display size; another size renders again.
Allocation, kernel and read failures report `GA_PREVIEW_GPU_DOWNLOAD`.

`tests/preview_fit.py` compares forty fitted outputs byte-for-byte against the previous
sampling rule using independently fitted legacy full-canvas frames. Landscape,
portrait, odd dimensions, all alpha levels, black bars, a spatial blur and the final
look buffer are covered. Invalid/oversized dimensions are refused, the next valid
command recovers, and `FLOAT` bytes and legacy `PREVIEW` remain unchanged. Native
provider checks refuse enlarging or shrinking a file cached at another display size.

Three paired 120-sample headless editor runs after three warmups on the supplied
4K/59.94 AV1/PQ clip at 2560x1440 have median-of-run-medians of 23.75/21.98 ms
program preparation and 28.83/27.10 ms serial preview before/after GPU fitting,
about 6% overall. Native presentation, audio and overlap are excluded. This does
not establish sustained interactive 4K60 or long-timeline A/V synchronization.

## Audio, scopes and timeline frame identity

Monitor pixel headers now carry the decoded source/program frame positions and media
revision. Monitor timecodes use those completed positions, and the playing timeline
uses the displayed program frame rather than labeling an older picture with a newer
decode request. Paused scrubbing still updates the requested timeline position immediately.
Reload also invalidates queued audio when the document/path has not changed.

Timeline strips have a separate task, channel and provider. Their request signature
ignores transport and selection changes, so thumbnails and waveforms can finish during
playback without interrupting its decoder. Viewport/media/clip changes still invalidate
the request. Bitmap manifests record native source frames; waveform manifests record
source endpoints and length. Both readers and painting reject obsolete mappings after
editing, and a strip slot is reserved before reuse. Native generated-media checks cover
publication during playback, reverse/trim/2x mappings and incomplete-slot preservation.

`tests/frame_identity.py` adds a lossless fixture with a different RGB color on every
frame, independently decoded by FFmpeg before the native application test. Forty-four
source/program picture pairs and their completed frame stamps, and 128 timeline
bitmap surfaces, match independently specified colors and integer frame mappings.
The cases cover 23.976-to-29.97 fps conversion, nonzero clip placement, trim, reverse,
1.25x/0.5x speed and rewind. Scene-only fixtures could miss a one-frame seek error;
this check verifies the actual picture within each scene. It is part of the Windows gate.

The RGB histogram previously painted green and blue bars up to the previous channel's
height, hiding equal-height bins. Independent bars now share one baseline. Native pixel
checks cover all three channels in white/black pictures, a blue program with a red source
and clearing old bins during retained repaint. Frame-stamp checks separate a completed
frame from a newer transport request.

Thirty-three editor audio cases cover all twenty effects and compare chunked PCM with
whole-range output. Additional independent signal checks cover clip/track gain products,
opposite-channel pan silence, mute, solo isolation and embedded video audio. Native
device checks verify stereo, panned and silent meters at its sample cursor. This is
headless processing/device evidence; interactive long-timeline A/V sync remains open.

## Bounded reverse audio source reads

The Windows compositor now reads reverse source PCM in two-second windows, reverses
stereo frames and feeds them to a persistent post-reverse effect graph. It no longer
puts the remaining source range through a buffering `areverse` filter during playback.
Forward playback and the whole-range export path retain their existing decoder graphs.

Each source window includes decoder preroll and resampler overlap. Anchoring those reads
to whole seconds from the clip's first native sample preserves the original resampler
phase. The native duration count follows the pinned [FFmpeg atrim implementation](https://github.com/FFmpeg/FFmpeg/blob/2a571b6068/libavfilter/trim.c),
then accounts for the flushed resampler count. Rounding directly at 48 kHz had shifted
every reversed sample of a fractional 44.1 kHz trim by one sample; the native count fixes it.
Seeking before the window also avoids a compressed packet starting after its trim boundary.

`tests/audio_reverse.py` is part of the Windows gate. Sixty-second and ten-minute PCM
ranges use three unequal pulls and match independent reversed samples exactly. Delay
and 2x/delay retain graph history and match whole-pass output exactly. Three fractional
44.1 kHz trims differ from independent FFmpeg references by at most one signed-16 unit;
a complete twelve-second AAC reversal differs by at most two, mean 0.083449. The supplied
Costa Rica video's twelve-second AAC reversal differs by at most one, mean 0.000013.

One paired ten-minute fixture run measured 160.10 MiB peak worker memory and 172.00 ms
to the first completed PCM file, including process startup. The earlier worker measured
388.60 MiB and 246.48 ms; its sixty-second fixture used 181.70 MiB, while the new worker
used 160.11 MiB. This verifies bounded source buffering on these headless native ranges;
sustained device playback, interactive preview throughput and long-run A/V sync remain open.

## Clip gain automation reaches native audio

Gain keys were serialized by `std.editor`, but the compositor received only one static
clip/track multiplier for each decoded range. The audio-lane K action also refused them.
The application now publishes an optional gain envelope with rounded absolute 48 kHz
sample positions, original clip-local key frames, values and interpolation modes.
The worker evaluates the envelope after audio effects and before track gain, fades and
mixing. It preserves the decoder/effect graph across chunks. Original frame coordinates
retain the pinned `std.curve` Catmull-Rom metric; the remaining ease functions follow the
same SDK formulas. Gain overshoot below zero clamps to zero. No SDK change was needed.

K works on audio and embedded-video clips. Once a gain is keyed, fader edits add or update
the current-time key. Inspector values follow the curve after seeking. Existing-key
interpolation survives an edit, and the whole drag remains one Undo operation.
The SDK's named key evaluator interns its parameter name. The display enters it only
for existing gain keys; the audio planner reads stored names directly. Reading an
unkeyed clip preserves project bytes.
Track gain and audio-filter automation are still unfinished.

`tests/audio_keys.py` checks 45 editor-to-worker cases against independent unkeyed PCM
and 9,276 SDK curve samples, with complete-sample linear checks and exact hold boundaries.
Uneven chunks and whole-range output agree within two signed-16 units through all 38
modes, reverse/rate/effect history, fractional frame rates, nonzero placement, fades,
mute and seeking. Each case round-trips project encoding before rendering. Seven invalid
envelopes report `GA_AUDIO_GAIN_KEYS` and recover without contaminating the next mix.
The generated-media gate measures a 4:1 gain step after MP4/AAC encoding. Native inspector
checks exercise the actual K button and fader drag, curve reading and single-step Undo.
Histogram pixels and per-frame monitor/timeline bitmap acceptance remain in the Windows
gate. These checks do not establish sustained interactive audio/video synchronization.

## Selected-frame Windows readback

The native Windows decoder now checks timestamps before transferring a decoded
picture to CPU memory. Scrubbing, mixed frame rates and speed changes still decode
the necessary source frames, but unused pictures do not cross that boundary.
Selected NV12/P010 pictures use a cached D3D11 staging texture and reusable aligned
AVFrame buffers with libavutil's public uncached-memory copy primitive. Chroma offsets
use the texture's padded height, and visible row widths are checked against its pitch.
Color metadata and the existing FP32 conversion/composition path are preserved.
Other formats and failed staging reads use the ordinary FFmpeg transfer, with
`GA_VIDEO_TRANSFER` marking recovery. `GENESIS_DEFAULT_TRANSFER=1` selects that path
for comparison. No AIR SDK change was required.

`tests/video_transfer.py` compares exact RGBA and float output against the ordinary
transfer and, optionally, a previous worker. Generated H.264/HEVC/AV1 clips use
non-aligned dimensions, B-frame/reordered decoding and fractional timestamps, with
forward skips, final frames, reverse seeks and frame-zero rewind. The supplied
4K/59.94 AV1/PQ clip also passes, including its final frame. Together they pass
332 pixel pairs, including software decode; all four sources use native D3D11 in
this run. The profile logs contain one readback per selected picture, including
requests that skip many source frames. The standard Windows gate includes the
generated cases and reports hardware availability separately from pixel equivalence.

Three paired headless editor runs at 2560x1440, each with three warmups and 120
consecutive sequence frames, compare this worker with `7f0d124`. Median-of-run-medians
are 22.18/19.63 ms for program preparation and 27.22/24.74 ms for the serial preview
path, about 9% less serial work. Native presentation, audio and overlap are excluded;
sustained interactive 4K60 and long-run A/V synchronization remain open.
A one-frame decode/readback-ahead experiment brought no additional measured benefit
and was removed. The retained implementation adds no decode queue or thread.

## Windows audio position formats and continuity

The native adapter formerly refused any driver position other than `TIME_SAMPLES`.
[Windows allows `waveOutGetPosition` to return another format](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutgetposition),
so a working byte- or millisecond-position driver could stop playback with
`GA_AUDIO_CLOCK`. The adapter now converts all three PCM position formats to
48 kHz stereo frames. Native 32-bit ticks are extended before conversion, so a
byte-counter rollover retains its correct frame period. Backward observations
hold the last sample instead of jumping forward by a complete counter epoch.
A reported-unit change reconstructs the nearest epoch at the previous media time;
coarse millisecond observations cannot move time backward. Stop/start clears this
state. Unsupported types and failed driver calls retain coded refusal and do not
modify the last valid position. The AIR-side clock ABI is unchanged.

`tests/audio_clock.cpp` calls the actual native clock/meter ABI with a controlled
position API. Its 61 checks cover sample/byte/millisecond conversion, incomplete
stereo byte counts, three rollover epochs, jitter, changes of units after rollover,
post-mix meter indexing, failure/recovery and restart. Alternate-format hardware
has not been physically tested; those formats have controlled ABI evidence.

`tests/audio_clock.py` measures a real output device with silent, uneven stereo
buffers. The Windows gate runs twenty seconds. A separate 180-second run made
21,574 observations and completed 222 buffers; its post-startup interval drift was
-2.976 ms and its phase range 3.114 ms versus monotonic time. Draining held the
sample cursor and cleared both meters; queueing after a gap resumed at the existing
count, and a new transport began at zero. Final counts were exact on this device.
The test allows fewer than 48 missing samples for a driver reporting whole
milliseconds. This is device-clock evidence, without image presentation or physical
speaker latency. Sustained interactive 4K playback and long-running A/V sync remain
open. No AIR SDK change was needed.

## Pictures prepared against the Windows audio clock

The old window requested the currently heard frame and painted it after the worker
completed, creating a persistent picture delay. The application now snapshots a
future transport position without advancing the authoritative document. Prediction
uses measured request completion with room for the event wait and retained paint;
the time lead is capped at 50 ms and rounded up to an output frame. The worker still
coalesces one latest mailbox. The UI retains at most two complete waiting pictures,
plus sixteen scalar request timings, and releases only the newest picture whose
stamp is due. No decode thread or AIR SDK change was needed.

Paused seeks are immediate. Stable edit identity, media revision, audio epoch,
active monitor and geometry invalidate pending pictures. An older completion within
the same epoch remains valid even when a newer request is outstanding; a completion
from a retired epoch cannot overwrite rewind. The parked Source image survives
retired Program pictures and can be recovered from the channel's cached RGBA bytes.
Histogram input, monitor timecode and playing timeline cursor all use the released
picture. The document continues to track the actual audio device sample count.

`tests/picture_queue.ai` checks bounded buffering, due-time release, skipped due
frames, exact paused requests, invalidation, Source time, fractional rates and end
clamping. Inspector pixel checks prove the histogram does not show a prepared future
picture, then changes with its release and with rewind. Stream checks recover every
RGBA byte of the parked Source after its original image was consumed, and refuse
recovery after an explicit empty Source. Existing individual-frame and timeline
bitmap checks continue to use independent lossless source colors.

The new `profile-playback` diagnostic runs the production preview and audio tasks,
the real Windows device and retained painter without opening a window. The final
track gain of its loaded document copy is zero; media remains decoded and mixed.
`tests/playback_timing.py` independently decodes its generated lossless source and
checks every reported pixel/frame pair, audio clock conversion, playing cursor,
queue bound, lack of early pictures and audio continuity across five-second buffers.
Its TSV captures the clock after painting. Native presentation and physical speaker
latency remain outside this measurement, and sustained interactive 4K60 remains open.

The earlier sleep/poll diagnostic (`--poll`) ran three alternating twenty-second
pairs on the supplied 4K/59.94 AV1/PQ clip. These
measure a median of per-run picture-delay medians of 78.79 ms for the diagnostic
baseline and 26.46 ms with preparation. Picture delivery varies: 28.35–28.65 versus
25.60–28.70 pictures/second in those short runs. One ninety-second pair over the
same starting interval measures 115.45/52.63 ms median delay, 205.12/138.95 ms p95,
and 17.83/20.90 pictures/second. The prepared run observes 5,354 complete clock/
picture/cursor samples with no audio underruns or early pictures. These are silent
real-device and headless-painter measurements, including mixed audio buffers, with
native presentation and speaker latency excluded. They establish less picture delay
on these runs; throughput still varies with the footage and is below 4K60.

## Native playback wait precision

The playback diagnostic now waits for preview-channel activity and repaints only
after clock, picture or meter changes, matching the window's scheduling policy.
The earlier fixed eight-millisecond sleep and unconditional repaint remain
available as `--poll`; their historical throughput is not a measurement of the
window's event loop. Idle channel deadlines preserve partial packets and permit
the next request to recover. The TSV adds worker phase, paint and wait durations
and the active timer request.

The native audio adapter requests `timeBeginPeriod(1)` after successful device
opening. Its noncopyable guard balances each successful request on Stop, restart
or destruction. Device-open failure makes no request; timer refusal preserves
ordinary audio availability. `timer-resolution` reports the current request state
even after Stop. Fourteen additional controlled ABI checks bring the clock/timing
total to 75 and cover acquisition, restart, repeated Stop, refusal, destruction and
recovery. No SDK change was needed.

[Windows documents improved short-wait accuracy from this request](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod),
not improved performance-counter accuracy. Restricting the request to the open
device avoids keeping the finer period while idle. Windows 11 may relax precision
for a minimized or occluded window; this checkpoint does not override that policy.

Three alternating twenty-second pairs on the supplied 4K/59.94 AV1/PQ clip use
an identical diagnostic executable and prepared-picture policy, changing only
the native audio DLL. The median of run p95 waits falls from 20.73 to 9.72 ms;
the median of picture-delay medians falls from 25.36 to 16.89 ms. Picture delivery
is 26.15–32.30 before and 34.35–35.45 pictures/second after. These event-wait
measurements include the real silent device, asynchronous decode/mix and retained
ordinary-editor paint; they exclude native presentation and physical speaker latency.
No run reports an early picture or audio underrun. Results are specific to this
footage and machine and remain below sustained 4K60.
One ninety-second event-wait run after the change observes 8,434 complete clock/
picture/cursor samples with no early pictures or audio underruns. It delivers
26.83 pictures/second, with 28.81 ms median and 93.92 ms p95 picture delay.

The full Windows gate passes, including 75 clock/timing ABI checks, the real device,
all twenty audio effects, post-mix stereo/pan/silent meters, histogram/rewind pixels,
44 source/program frame identities and 128 timeline bitmap identities. The default
eight-second event-wait fixture checks 897 picture/frame/cursor observations with
no early pictures or audio underruns across its five-second PCM boundary.

## Bounded parallel HDR conversion

The native color graph formerly had a fixed four-thread limit. Phase measurements
on the supplied 4K/59.94 AV1/PQ footage showed about fourteen milliseconds in
HDR-to-SDR conversion before upload, compared with roughly two milliseconds for
GPU effects and final publication. The graph now uses the detected logical CPU
count, clamped to one through eight. This increases parallel conversion on larger
machines while bounding its workers and adapting to smaller machines. The color
transform, 16-bit source conversion, FP32 composition and export precision stay
the same. `GENESIS_MEDIA_PROFILE` records the graph limit and detected CPU count.
The setting uses [FFmpeg's filter-graph thread limit](https://ffmpeg.org/doxygen/trunk/structAVFilterGraph.html).

The readback gate now includes generated PQ and HLG P010 clips, with differing
native dimensions and reordered frames. Independent probing checks the encoded
primaries, transfer and matrix; `setparams` also puts those tags on the generated
frames because encoder-only options had dropped their primaries/transfer. Their
diagnostics must show entry into the color graph on hardware and software decode.
A candidate/previous-worker run
with the supplied 4K clip passes 504 exact RGBA/FP32 comparisons through fractional
timestamps, skipped frames, final frames and rewind. The standard Windows gate
passes, including audio, histogram pixels, monitor time/frame identity and actual
timeline bitmaps. The precision suite also retains all 1024 narrow-band values,
100-nit HDR title white, HEVC 10-bit tags, the native 4K 16-bit PQ master, the SDR
preview's mean 0.97/255 difference from the independent floating-point reference,
and audible program audio after 181 seconds.

Three alternating twenty-second native-device playback pairs change only the
worker's thread limit. Delivery rises from 33.40–35.00 to 36.20–37.75 pictures/second;
the median of run picture-delay medians falls from 22.16 to 15.77 ms. One
ninety-second pair delivers 25.01/26.24 pictures/second before/after, with
30.63/29.78 ms median delay and 110.32/95.35 ms p95 delay. All runs report no early
pictures or audio underruns. They include the real silent device, asynchronous
decode/mix and retained ordinary-editor paint, excluding native presentation and
physical speaker latency. The longer result is a modest improvement and does not
establish sustained smooth 4K60. Worker-only conversion timing must not be used
as the editor's delivery rate.

## Reuse the Windows program-picture reader

Splitting provider timing showed that opening each newly written program RGBA
file took a median 4.44 ms in the supplied-media run. Reading its bytes took
0.12 ms and materializing the surface took 0.07 ms. The file-open cost, rather
than the bulk pixel copy, was the next measured avoidable delay.

The provider retains its reader on the preview task's owning thread, rewinds
after the worker's `DONE`, and bounds input to the expected byte count plus one.
The worker's in-place rewrite contract preserves that file identity. Reload,
restart, shutdown and failures close the reader, including a broken-pipe retry
whose replacement worker creates a new output file. `GA_PROGRAM_SIZE` refuses
short, empty and oversized pictures; `GA_PROGRAM_READ` identifies open, seek and
read failures. Existing `fs.seek` and resource ownership suffice; no SDK change
was needed. Twenty-six real-process checks cover new pixel contents, both resize
directions, malformed data, live worker errors, replaced files, broken-pipe
recovery and profile enable/disable/reset.

The diagnostic emits a fresh `provider-profile.tsv` with call identity and
request/reply, reader preparation, byte-read and surface-copy nanoseconds.
`tests/playback_timing.py` validates its rows and reports phase medians/p95.
Ordinary editing does not write this artifact.

Three alternating twenty-second pairs keep the native audio DLL and compositor
fixed. Delivery changes from 47.00–47.35 to 52.05–55.40 pictures/second;
median-of-run program preparation changes from 17.99 to 12.50 ms, and picture
delay from 13.14 to 11.63 ms. Reader preparation measures roughly 0.002 ms.
A ninety-second pair delivers 45.33/53.92 pictures/second before/after, with
13.32/12.07 ms median delay and 31.83/28.18 ms p95 delay. The new run observes
11,530 clock/picture/cursor samples with no early pictures or audio underruns.
These runs use the real silent device, asynchronous decode/mix and ordinary
retained editor paint. Native presentation and physical speaker latency are
excluded, and sustained interactive 4K60 remains open.

The Windows gate retains the audio, meter, histogram/rewind, 44 monitor-frame and
128 timeline-bitmap identity checks. Its eight-second lossless device fixture
checks 957 pixel/frame/cursor observations across a five-second audio boundary.
An additional supplied-HDR check compares Source with a neutral Program at
matched working/monitor sizes: 480x270, 320x180 and the 80x45 thumbnail size.
Through frames 0/1/7/0, all twelve pairs are exact. That confirms the current
shared color path; it required no color fix.

## Preserve small-sequence preview resolution

`configure_preview` previously always filled its 1280x720 bound. A 320x180
sequence therefore passed through a four-times-larger canvas in each dimension
before fitting back to the monitor. Capping the fit factor at one preserves a
small sequence's own pixels and avoids unnecessary scaling and filtering.
Large sequences still use the existing preview bound; export dimensions and
frame/time mapping are unchanged. This uses existing AIR math operations and
requires no SDK or compositor change.

Thirty native assertions cover working/export dimensions and playhead preservation
for six formats, including odd-sized, portrait and 4K sequences. Six whole-image
media comparisons cover 320x180, 321x181 and 180x320, plain and with Blur/Text,
against independently decoded 16-bit FFV1 masters fitted to the monitor. The new
build has at most one 8-bit channel unit of difference. The preceding build fails
the first comparison with maximum difference 43, so the fixture detects the
unnecessary canvas scaling rather than only checking successful replies.

Three alternating eight-second native playback pairs use the same 320x180
lossless 23.976 source in a 29.97 sequence, compositor and audio DLL. The median
of run program-preparation medians falls from 10.10 to 2.39 ms; median picture
delay falls from 19.40 to 15.15 ms. The new runs show 240 pictures each and check
2,933 pixel/frame/cursor observations, with no early pictures or observed audio
underruns. These measurements include asynchronous preparation, the silent
native audio device and ordinary retained editor paint, excluding native
presentation and physical speaker latency. They measure small-project playback
and do not establish a new 4K delivery rate.

The full Windows gate passes, including gain/pan/mute/solo and all twenty audio
effects, post-mix meters, histogram/rewind, 44 monitor pictures and 128 actual
timeline bitmaps. `tests/preview_canvas.py` is included in that gate for future
preview/master comparisons.

## Prepare both sides of a transition and preserve the last audio samples

The frame adapter refused incoming fades/opacity and could apply an outgoing
picture grade to the combined transition. It now resolves each side's picture
effects and clip-local fade/opacity before the transition, using the existing
FP32 intermediate passes. Outgoing fade also runs before upper layers. Titles
are prepared before their clip's fade. The single-wire helper still refuses an
incoming opacity that requires preparation; the complete frame plan supplies it.
Incoming Blend/PiP/Chroma key and upper-lane transitions remain unimplemented.

`tests/transition_clips.py` checks 51 complete preview/master pairs across all
eleven kinds and additional opacity-curve, fade, grade, overlap, gap, title and
upper-layer cases. Non-title pixels agree with independent color/transition
formulas within three channel units; angular threshold ties permit either whole
neighbor color. All pixels, including thresholds and glyphs, agree between preview
and the independently decoded 16-bit FFV1 master within two channel units.
Seventeen master audio streams have exact decoded sample counts and audible PCM.
The prior editor fails the grade case with a maximum difference of 32 units.

That gate also exposed padding in the native encoder's final PCM buffer: a
24-frame / 38400-sample master contained 38912 samples. `fpx_enc_finish` now
uses the real final count when the codec advertises variable frames or a short
last frame, retaining padding for codecs requiring fixed frames. The installed
FFmpeg headers provide these codec capability contracts. No AIR SDK change is
needed; the encoder fix is maintained in `windows/gcompose-windows.patch`.

`tests/audio_export_length.py` checks sixteen exact PCM/FLAC lengths and every
sample around buffer boundaries, including a one-sample output, and four AAC
stream durations. Its input sample count comes from the actual worker accumulator;
the one-frame picture is separate from this encoder-focused duration test.
The preceding worker fails by padding that one-sample PCM output to 1024.
Both media gates are included in `tests/windows.ps1`.
The pro-media gate also requires exactly 9610 decoded PCM samples in the six-frame
3840x2160 ProRes output at 30000/1001, preserving its measured four-pixel detail.

## Share the MM-AIR media runtime and admit native Vulkan decoding

Genesis now reads a three-line location file for the shared MM-AIR codec directory
and existing tools. Its compositor loads the native libraries before binding delayed
imports, with coded runtime/ABI failures. Setup stops copying FFmpeg executables and
DLLs into Genesis. The installed MM-AIR tool is static, so its shared media directory
holds one versioned native library set for library clients. No AIR SDK change is
needed; the application uses existing file, text and process operations.

Native Vulkan decoding uses libavcodec directly, with the hardware pixel format
selected from the chosen device type. It retains the current frame selection and
color pipeline. D3D11 remains the default; the optional Vulkan path passes 504 exact
RGBA/FP32 picture/reference comparisons across generated and supplied HDR media.
Six fresh-process checks prove isolated/Unicode startup without local codec DLLs,
runtime override, and coded failure behavior. Full Windows and professional-media
gates pass with the shared runtime.

The [FFmpeg source and performance investigation](FFMPEG_GPU_PREVIEW.md) records
the tested GPU pipeline, rejected D3D11 resize prototype, current native implementation
and remaining color/scaling work. Raw FFmpeg pipeline speed is not editor delivery:
the current shared-runtime editor diagnostic delivers 53.90 pictures/s in twenty
seconds with no early pictures or observed audio underruns, consistent with the
53.65 baseline. Sustained interactive 4K60 is still open; fullscreen 4K remains deferred.
