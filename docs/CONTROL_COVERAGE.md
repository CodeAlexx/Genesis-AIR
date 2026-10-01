# Control acceptance ledger

The target is every control Genesis AIR currently exposes. All 31 video and 20 audio filter
kinds have a media mapping, but a mapping alone is not control acceptance. A control is
complete when its document edit, saved/reloaded state, preview, export, and failure behavior
agree. The 749-click UI gate proves hit testing and command dispatch in its representative
panel states;
state-dependent controls also need focused checks. It does not by itself prove media output.

## Verified Windows checkpoint (2026-10-01)

Branch `windows-native`, SDK `fe68ba62fd8efceb31ebffc7820f9900113ad41e`, and the
compositor revision/Windows patch recorded in `windows/source-pins.json` and
`windows/gcompose-windows.patch` pass these measured gates:

| Gate | Evidence |
|---|---|
| Project and control model | 152 saved application facts, three native file-drop checks, 749 dispatched clicks across four tabs, no enabled-control overlap |
| Native media and project I/O | Eight cases / 65 checks, Unicode media paths, source/program pixels, native frame units, coded failure exit status |
| Inspector and transport | Twelve cases / 58 checks: real monitor buttons, both scrub bars, fullscreen transport and seeking, lane-area playhead dragging, video/audio lane refusal, file shortcuts, ruler scrubbing, pause during seek, slider clamping/one undo/cancel, disabled filter selection, embedded audio gain/pan and stable mix signature |
| Project safety and recovery | Fifteen cases / 84 checks. Headless input policy checks preserve edits on Cancel, missing/invalid Open and failed Save; Save as completes a deferred action only after publication; native close-request dispatch uses the same policy; paused final edits autosave on an independent timer; atomic failures preserve the prior snapshot and foreign temporary; independent sessions have separate snapshot names; startup skips corrupt records; legacy recovery opens a paused copy; ordinary project files are preserved, including inside the recovery folder; File Recover includes the active snapshot; pending recovery preserves it despite autosave and native path spelling differences |
| Native audio device | Two queued PCM chunks, advancing device sample clock, nonzero post-mix stereo levels, immediate Stop |
| Retained playback painter | Fifteen cases / 282 checks: every RGBA byte matches a complete paint across all four docks at 1x/1.5x/2x scaling, changing pictures and playhead positions, rewind, fullscreen, resize, transport changes, transparent pictures, themes, menus, prompts, keyed inspector values and project-decision/Save as cancellation |
| Native pixel handoff | MSVC headless RGB24/RGBA32 converter: all 65,536 channel/alpha pairs, byte/row order, invalid dimensions and buffer lengths; no GUI opened |
| Asynchronous preview | Generated red/blue pixels after dragging the painted red playhead across lanes; time changes during the drag and the clip track stays intact; the final picture matches a 32-request drag; rewind restores frame-zero pixels; source playback reuses the program picture; actual clip edits invalidate it; actual red/blue thumbnail surfaces are checked both in the mailbox and in painted video-lane pixels; timeline bitmaps and embedded audio waveforms publish independently and wait during playback; fullscreen publishes 1280x720 pixels; replacing a LUT at the same path and requesting Reload changes red program pixels to blue; coded malformed-request and blocked-pixel-publication failures recover on the same worker; a reused image slot refuses its old generation; persisted Stop cancels an idle worker without a wake |
| Generated media | All 11 transition kinds, all 12 blend modes, representative mapped effects, captions, Latin/Cyrillic/CJK text, reverse/speed audio, audio-only projects, worker recovery, progress/cancellation/partial cleanup |
| Sequence/export quality | Six-frame 3840x2160 ProRes preserving four-pixel detail at 30000/1001 with 24-bit PCM; portrait preview square stays square; 1080x1920 H.264/HEVC output; exact held multicam cuts at frames 30/60 |
| Precision/color/audio duration | 1024 distinct narrow-band values survive filtered three-layer FFV1 16-bit composition; a supplied 4K AV1/PQ source round trips into a 16-bit PQ/BT.2020 master; SDR preview agrees with the floating-point reference within mean 0.97/255; 100-nit SDR title white is converted to PQ correctly; HEVC HDR is 10-bit PQ/BT.2020; audio remains audible after 181 seconds |

A 120-sample worker timing check on consecutive frames of the supplied 4K/59.94 AV1/PQ
clip and RTX 5080 measured 59.49 previews/second with D3D11 decode and the NVIDIA OpenCL
device. It excludes mailbox conversion, canvas painting and audio, and does not
establish sustained 60 fps in the window or long-run sync.

The current nonblocking-channel checkpoint headless diagnostic uses 20 samples
after three warmups on the supplied 4K/59.94 AV1/PQ source at 2560x1440. Editor
medians are 27.86 ms request-to-ready, 2.18 ms image loading,
7.10 ms retained paint and 37.21 ms serial. Fullscreen medians are
29.95 ms, 3.14 ms, 27.48 ms and 60.54 ms respectively.
The preceding checkpoint (`25178c9`) measured 37.87/35.72 ms request-to-ready and
46.95/66.54 ms serial in editor/fullscreen. The earlier editor baseline (`40dafe4`)
measured 41.79 ms request-to-ready and 49.91 ms serial. The retained-painter checkpoint
(`77ea56a`) measured 42.23 ms for a complete paint. Native presentation, audio and
overlap are excluded; sustained smooth 4K60 remains open.

Detailed phase timing exposed an 11.55 ms empty wake-coalescing wait. The shared
SDK's `net.tcp_accept_now` / `net.tcp_recv_now` and `std.channel.recv_now` remove
that timed read; the final editor drain is 0.03 ms median. The native and
reference channel suite passes 162 harness checks, with the new three-case /
17-check fixture covering idle polls, binary short reads, EOF, unchanged expired
deadlines and resumable partial greetings/frames. Headless MSVC socket checks
also pass: 32 idle reads take 0.019 ms on this machine. Profile JSON now includes
all seven internal request phases with matching generations and sample counts.

Preview uses bounded `std.channel` command/events and the existing native
`ui.next_event_on` socket/input wait. The request document and geometry are one
atomic snapshot, and two image slots are checked by generation before and after
reading. Request/publication failures carry their generation, allowing the next
valid request to recover. The new wake path passes native headless channel/media
checks; its window interaction has not been re-exercised interactively in this
checkpoint.

The native Windows window was also exercised with the supplied Costa Rica 4K clip:
source/program images, visible transport controls, moving L/R meters, Mute silencing
playback while video continues, and paused program-monitor seeking. This is focused
interactive evidence; it is not a sustained throughput or long-timeline sync measurement.

Use the Windows reproduction commands in [README](../README.md#tests). Historical Unix
X11 tests remain in `tests/window_file_picker.py` and `tests/window_playback.py`.

The new Save/Discard/Cancel and recovery dialogs have headless rendered-image checks and
use the same geometry for painting and pointer dispatch. Their native picker and close
interaction has not received a new interactive Windows check in this checkpoint.

The highest-impact remaining work is continuous playback filter state across audio chunk
boundaries, parameter/animation measurements for mapped effects, nested sequences,
complex-script text, audio automation and measured sustained audio/video synchronization.

## Video filters (31)

| Status | Kinds | Remaining gate or implementation |
|---|---|---|
| Mapped to the worker wire | brightness, contrast, saturation, gamma, hue, sharpen, blur, glow, grain, levels, lift_gamma_gain, rotate, flip, mirror, denoise | Upper-clip brightness now has two- and three-lane preview/MP4 pixel gates proving lower clips stay unchanged. Pixel change and preview/export parity for the remaining parameter values and animation are still required. |
| Mapped with limits | white_balance, vignette, sepia, mono, invert, crop, size_position, chroma_key, opacity, blend, mask, speed, lut3d, text, timer, stabilize | Base and overlay opacity have preview/MP4 pixel gates. White-balance temperature and tint have preview/MP4 color gates, including gain composition with Color Grading. LUT3D accepts a `.cube` path through the filter panel, stores it in revision 2 projects, validates the grid, and has a full-strength preview/MP4 channel-swap gate, a half-mix preview gate, and keyed Amount preview endpoints. Text renders stored content with keyed Size/X/Y, and Timer renders a clip-local timecode with Size; both use TrueType faces through AIR's `std.font` with fallbacks and have generated preview/MP4 gates, including a Latin/Cyrillic/CJK title. A character no installed face covers is refused with its code point. All 12 displayed blend modes have generated formula and preview/MP4 pixel checks. Four independent Crop margins have asymmetric preview/MP4 edge gates. Upper Crop and Mask clear alpha in a per-clip pass, with lower-layer visibility and preview/MP4 gates. Invert, Sepia, and Mono Amount have half-strength preview/MP4 mix gates. Vignette Softness has hard and broad edge preview/MP4 gates. Upper rotation has lower-layer corner and upper-layer center preview/MP4 gates. The centered base mask has feather/invert preview/MP4 center and edge gates. Speed multiplies clip Rate and has a generated 24-to-30 fps, 2x picture/audio/15-frame export gate; animated speed remains unsupported. Stabilize has measured preview/MP4 jump reduction, keyed Strength endpoints, an upper-lane gate, and flat-shot identity. Its local translation window is limited to 24 output pixels; rotation, perspective, and long camera-path smoothing are not implemented. Filter ordering and remaining parameter combinations need media gates. Existing unsupported values fail explicitly. |

## Audio filters (20)

Gain, pan, three-band EQ, ten-band EQ, compressor, gate, normalize, reverb, delay, pitch,
low pass, high pass, tremolo, bass, treble, notch, chorus, flanger, phaser, and limiter
have AIR-to-worker mappings. The real-media suite applies each and checks for audible
output. Tremolo Depth now reaches the exposed 1.0 endpoint; a generated WAV gate
distinguishes it from 0.95. A generated playback WAV gate checks that Pan's -1 and +1
endpoints favor opposite output channels. Other parameter-specific signal measurements,
animated parameters, and long-timeline playback timing remain acceptance work. The
gate's stored `hold` is presented as release time because that is what the worker filter
implements.

## Other exposed controls

| Area | Verified | Still required |
|---|---|---|
| Timeline, pool, tracks, transport, undo/redo | Command/state gate, save/reload, drag undo step; X11 import, V1 placement, ruler scrub, and save at 1× and 4K 2×; generated-media preview/export and X11 Play/Pause for representative cases; all 11 named transition kinds have spatial preview/MP4 gates on touching cuts; overlap and short-gap seams have midpoint crossfade gates; incoming and outgoing Text titles are checked through a crossfade | Media outcomes for every edit operation, nested sequences, non-touching seams for every kind, measured sustained interactive throughput. Incoming transition opacity, fade, and overlay-only effects currently fail explicitly. |
| Project lifecycle | Save/Discard/Cancel for New/Open/Recover/Close, failed-save retry and preservation, isolated history/clipboard, independent paused autosave, separate snapshots, newest-valid and legacy recovery, Save as copy and atomic temporary collision checks | Native picker/modal interaction under an interactive Windows session; recovery ownership across simultaneous running processes. |
| Inspector and keyframes | Representative controls are clicked; focused drag/undo/cancel checks pass; clip-local opacity and brightness keyframes change the render wire; keyed picture fade and base opacity have preview/MP4 pixel gates; LUT3D Amount and Stabilize Strength have keyed preview endpoints; K creates a missing filter in one undo step and refuses known unsupported automation | Full mapped video parameter coverage, remaining keyframed clip properties, unsupported video filter combinations, and audio automation. Per-layer filter support still needs to be reflected at the K action. |
| Subtitles and text | Two timed caption cues, one Latin/Cyrillic/CJK, appear in preview and MP4; Text content, Size/X/Y, and Timer timecode/Size have generated media gates | Complex-script shaping, right-to-left text, richer typography, and subtitle placement. |
| Export and audio | Generated MP4 pixel/audio checks; WAV mix, spaced output path, and X11 audio start/stop | Precise long-timeline audio/video sync, continuous audio-filter state across playback chunks, live scrub sound. |
| Frame rates | AIR editor native-to-sequence bounds, pure-AIR wire sampling, a generated 24-to-30 fps preview/export/audio gate, and a 24 fps sequence preview/9-frame MP4/audio gate | More mixed fractional-rate cases and long-timeline audio sync. |

Keep this ledger with the implementation. Add a measured output assertion when closing a
row; a document mutation or successful worker reply alone is insufficient.
