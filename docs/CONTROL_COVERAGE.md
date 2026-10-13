# Control acceptance ledger

## Current R19 control scope

The target is every exposed control. A mapping or successful command is not
acceptance by itself: document/Undo behavior, saved/reloaded state, evaluated
preview/master output and coded failure behavior must agree. The
[current checkpoint ledger](PRO_EDITING_ACCEPTANCE_WINDOWS.md#r19-checkpoint-status)
records R19's exact combined and native receipts. Its complete BackgroundOnly
suite passes all 92 required fresh reports; native UI checks remain limited to
the explicitly observed workflows. All six native Delay/Reverb export variants
now pass their independent picture/PCM checks. R19 coherent root products are
published and fresh actual-root 4K workflow/module/owned Close verification
passes. The accompanying sanitized archive and verification receipt preserve
the measured workflows and separately scoped history.

| Current control family | Maintained R19 report coverage | Practical limits |
|---|---|---|
| Linked timeline editing and Snap | `linked-media-tests.json`, `editing-safety-tests.json`, `snap-controls-tests.json`, `editor-trim-tests.json`, clipboard/model/media gates; actual paired split/head trim, Undo/Redo, reopen and locked refusal | Native edited effect-tail equality is separately qualified, not inferred from geometry. |
| A1 reference waveform and visible mixer state | `waveform-visual-tests.json`, `waveform-visual.json`, waveform view/detail, direct/nested waveform gates | Reference display neutralizes the owning track mixer only. Mute/Gain 0/Solo exclusion preserve a dimmed labelled shape; actual postmix output still follows mixer state. Cold effects/descendants need background cache work. |
| Follow, marker/time and scopes | `timeline-track-scroll-tests.json`, picture clock/queue, inspector/live-paint and actual cadence gates | Pages from current completed Program pictures. Manual scrolling suspends Follow; Source, gestures and pending endpoint preparation cannot page Program. No physical AV/fullscreen proof. |
| Titles and shared prompts | `inspector-tests.json`, transition controls, current native Unicode edit/Save/Open/title master | Shared caret, selection, multiline editing and visible draft refusals; right-to-left rows and Arabic joining render since R22, while OpenType shaping and richer typography remain incomplete. |
| Keyframes and effect parameters | `keyframe-controls-tests.json`, `keyframe-controls-media.json`, filter order/transactions and evaluated media gates | Previous/Next, exact-key Delete/interpolation, local-frame conversion and one Undo; unsupported audio FX/track automation retain refusals. Not every mapped parameter/order/curve is qualified. |
| Transition management and compositor | `transition-controls-tests.json`, `transition-controls-media-tests.json`, `upper-transition-media.json`, `upper-transition-protocol.json`, picture-memory gates | Stable selected seam badge, 11 types, exact duration, Remove and atomic Undo/Redo. Unsupported direct compound sides, side PiP rotation and base incoming overlay-only edits are refused. No audio fades are synthesized. |
| Save/Open/recovery | Project-safety, recovery-ownership and current native paired/title Save/Open receipts | Actual recovery/failed-save/dirty-close interaction beyond the measured workflows remains separate from model checks. |
| Program/Source transport and accepted EOF | Standalone endpoint actor/controller/media/export/preview, audio EOF query/tail phase/protocol/history and source-boundary gates | Same accepted graph/session, exact PCM count, independent Source, black after video body; restricted DSP domains and actual native tail outputs remain separately scoped. |
| Export ownership and cancellation | Export-ownership and all-phase CLI cancellation checks; actual active native Cancel/same-target retry plus independent all-picture/PCM verifier | Owned cleanup/retry is tested, not a promise of a fixed GUI cancel latency for every frame or codec. Foreign output/partials remain protected. |
| Video/audio filter mappings | 31 video/20 audio mapped kinds with representative current background preview/master/PCM checks | Mapping counts do not qualify every combination, animated field or authored-history transform. |

Normal import/Open separates linked V1 pictures and A1 sound. A1 displays processed
clip audio with its owning track mixer made neutral for reference only; clip
processing and compound child mixing remain represented. `Muted`, `Gain 0`,
`Solo excluded`, `Loading waveform...` and `Unavailable` distinguish actual state
and data availability. A visible shape does not prove audible sound.

Follow in the timeline bar and View menu shares one view toggle. It pages from
completed Program picture/frame identity, aligning ruler, time and marker;
manual horizontal scrolling suspends it. Toggling Follow does not author a
project edit or consume Undo. Actual software steady cadence passes retain raw
inputs/startup/shutdown and do not imply physical scanout or speaker latency.

## Historical control and media catalogue

Everything below records the dated binary/component scopes named in its section.
It is retained for test/control detail, not a statement that an old candidate is
current or that its pending work remains pending in R19. Older counts, throughput
measurements and renderer refusals must be read with their original identities;
current upper-transition/endpoint/reference-waveform behavior is summarized
above. Complete prior candidate documents and failures are retained as described
in the [acceptance history](PRO_EDITING_ACCEPTANCE_WINDOWS.md#retained-history-and-checkpoint-completion).

## Verified Windows checkpoint (2026-10-09)

Branch `windows-native`, SDK `df80f270dd28af76674b6e80a4f08970c081be3e`, and the
compositor revision/Windows patch recorded in `windows/source-pins.json` and
`windows/gcompose-windows.patch` pass these measured gates:

The complete isolated Windows build and gate passed on October 9, including the
native audio clock, real-media preview, HDR GPU conversion, three-minute audio
continuity, keyed video, project recovery, retained painting and all 749 control
clicks. The separate 4K ProRes, portrait, multicam and 16-bit/HDR precision gates
also passed. These checks exclude interactive native presentation and physical
speaker latency; sustained smooth 4K60 remains open.

The October 9 root application SHA-256 was
`9DD7F025134C146080232A633D3E23060CF441A3AC008DF3D32916F6372C577E`;
the worker is `66EE15B507E15EEC67E69999411654C4893A0F9FF3EA8ACCBD1224CC5B62FD9C`.
After the complete combined gate, two additional bounded paint fixes received
the expanded 32-case/656-check native pixel gate and final application smoke.
Its root-file hashes matched the accepted files, and its six shared-runtime process
cases pass. The native playback timing below names its separately measured
application hash; it is not a timing claim for every subsequent build.

| Gate | Evidence |
|---|---|
| Shared MM-AIR media runtime | Six isolated native process cases, delayed DLL imports, Unicode paths, explicit override and coded missing/invalid runtime recovery; Genesis packages no FFmpeg executable or codec DLLs. Optional Vulkan decoding passes 504 exact RGBA/FP32 and software-reference picture pairs across generated NV12/P010/PQ/HLG and the supplied 4K clip, including EOF/rewind. |
| Project and control model | 153 saved application facts, three native file-drop checks, 749 dispatched clicks across four tabs, no enabled-control overlap |
| Native media and project I/O | Ten cases / 105 checks, Unicode media paths, source/program pixels, native frame units, coded failure exit status, every fitted-memory RGBA/alpha byte, rejection of stale signatures, mismatched geometry and truncated buffers, Reload invalidation, and six small/odd/portrait/4K preview canvas formats preserving sequence/export dimensions and time. Actual fitting and letterboxing have separate worker pixel gates. |
| Inspector and transport | Twenty cases / 174 checks: real monitor buttons, both scrub bars, fullscreen transport and seeking, lane-area playhead dragging, video/audio lane refusal, file shortcuts, ruler scrubbing, pause during seek, slider clamping/one undo/cancel, disabled filter selection, embedded audio gain/pan/mute/solo, gain and video K/fader key editing with evaluated readings, unchanged project names during unkeyed gain display/planning, stable mix/strip signatures, equal-height RGB histogram bins, retained program-scope updates and completed-frame monitor/timeline time |
| Project safety and recovery | Sixteen cases / 94 checks, including saved Program/Source In/Out marks and their Undo/Redo. Headless input policy checks preserve edits on Cancel, missing/invalid Open and failed Save; Save as completes a deferred action only after publication; native close-request dispatch uses the same policy; paused final edits autosave on an independent timer; atomic failures preserve the prior snapshot and foreign temporary; independent sessions have separate snapshot names; startup skips corrupt records; legacy recovery opens a paused copy; ordinary project files are preserved, including inside the recovery folder; File Recover includes the active snapshot; pending recovery preserves it despite autosave and native path spelling differences |
| Native audio device | Two queued PCM chunks, advancing device sample clock, nonzero post-mix stereo levels, a panned file with a zero opposite meter, silent PCM with zero meters, immediate Stop |
| Native audio clock and timing | 75 controlled ABI checks cover sample/byte/millisecond driver positions, repeated 32-bit rollover, backward observations, changing units, post-mix meter indexing, coded refusal/recovery and scoped timer lifecycle. Successful device opening requests a one-millisecond timer period; Stop, restart and guard destruction release it. Failed opening makes no request; timer refusal preserves audio availability and is inspectable. The twenty-second silent device gate checks uneven buffers, monotonic position, drained-queue hold, resume and reset. A separate three-minute device run completed 222 buffers with -2.98 ms interval drift and a 3.11 ms phase range versus monotonic time. This excludes picture presentation and physical speaker latency. |
| Continuous playback audio | Four direct-worker and thirty-three editor/source/rate/mixer cases compare concatenated playback chunks against whole-range WAVs. All twenty audio effects, reverse, 2x speed, fractional sample endpoints, seek reset, source audition and embedded video audio are covered. Independent PCM checks verify the clip/track gain product, left/right pan, zero muted output and solo isolation; coded filter failure/recovery and idle Stop without a wake |
| Bounded reverse audio | Sixty-second and ten-minute PCM ranges use unequal output pulls and match independent reversed samples exactly. Peak worker memory stays within a 64 MiB growth allowance as duration increases tenfold. Reverse/delay and reverse/2x/delay retain history and match a whole pass exactly. Three fractional 44.1 kHz trims and a complete twelve-second AAC reversal match independent FFmpeg output within two PCM units and mean below 0.1. A separate supplied Costa Rica AAC check passes the same bound. |
| Clip gain automation | 45 native PCM cases cover all 38 pinned SDK curve modes, reverse, speed, fractional rates, placement, fades, mute, seeks and save/open serialization. Uneven playback chunks match whole-range output within two PCM units. 9,276 SDK oracle samples, every-sample linear checks and exact hold boundaries verify actual gain. Seven malformed envelopes report `GA_AUDIO_GAIN_KEYS` and recover. A generated MP4/AAC output measures a keyed 4:1 step. Track gain remains multiplicative even when the keyed clip's static gain is zero. |
| Active audio cancellation | Six headless native cases: Stop, seek and a missing request marker while a worker stalls a reply or blocks a 512 KiB stdin write; Stop joins without a wake, the old PID is confirmed exited, partial WAVs are removed, recovery matches the normal compositor PCM, and control faults report `GA_AUDIO_STREAM_CONTROL` without poisoning the next request |
| Active export cancellation | Five native CLI cases stall OPEN, ENC, AUDIO, CLOSE and the final child-exit wait; cancellation joins within a 2.5-second test bound, confirms the old PID exited, removes owned partials/signals and permits the same output to export six red frames with audible audio; existing final and foreign partial files are preserved with `GA_EXPORT_EXISTS` / `GA_EXPORT_PARTIAL_EXISTS` |
| Retained playback painter | Twenty-four cases / 444 checks: every RGBA byte matches a complete paint across all four docks at 1x/1.5x/2x scaling, changing pictures and playhead positions, rewind, fullscreen, resize, transport changes, transparent pictures, themes, menus, prompts, keyed inspector values and project-decision/Save as cancellation; nine cases keep image dimensions fixed while transitioning between opaque, zero-alpha and mixed-alpha frames in the editor and both fullscreen monitors at three scales |
| Native pixel handoff | MSVC headless RGB24/RGBA32 converter: all 65,536 channel/alpha pairs, byte/row order, invalid dimensions and buffer lengths; no GUI opened |
| Asynchronous preview | Generated red/blue pixels after dragging the painted red playhead across lanes; time changes during the drag and the clip track stays intact; the final picture matches a 32-request drag; rewind restores frame-zero pixels; source playback reuses the program picture; actual clip edits invalidate it; actual red/blue thumbnail surfaces are checked both in the mailbox and in painted video-lane pixels; the legacy file diagnostic defers its strips during playback; the window uses the separate strip worker below; fullscreen publishes 1280x720 pixels; replacing a LUT at the same path and requesting Reload changes red program pixels to blue; coded malformed-request and blocked-pixel-publication failures recover on the same worker; a reused image slot refuses its old generation; persisted Stop cancels an idle worker without a wake |
| Streamed monitor pixels and timeline bitmaps | Nine headless native transport cases verify every RGBA byte in two 1280x720 images, decoded frame stamps and revision, a consumer paused for 250 ms, source holding/clearing, exact cached-source restoration after image consumption, idle event-wait expiry followed by recovery, and coalescing before the first image is taken, Stop/seek during backpressure, and coded invalid/truncated/oversized/mismatched-frame recovery. Generated-media requests verify source/program colors, held-source preservation, size changes, rewind, Reload, a 32-request drag burst, a separate strip provider publishing actual bitmaps during playback, matching bitmap source frames/colors after reverse/trim/2x rate, stale/incomplete strip refusal, absent monitor mailbox files and idle Stop |
| Generated media | All 11 transition kinds, all 12 blend modes, representative mapped effects, captions, Latin/Cyrillic/CJK text, reverse/speed audio, audio-only projects, worker recovery, progress/cancellation/partial cleanup |
| Audio-timed prepared pictures | Six queue cases / 30 checks cover release time, two-picture bound, coalesced requests, consecutive preparation, paused seeks, retired epochs, edits/geometry, source replacement, Source time and fractional rates. Inspector RGBA pixels verify that a future red frame stays out of the blue histogram, picture/time/cursor/scopes change together when due, and late old black pixels cannot blank frame-zero rewind. The native lossless-fixture run checks every observed picture/frame/cursor pair and the real device clock across mixed-audio boundaries; no early pictures or underruns are accepted. |
| Individual frame identity | A lossless per-frame RGB fixture is independently decoded by FFmpeg. Forty-four source/program picture pairs and completed frame/time positions, and 128 actual timeline bitmap surfaces, match independent colors and integer frame mappings through 23.976-to-29.97 fps conversion, nonzero clip placement, trim, reverse, 1.25x/0.5x speed and rewind. |
| GPU monitor fitting | Forty exact RGBA comparisons against independently fitted full-canvas frames: landscape/portrait/odd sizes, all alpha levels, opaque bars, blur and the final look buffer. Invalid/oversized dimensions are refused, valid commands recover, and full-precision FLOAT/legacy PREVIEW bytes remain unchanged. Native cache checks require the requested display geometry. |
| Windows video readback and color conversion | 504 exact RGBA/float picture pairs with ordinary FFmpeg transfer, software decode and the previous worker. H.264 NV12, HEVC/AV1 P010, generated PQ/HLG P010 and the supplied 4K clip cover padded textures, fractional timestamps, forward skips, final frames and rewind; only selected pictures cross the GPU/CPU boundary. PQ/HLG metadata is independently probed and diagnostics confirm entry into the color graph on hardware and software decode. Its thread limit adapts to available logical CPUs, capped at eight, with color transforms and precision retained. Three 20-second device pairs improve delivery from 33.40–35.00 to 36.20–37.75 pictures/second; a 90-second pair improves 25.01 to 26.24. No early pictures or audio underruns are observed; these headless-painter runs exclude native presentation and do not establish sustained 4K60. Hardware availability is reported independently. |
| Sequence/export quality | Six-frame 3840x2160 ProRes preserving four-pixel detail at 30000/1001 with exactly 9610 samples of 24-bit PCM; portrait preview square stays square; 1080x1920 H.264/HEVC output; exact held multicam cuts at frames 30/60 |
| Small-sequence preview canvas | Six whole-image comparisons at 320x180, 321x181 and 180x320, plain and with Blur/Text, agree with independently decoded native-size 16-bit FFV1 masters after monitor fitting, with maximum channel error of one 8-bit unit. The preceding build fails the first fixture with maximum difference 43. Small sequences now render at their own resolution; larger preview canvases retain the 1280x720 bound. |
| Per-clip transitions | 51 whole-image preview/master comparisons cover all eleven spatial kinds with independently faded sides, plus opacity curves, separate outgoing/incoming grades, overlap, a short gap, titles and an upper layer. Independent transition/color formulas check all non-title master pixels; angular threshold ties accept either adjacent whole color. Complete preview/master agreement includes those threshold pixels. Seventeen master audio streams decode to their exact sample counts and audible PCM. |
| Final export audio samples | Twenty direct encoder cases: sixteen PCM/FLAC outputs preserve every sample and exact lengths of 1, 2, 1023, 1024, 1025, 1600, 9601 and 48001; four AAC outputs retain exact stream durations with audible decode. The preceding worker pads a one-sample PCM output to 1024 samples. Codecs supporting variable or short final frames now receive the real count; fixed-frame-only codecs retain padding. |
| Precision/color/audio duration | 1024 distinct narrow-band values survive filtered three-layer FFV1 16-bit composition; a supplied 4K AV1/PQ source round trips into a 16-bit PQ/BT.2020 master; SDR preview agrees with the floating-point reference within mean 0.97/255; 100-nit SDR title white is converted to PQ correctly; HEVC HDR is 10-bit PQ/BT.2020; audio remains audible after 181 seconds |

A 120-sample worker timing check on consecutive frames of the supplied 4K/59.94 AV1/PQ
clip and RTX 5080 measured 59.49 previews/second with D3D11 decode and the NVIDIA OpenCL
device. It excludes mailbox conversion, canvas painting and audio, and does not
establish sustained 60 fps in the window or long-run sync.

Three paired ordinary-editor runs use 120 samples after three warmups on the supplied
4K/59.94 AV1/PQ source, at 2560x1440 with 480x270 monitor surfaces. Alternating
stream/file order, the median of per-run medians is 28.58/35.28 ms serial, about
19% less work for the pixel stream. Request-to-ready is 25.99/28.90 ms, image import
0.07/4.10 ms, publication 0.26/3.10 ms and painting 2.47/2.50 ms. Program-monitor
preparation remains 23.52/23.53 ms. Native presentation, audio and overlap are
excluded; sustained smooth 4K60 remains open. Fullscreen 4K work is deferred.

The earlier opaque-background checkpoint headless diagnostic uses 20 samples
after three warmups on the supplied 4K/59.94 AV1/PQ source at 2560x1440. Editor
medians are 27.83 ms request-to-ready, 2.41 ms image loading,
2.52 ms retained paint and 33.28 ms serial. Fullscreen medians are
29.97 ms, 3.30 ms, 6.69 ms and 39.59 ms respectively.
The baseline before these changes measured 6.01/21.69 ms painting and 40.01/58.37 ms serial.
Panel bands skip the picture interior that the opaque background overwrites;
shared opaque rectangle interiors reuse a stored row. Fractional edges and alpha
keep independent destination blending. The retained-alpha checkpoint measured
6.00/21.82 ms painting and 36.34/55.32 ms serial.
The opaque-row/span-copy checkpoint (`d5a7d25`) measured 6.12/22.54 ms painting
and 35.80/56.11 ms serial. The retained painter now clears monitor backgrounds
before composition without scanning either image for alpha or forcing transparent
frames through a complete paint.
The preceding checkpoint (`8203d66`) measured 7.10/27.48 ms painting and
37.21/60.54 ms serial in editor/fullscreen. The earlier checkpoint (`25178c9`)
measured 46.95/66.54 ms serial. Native presentation, audio and overlap are excluded;
sustained smooth 4K60 remains open.

Shared span copying passes 313 checks on native and reference backends, including
all legal offsets/counts, both overlap directions, zero-length end positions,
plain records and floating-point bits; wrong types, overlapping owner borrows,
invalid/wrapping ranges and invalid slices fail with coded diagnostics. The native
runtime suite also passes, preserving the exported slice helper ABI. The independent
raster oracle passes 387 rectangle and 204 image checks, including opaque interiors,
fractional edges, reflections, clipping and mixed alpha over varied row backgrounds.
Rectangle backgrounds now vary by both row and column to expose incorrectly copied
partially blended edges. The native retained painter still matches all 444 checks.

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
atomic snapshot. Pixel packets carry decoded frame positions and media revision;
file diagnostics and strip slots check their generation before and after reading. Request/publication failures carry their generation, allowing the next
valid request to recover. The new wake path passes native headless channel/media
checks; its window interaction has not been re-exercised interactively in this
checkpoint.

The native Windows window was also exercised with the supplied Costa Rica 4K clip:
source/program images, visible transport controls, moving L/R meters, Mute silencing
playback while video continues, and paused program-monitor seeking. This is focused
interactive evidence; it is not a sustained throughput or long-timeline sync measurement.

Use the Windows reproduction commands in [README](../README.md#tests). Historical Unix
X11 tests remain in `tests/window_file_picker.py` and `tests/window_playback.py`.

The Save/Discard/Cancel and recovery dialogs have headless rendered-image checks and
use the same geometry for painting and pointer dispatch. An October 10 interactive
Win32 check verifies Cancel before New, native Save as with a Japanese filename,
clean New and native Open restoring the saved gain and pictures. Native recovery,
failed-save and dirty-close interaction remain separate acceptance gaps.

The highest-impact remaining work is sustained playback,
parameter/animation measurements for mapped effects, nested pictures,
complex-script text, track/audio-filter automation and measured sustained audio/video synchronization.

The latest native worker checkpoint retains the audio, histogram and frame-identity
gates above. NV12/P010 readback additionally has 332 exact RGBA/float pixel pairs
against ordinary FFmpeg transfer, software decode and the prior worker, including
the supplied 4K clip's final frame and rewind. Only selected source frames are copied
to CPU memory. Three paired ordinary-editor headless profiles measure 27.22/24.74 ms
serial preparation before/after, about 9% less work; native presentation, audio and
overlap are excluded. Sustained interactive 4K60 remains an acceptance gap.

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

The current diagnostic uses preview-channel events and repaint-on-change; `--poll`
retains the historical sleep/poll mode above. With an identical diagnostic executable
and prepared-picture policy, three alternating twenty-second 4K pairs changing only
the audio DLL measure 20.73/9.72 ms median-of-run p95 waits and 25.36/16.89 ms
median-of-run picture delays before/after the scoped timer request. Delivery is
26.15–32.30/34.35–35.45 pictures/second. All six runs reject early pictures and
audio underruns. These are silent native-device, asynchronous decode/mix and retained
ordinary-editor paint measurements; native display and physical speaker latency are
excluded. The full Windows gate passes, with 897 per-frame identity/clock/cursor
observations in its default eight-second event-wait fixture. Smooth 4K60 remains open.
A separate ninety-second event-wait run observes 8,434 clock/picture/cursor samples,
no early pictures or audio underruns, 26.83 pictures/second and 28.81/93.92 ms
median/p95 picture delay. This uses the same headless scope and exclusions.

The provider now retains its program-picture reader on the owning preview thread.
Twenty-six process/file checks cover changing pixels, both resize directions,
short/empty/oversized refusal, live worker errors, Reload, replaced outputs,
broken-pipe retry, restart and diagnostic session behavior. Reads are bounded to
the exact RGBA size plus one and failures have `GA_PROGRAM_SIZE`/`GA_PROGRAM_READ`
codes. Three paired twenty-second 4K runs improve delivery from 47.00–47.35 to
52.05–55.40 pictures/second, with 17.99/12.50 ms median-of-run program preparation.
A ninety-second pair improves 45.33 to 53.92 pictures/second and 13.32/12.07 ms
median picture delay. The new run checks 11,530 clock/picture/cursor observations
with no early pictures or audio underruns. These silent-device/headless-painter
measurements exclude native display and speaker latency; sustained interactive
4K60 remains open. The current lossless Windows fixture passes 957 independent
pixel/frame/cursor checks, and the monitor/timeline identity checks remain green.

## Video filters (31)

| Status | Kinds | Remaining gate or implementation |
|---|---|---|
| Mapped to the worker wire | brightness, contrast, saturation, gamma, hue, sharpen, blur, glow, grain, levels, lift_gamma_gain, rotate, flip, mirror, denoise | Upper-clip brightness now has two- and three-lane preview/MP4 pixel gates proving lower clips stay unchanged. Pixel change and preview/export parity for the remaining parameter values and animation are still required. |
| Mapped with limits | white_balance, vignette, sepia, mono, invert, crop, size_position, chroma_key, opacity, blend, mask, speed, lut3d, text, timer, stabilize | Base and overlay opacity have preview/MP4 pixel gates. White-balance temperature and tint have preview/MP4 color gates, including gain composition with Color Grading. LUT3D accepts a `.cube` path through the filter panel, stores it in revision 2 projects, validates the grid, and has a full-strength preview/MP4 channel-swap gate, a half-mix preview gate, and keyed Amount preview endpoints. Text renders stored content with keyed Size/X/Y, and Timer renders a clip-local timecode with Size; both use TrueType faces through AIR's `std.font` with fallbacks and have generated preview/MP4 gates, including a Latin/Cyrillic/CJK title. A character no installed face covers is refused with its code point. All 12 displayed blend modes have generated formula and preview/MP4 pixel checks. Four independent Crop margins have asymmetric preview/MP4 edge gates. Upper Crop and Mask clear alpha in a per-clip pass, with lower-layer visibility and preview/MP4 gates. Invert, Sepia, and Mono Amount have half-strength preview/MP4 mix gates. Vignette Softness has hard and broad edge preview/MP4 gates. Upper rotation has lower-layer corner and upper-layer center preview/MP4 gates. The centered base mask has feather/invert preview/MP4 center and edge gates. Speed multiplies clip Rate and has a generated 24-to-30 fps, 2x picture/audio/15-frame export gate; animated speed remains unsupported. Stabilize has measured preview/MP4 jump reduction, keyed Strength endpoints, an upper-lane gate, and flat-shot identity. Its local translation window scales with the canvas up to 96 output pixels at 1 pixel precision (R22); rotation, perspective, and long camera-path smoothing are not implemented. Filter ordering and remaining parameter combinations need media gates. Existing unsupported values fail explicitly. |

## Audio filters (20)

Gain, pan, three-band EQ, ten-band EQ, compressor, gate, normalize, reverb, delay, pitch,
low pass, high pass, tremolo, bass, treble, notch, chorus, flanger, phaser, and limiter
have AIR-to-worker mappings. The real-media suite applies each and checks for audible
output. Tremolo Depth now reaches the exposed 1.0 endpoint; a generated WAV gate
distinguishes it from 0.95. A generated playback WAV gate checks that Pan's -1 and +1
endpoints favor opposite output channels. Other parameter-specific signal measurements,
animated audio-filter parameters remain acceptance work. The
gate's stored `hold` is presented as release time because that is what the worker filter
implements.

Playback now retains each clip's native decoder, resampler and effect graph across
five-second device buffers. The continuous-audio gate compares all twenty effects
with whole-range output and checks reverse, speed, seek/reset, source audition
and fractional-rate sample counts. Generated PCM samples match exactly; this is
headless processing evidence, not a new interactive playback or long-run A/V sync check.
In-flight pipe waits now check Stop/new requests in 50 ms steps. Six stalled-process
cases passed with active Stop joins at 166–169 ms and seek recovery at 315–317 ms;
missing-marker failures appeared at 152–169 ms and then recovered. These timings
include actual process shutdown and recovery, without GUI/device output.
The earlier supplied 4K clip check produced nonzero AAC output in seventeen cases;
its seek-start decoder output differs slightly from the whole-range reference.
Reverse source PCM now uses two-second decode windows with preroll around seams;
post-reverse effect graphs remain continuous. Native sample-rate rounding and whole-second
resampler anchors preserve fractional trim alignment. The ten-minute generated fixture
used 160.10 MiB peak worker memory and 172.00 ms first-buffer preparation versus
388.60 MiB and 246.48 ms in the earlier worker, in one paired headless run. Long interactive
playback and A/V synchronization remain unmeasured.

The extended 180-second fractional-rate device/painter gate checks 20,661 exact
picture/frame/cursor/audio conversions and 36 production buffer boundaries.
It observes 5,395 pictures, no drained queues or early pictures and -3.00 ms
device-clock drift over 178.99 seconds. These are silent native-device and
retained-painter results; native display and physical speaker latency are excluded.

The D3D11 HDR preview gate additionally checks 512 color-patch samples, eight
whole-image PQ range excursions, selected preview-sized GPU readbacks,
seek/EOF/rewind, finite opaque pixels and exact native-size/HDR master fallback.
Preview spatial resampling differs at edges; master transforms retain the reference.

## Other exposed controls

| Area | Verified | Still required |
|---|---|---|
| Timeline, pool, tracks, transport, undo/redo | Command/state gate, save/reload, drag undo step; X11 import, V1 placement, ruler scrub, and save at 1× and 4K 2×; generated-media preview/export and X11 Play/Pause for representative cases; all 11 named transition kinds have spatial preview/MP4 gates on touching cuts; overlap and short-gap seams have crossfade gates; incoming/outgoing Text, opacity keys, fades and independent grades have native preview/master pixel checks | Media outcomes for every edit operation, nested sequences, non-touching seams for every kind, measured sustained interactive throughput. The historical checkpoint refused incoming Blend/PiP/Chroma key and upper transitions; later maintained upper-side support is scoped above. Incoming overlay-only base-transition edits remain refused. |
| Project lifecycle | Save/Discard/Cancel for New/Open/Recover/Close, failed-save retry and preservation, isolated history/clipboard, independent paused autosave, separate snapshots, newest-valid and legacy recovery, Save as copy and atomic temporary collision checks; Win32 Cancel/New and Unicode Save as/Open; actual simultaneous-process lock, crash, claim-race and failed-cleanup checks on Windows/Linux | Native recovery, failed-save and dirty-close interaction under an interactive Windows session. |
| Inspector and keyframes | Representative controls are clicked; focused drag/undo/cancel checks pass; clip-local opacity and brightness keyframes change the render wire; keyed picture fade and base opacity have preview/MP4 pixel gates; LUT3D Amount and Stabilize Strength have keyed preview endpoints; K creates a missing filter in one undo step; audio gain K/faders write local keys, show evaluated values and undo a drag together; gain curves have native PCM/AAC output gates | Full mapped video parameter coverage, remaining keyframed clip properties, unsupported video filter combinations, and track/audio-filter automation. K/faders now refuse unsupported PiP/Blend/Chroma-key layers and transition sides, unknown fields, unsupported rotation and stale filter targets with codes. Keyed video faders display/edit evaluated values; held Blend mode switches are exact. |
| Subtitles and text | Two timed caption cues, one Latin/Cyrillic/CJK, appear in preview and MP4; Text content, Size/X/Y, and Timer timecode/Size have generated media gates | Complex-script shaping, right-to-left text, richer typography, and subtitle placement. |
| Export and audio | Generated MP4 pixel/audio checks; WAV mix, spaced output path, X11 audio start/stop, continuous native playback decoder/filter history and bounded long reverse buffering with fractional-resample/AAC reference checks | Interactive native-display/speaker synchronization, sustained device playback of larger reversed projects, live scrub sound. A 180-second headless device/picture fixture now checks unique frame identities, 36 buffer boundaries and clock drift; 181-second fractional resample/filter/gain processing is bit-identical across 37 pulls and a resumed seek. |
| Frame rates | AIR editor native-to-sequence bounds, pure-AIR wire sampling, a generated 24-to-30 fps preview/export/audio gate, and a 24 fps sequence preview/9-frame MP4/audio gate | More mixed fractional-rate cases and long-timeline audio sync. |

Keep this ledger with the implementation. Add a measured output assertion when closing a
row; a document mutation or successful worker reply alone is insufficient.

## Additional Windows candidate acceptance on 2026-10-09

The native window opens the supplied 4K AV1/PQ project, updates paused pictures and
timecodes from the ruler, and rewinds to a visible frame zero. Live stereo meters,
filmstrip bitmaps, histogram, spatial RGB parade and luma waveform were observed.
Scopes describe the displayed SDR preview, including horizontal sample positions.
The final native Audio-tab interval delivers 56.76 changed pictures/s over 79.20
seconds, with 1.42 ms median painting and no observed drained audio queues.
Sustained 4K60 remains open; fullscreen 4K remains deferred.
See [native timing](FFMPEG_GPU_PREVIEW.md#native-window-measurements-on-2026-10-09).

Independent native 16-bit pixel checks establish ordered picture operators,
duplicates, unclipped float intermediates, title/grade order and four simultaneous
camera titles. Each duplicate picture filter has its own animation keys;
qualified keys take precedence over legacy kind keys, and the first edit migrates
the selected instance's legacy curve. Inspector checks cover the selected instance,
Save/Open and Undo/Redo. Transport/composition controls remain separate from the
ordered picture passes; arbitrary interleaving and duplicate composition semantics
are not established. Complex 4K effect-stack throughput is unmeasured.

Refused source Insert/Overwrite preserves document bytes, selection, semantic
revision and every undo/redo snapshot. Legal edits remain reversible. Program and
Source In/Out marks now create saved edits with history; repeated identical marks
create no extra history step. The project-safety gate has 16 cases and 94 checks.
Retained painting matches complete painting in 32 cases/656 checks, including held
Source pixels, transparent same-size replacement, resize at all three UI scales,
scrolled unkeyed Audio meters, and narrow/short windows. Two added cases exposed
status erasure crossing a track header and timecode glyphs escaping the narrow
monitor's redraw band; both boundaries are fixed without pixel tolerances.

## Additional acceptance on 2026-10-10

The shared trim/Split overlay passes six cases/33,371 retained-source, key-curve,
fade, bounds and atomic-refusal checks in Windows native, Linux native and the
AIR interpreter. The cache/Split suite now passes eight cases/2,517 checks.
Ten application trim-history cases/187 checks establish exact refusal and
clamped-no-op preservation, single capture, and byte-exact Undo/Redo.

The pixel transport has ten synthetic native cases. Its added failure case checks
25 outcomes on real channel events: retired epochs, Stop/restart, the same error
code at different generations, current-error pause and valid pixel recovery.
The producer checks the committed request marker after decoding; the presenter
checks the freshly configured request range before applying an error. An old
decode failure cannot pause newly restarted playback. A current failure pauses
and suppresses that iteration's next frame request.

Native queue tests pass nine cases/77 checks. The supplied 4K/59.94 source now
delivers 59.87 distinct pictures/s over 131.88 seconds in the ordinary maximized
Audio-tab editor, with eight skipped positions and continuous queued stereo
audio. Median/p95 after-presentation lateness remains 16.68/33.37 ms. These
measurements use fitted monitors and exclude physical display/speaker latency;
fullscreen 4K remains deferred. See the [full timing and loss
attribution](FFMPEG_GPU_PREVIEW.md#native-window-recovery-on-2026-10-10).

The published October 10 application also passed an interactive Win32 project
workflow using an isolated copy of the supplied project. A gain edit from 1.00
to 1.05 opened Save/Discard/Cancel before New; Escape kept the clip and gain.
Ctrl+Shift+S opened the native Save project picker and saved a filename containing
spaces and Japanese characters. New then opened a clean project, and Ctrl+O's
native picker reopened the saved copy with its 1.05 gain, Source/Program pictures
and timeline bitmaps. Independently reading the saved JSON confirmed the gain;
hashes confirmed both the original and working project were unchanged. This
closes the ordinary native picker/modal interaction gap, rather than proving
multi-process recovery ownership. The sanitized receipt is
`archive/native-project-lifecycle-2026-10-10.json` and names the checked application.

## Concurrent sessions and transition fidelity on 2026-10-10

Recovery now retains stable sidecar locks through atomic snapshot replacement.
Actual process tests pass 70 Windows checks and 74 Linux checks: live-owner
refusal preserves document and all history, forced exit releases the lock,
competing orphan claims have one winner, and Save-before-own-Recover transfers
the existing handle. Ordinary project files create no sidecars. Failed deletion
retains its owned path and lock; Recover refuses installation with
`GA_RECOVERY_CLEAR` until cleanup can succeed, preserving native alias spelling
on refusal. The Linux run independently checks two case-distinct snapshot paths.
Startup resolves relative state directories before constructing the application;
absolute native-picker paths still identify live owners and refuse recovery.
Drive-rooted Windows paths resolve against the current drive; ambiguous
drive-relative paths and unavailable working directories report `GA_STATE_ROOT`.

Two concurrent native media workers pass three rounds each, with six decoded
pictures, six cache reads and six 9,600-frame stereo mixes checked against
independent 440/880 Hz tone oracles. Preview/audio/strip resets and export
cancellation remain private; shared settings, diagnostics and foreign recovery
bytes stay intact. Caller-owned session reports are exclusive and refuse reuse.
Retired private media directories currently remain for artifact inspection;
automatic storage cleanup is still unfinished.

Thirty-four whole-monitor comparisons against independently decoded native
16-bit FFV1 masters pass with maximum error 1/255. They cover all eleven
transition kinds in 4K landscape and portrait, with extra progress positions
for iris, clock and barn-door masks. The former 22-case baseline fails 17
comparisons. A four-case/107-check canvas gate verifies exact seam boundaries,
hidden/inactive/audio lanes, portrait, small/odd sequences and unknown-kind
refusal. Spatial seams use native sequence pixels; surrounding and pointwise
frames retain fitted canvases. Native 4K seam throughput is unmeasured.
Two persistent stream cases additionally reuse one immutable snapshot through
seven frame commands each, including seam exit and reentry. Actual worker launch
receipts show fitted/native/fitted/native/fitted dimensions; all 14 delivered
RGB pictures match independently decoded native masters within 1/255. Encoded
FFV1 RGB does not establish monitor alpha equivalence.

The combined Windows gate passed with 749 control outcomes, both concurrent
process gates, long audio/clock checks, HDR/readback and cancellation in all five
worker phases (140–174 ms). The root application SHA-256 is
`2A7872B732249F09391292016FA00DB0238C851002D30BC780709B03245FF6BF`;
the unchanged worker is
`66EE15B507E15EEC67E69999411654C4893A0F9FF3EA8ACCBD1224CC5B62FD9C`.
This build reuses MM-AIR's media runtime.

An interactive check of this exact root build used a relative state directory
and recovered an isolated snapshot of the supplied project. It restored gain
1.05, both pictures and timeline filmstrip. Playback advanced with active stereo
output meters; Stop paused, and Start returned a visible first frame. Ruler
scrubbing selected the snake at `00:00:07:14`, changing the histogram, RGB parade
and luma waveform. The native Save picker wrote a separate Unicode filename;
independent JSON/hash checks confirmed gain 1.05, cleanup of owned recovery
records and no change to the original project. The receipt is
`archive/native-session-ui-2026-10-10.json`. This proves interactive correctness;
the earlier sustained timing measurement belongs to its separately named build.

The broader generated-media workflow also passed on the same application and
worker with Windows Segoe UI and Noto Sans JP fallback. Its final invalid audio
filter case requires both `GA_EXPORT_WORKER` and `GA_AUDIO_RENDER_FILTER`, a
nonzero exit and no output file. The prior text-only error assertion was stale.
The sanitized 41-entry source/acceptance archive is
`archive/session-safety-transitions-2026-10-10.tar.gz`, SHA-256
`df0d1ea540f9c6d1fb1431b0c3897e4d82a17935b3e46909647a0e339ed1dbc0`.
It includes numeric process/pixel evidence, the exact native UI receipt and the
separate overlap-audio defect reproduction. It contains no executables or media.

## Overlapping audio headroom on 2026-10-10

The mixer now sums signed clip contributions with float headroom and applies
one common hard limiter at final output. Playback WAV, the encoder, peak/RMS
meters, spectrum and oscilloscope consume that same limited signal. Encoding
uses at most 24,000 temporary floats (96 KB) per chunk. The wire protocol and
static gain/fade behavior are unchanged.

An independently authored stereo-float gate passes 14 cases/112 checks and 688
worker commands. All 1,501,892 PCM16 values match the mathematical sum exactly
across whole renders, three uneven retained chunks and fresh seeks. PCM24 export
differs by at most `1.1921e-7`; floating-point export by `9.0898e-8`. It checks all
six signed overlap orders, positive/negative overload, gain/pan, asymmetric
channels and a clipped sine. Independent peak/RMS, oscilloscope and selected
direct-DFT spectrum checks agree with final output. Float export explicitly
tests the encoder path that integer conversion could otherwise mask. The old
worker fails 24 checks. Both gates explicitly reject non-finite decoded samples.

Twelve additional saved-project cases exercise the actual application through
audition and lossless export: six storage orders, track gain/mute/solo, clip
gain, playhead seek and signed overload. Source and saved-project bytes remain
unchanged. The combined Windows suite and broader generated-media workflow
also pass on the new worker, retaining 749 control outcomes, HDR/readback,
spatial transitions, continuous/reverse audio and five-phase export cancellation.
Cancellation took 139–176 ms with worker exit, partial cleanup and audible
same-path retries. Finite-output assertions were strengthened after the combined
run; both new audio gates were rerun successfully against the unchanged worker.

The published worker SHA-256 is
`6AD0AB8B6D818CF32D51070D03F4C30B4FBC07A18C4CE71166BFE938E2CFEE19`;
the application remains `2A7872B7…`. A fresh native editor process and all three
descendant compositors were checked against those hashes. The supplied video
played with advancing pictures/time and active stereo meters; Stop, visible
rewind, scrubbing, histogram, RGB parade and luma waveform passed again. The
original project hash stayed unchanged. This is an interactive correctness
check, with no new sustained cadence or physical speaker/display latency claim.
See `archive/native-audio-headroom-ui-2026-10-10.json`.

The maintained overlay applies and reverses against the pinned donor; the local
canonical Rust source was migrated with exact old/new hash guards, preserving
all other source bytes. MM-AIR's existing media runtime is reused. The sanitized
14-entry archive `archive/audio-headroom-2026-10-10.tar.gz` has SHA-256
`2658ef022b1b0e8943ba7f848b02634d89c9aae63c262dc9310e07a2e619d711`.

The separate audit reproduced ignored audio fade keys and omitted nested audio
on the earlier worker. Those planning paths remain unchanged by this mixer fix.
At that headroom checkpoint, fade controls/audio automation and explicit nested-audio
handling were still open. It does not establish complete professional editing acceptance.

## Clip fade controls and audio on 2026-10-10

Fade in/out now display their evaluated values and support K on audio and video
lanes. After the first key, a fader writes a clip-local key at the playhead,
preserving an existing key's interpolation. Unkeyed scalar editing retains its
prior behavior. New fader writes must be finite and nonnegative; saved signed
knots remain part of the raw curve, and negative evaluated lengths clamp to zero.

Audio evaluates raw fade lengths in sequence-frame units at each destination
sample using the 38 pinned SDK curve modes, then converts the result to seconds.
The separate fade-in and fade-out ramps multiply each other and gain, preserving
the authored scalar audio convention. Picture opacity uses the smaller fade ramp.
Surrounding signed and off-body keys remain part of interpolation after a seek.
Animated fade trims and Split still refuse unsupported context with `GA_TRIM_CONTEXT`
or `GA_SPLIT_CONTEXT`; this stage does not relax those safeguards.

| Gate | Accepted evidence |
|---|---|
| Fade controls | Ten cases / 128 checks in Windows and Linux native fixtures: evaluated readings, an actual audio Fade K click, existing interpolation, signed surrounding knots, clip-local writes, a multi-move pointer drag in one Undo, Escape cancellation, save/open, and complete document/history/Redo/revision/selection preservation on refusal. Invalid values, missing/stale targets, out-of-clip pointer clicks, malformed either-side curves, invalid frame rates, sample collisions and frame/count bounds are checked. A 65,536-key curve permits replacement but refuses insertion. A fade-only write invalidates the audio signature; Undo restores it exactly and picture-only automation preserves it. |
| Fade PCM and SDK curves | 49 native cases compare every intended stereo sample of whole WAV, uneven retained chunks and fresh seek output against independent ramps and 2,829,783 SDK sample values. All 38 interpolation modes, raw signed Catmull context, off-body knots, source trim/reverse/2x, 59.94 fps placement/seek, overlap, gain multiplication, zero lengths and scalar fallback are covered. There are 2,350 integer checks against `editor.clip_value_at`; PCM differs by at most two signed-16 units. |
| Fade refusal/recovery | 32 malformed worker requests report the expected fade/gain code. Both token orders agree; zero frames and an overflowing final sample are refused, while the exact final sample bound is accepted. A primed changing source checks retained decoder continuation after invalid requests against an unaffected state and a fresh reference. |
| Saved-project audition and export | Seven independently authored linear/hold cases check every audition WAV and independently decoded lossless-master sample, with exact intended lengths and finite master values. Three AAC amplitude windows verify the held fade-length change. Sources and authored saved-project bytes remain unchanged. |

Whole-WAV and master allocation use the ceiling of range duration in 48 kHz samples, while
retained chunk lengths use differences of rounded absolute endpoints. The PCM gate
allows at most one extra stereo sample frame in the whole WAV and requires that
frame to be silent. It compares every intended sample rather than trimming a
larger unexplained length difference.

Fresh-seek fade comparisons use independently requested unkeyed PCM to isolate
source decoding/resampling/rate/reverse from destination-envelope timing. They
catch retained decoder drift but do not independently establish the authored
source phase for every codec. The independently authored constant-source project
oracle establishes fade/gain amplitude and timing rather than source phase.
These new gates make no sound-device timing, physical hearing or sustained native
presentation claim. The earlier native playback measurements retain their own
build hashes and scope.

The complete combined Windows suite passed, including the 749 control outcomes,
long fractional-rate/reverse audio, cancellation, project recovery and the new
fade gates. The broader generated-media workflow also passed. Native UI validation
with the supplied 4K video verified active stereo meters, Stop, visible frame-zero
rewind, timeline filmstrip, and scrub picture/time/scopes agreement. At frame 60,
the keyed Fade controls showed 150/30; a fader edit saved a frame-local value of
151 with interpolation 2, and Undo restored the value and key count. The original
project bytes remained unchanged; Genesis was left paused at frame zero.

At this fade checkpoint, the installed application had SHA-256
`7ebfe8eb2ddebf3ad15090e1baeaab37df7d92905e7960f79627f4df5a4f13f5`;
the installed worker was
`a98f186ca7fb872c6a4c113510f3b8728d3b85df80149b732adeca8a455edd9b`.
The canonical worker migration preserved the other six source files and passed
the maintained overlay reverse check. The 27-entry sanitized acceptance bundle
[`archive/audio-fade-2026-10-10.tar.gz`](../archive/audio-fade-2026-10-10.tar.gz)
has SHA-256 `fcd57f506a3d03e366b0baa67ecc87775e073aa819e46c24b98bbe8958b4e5df`.
The [native UI receipt](../archive/native-audio-fade-ui-2026-10-10.json) records
the observed values and original-project hashes. The earlier app/worker fail the
same saved-project fade test with a 7,200-unit PCM error; that baseline is archived.
MM-AIR's shared media runtime is reused, with no separate Genesis FFmpeg bundle.
At this fade checkpoint, nested sequence audio could still be silently omitted;
explicit refusal and recursive mixing remained open. The later nested-audio stage
below addresses that omission. The fade checkpoint does not establish complete
professional editing acceptance.

## Recursive nested audio on 2026-10-10

Nested audio now sums each child sequence before applying its enclosing clip's
pan and static audio filter chain, then parent gain and fade envelopes. Float
headroom survives every intermediate bus; final output applies the existing
limiter. Parent mute/solo and child mute/solo are evaluated in their own sequences.
Nested `source_in` uses the owner's frame units, while child placement and
automation use the child's frame rate. Reverse and speed act on the selected
child span without flattening child automation into a parent curve.

Each placed instance builds private IEEE-float RF64 caches for complete decoder
and DSP history. Child DSP precedes selection and retiming; parent DSP follows
the child sum. Uneven chunks and fresh seeks read exact absolute sample slices
from that history. Program playback, audition and export use the same recursive
plan. A descendant audio change invalidates its root signature; picture-only keys
leave the signature unchanged. Valid empty child sequences produce zeros through
the parent chain. Missing sequences and cycles are coded failures.

| Gate | Accepted evidence |
|---|---|
| Authored nested projects | 18 independently authored projects compare every intended audition WAV, independently decoded lossless master, native whole WAV, uneven retained chunk and fresh-seek sample. Cases cover child sums; parent/child gain, mute and solo; nonlinear parent compression on the sum; unclipped intermediate `1.6 × 0.5 = 0.8`; repeated child instances with separate DSP state; source trim, owner/child fps including 59.94/24 fps, reverse and 2x; child/parent gain and fade automation; two-level recursion; empty-child silence and recovery. The independent compressor oracle separates parent-on-sum from per-leaf filtering by 0.1783. Sources and authored saved-project bytes remain unchanged. |
| Model and encoded audio | Child gain keys change the recursive signature; Undo restores document and signature exactly, Redo restores the keys, save/open preserves both, and a picture-only key leaves audio unchanged. Four AAC amplitude windows verify the child held-gain change against independent authored PCM and a lossless master. All decoded float values must be finite. |
| Refusal and transaction safety | Seven saved-project cases check cycle, missing sequence, missing online child source, six-hour span, depth, instance count and prospective disk limits. Audition/export report the expected `GA_AUDIO_NESTED_*` code, publish no output or partial, leave no owned cache and preserve project bytes. Five direct malformed worker transactions preserve the accepted cache. Separate capacity probes refuse both prospective and old-plus-replacement cache overflow before writing. |
| Real warm cancellation | Two cases use an actual 30-minute sparse PCM source and compressor DSP, observing RF64 stage writes before cancellation. Stop/discard acknowledges in about 151 ms and a fresh Play succeeds in the same background owner; active task shutdown joins in about 158 ms, followed by a fresh owner/request. Both stay within the 2.5-second bound, confirm the exact observed worker identity exited, remove owned caches/partials and check every fresh short PCM sample. Source/project bytes remain unchanged. No fake stalled worker is used. |
| RF64 and retained history | Direct worker checks preserve float headroom, match whole/chunk/seek PCM exactly, handle empty buses and clean float files on normal exit. A sparse RF64 source declaring more than 4 GiB of data verifies the 64-bit size path and exact bounded PCM read. |

The planner bounds depth to 16, instances to 4,096 and source/output spans to
six hours. Prospective float storage per worker is capped at 32 GiB, including an accepted
cache and its replacement. The app also bounds descriptor expansion to 960,000
bytes before the one-MiB playback mailbox; the worker has its own 32-MiB descriptor
bound. Planner structural refusal precedes worker/cache creation and export encoding.
Runtime decode failures report `GA_AUDIO_NESTED_RENDER`; malformed descriptors,
ordering, cycles, capacity and ownership/cleanup failures have separate codes.
Workers exit before caller-owned flat caches are removed. An unconfirmed exit or
failed deletion reports `GA_AUDIO_NESTED_CACHE` and retains ownership for diagnosis.

Full-history warming can delay the first chunk and requires disk space proportional
to duration and placed instances. The native headless 300-second supplied-source
probe measured 0.635 seconds to the first forward/fresh-seek chunk, about 0.48 ms
median warm 50 ms pulls and about 346 MB of float caches. A changed root rebuilt
in about 0.534 seconds. Reverse first-chunk preparation took about 0.750 seconds.
The source bytes stayed unchanged and tested slices matched reference PCM exactly.
OS file caching was warm, native OpenCL initialization was included and root Windows
acceptance ran concurrently. These measurements exclude GUI presentation, audio
devices, speaker latency and sustained playback cadence; preparation stays in the
background audio owner.

The older fade checkpoint's omission is independently reproduced: a saved project
with direct 440 Hz and nested 880 Hz audio rendered only the direct tone, while a
nested-only project failed audition as having no audible audio. The new authored
gate checks actual recursive output instead of accepting a successful reply.
MM-AIR's shared codec runtime remains reused; Genesis adds no separate FFmpeg bundle.

The final combined Windows suite passed the existing 749 control outcomes and
media/project gates, the 18 nested projects, seven refusals, four AAC windows,
real warm cancellation, and the new five-case/43-check nested Audio-panel gate.
That panel finds sound on the requested track's owner and keeps parent and selected
clip controls editable when descendants are muted, disabled or offline. Cycle,
16/17-depth and 4,096/4,097-visit boundaries are covered on Windows and Linux.
The broader generated-media workflow passed preview/master comparisons, titles,
all transition kinds, encoded audio, cancellation and shared-worker recovery.
It used the shipping Windows font defaults and bundled Japanese fallback without
changing any image threshold.

The native window exercised a 30-second nested AAC compound and a separate flat
video track from the supplied 4K/59.94 AV1/PQ source. Stereo meters were active
during Play and restarted after Stop; Stop paused the picture and cleared the
meters. Parent Gain changed 1.00 to 0.95, Pan changed 0.00 to 0.05, Mute and Solo
toggled, and Undo restored each value. Rewind returned to a visible frame zero.
Scrubbing showed matching playhead/program times at 00:00:05:04 and 00:00:09:04,
corresponding filmstrip scenes, and changed histogram/parade/luma displays.
Only the private QA copy was saved; the original project and video hashes remained
unchanged. The [native UI receipt](../archive/native-audio-nested-ui-2026-10-10.json)
records this scope. It adds no sustained cadence or physical-hearing claim.

The installed app SHA-256 is
`07334d3b14302cdb67688df1f4e6f1c9d00e94c90644f6d3be187a856b1417bd`;
the worker is
`26ae94ea70ca67ec855af58a490e21a27fd7eff119f42d240d23ed793a6ad397`.
Canonical worker migration preserved the other six source files and passed the
maintained overlay reverse check. The 36-entry
[sanitized acceptance bundle](../archive/audio-nested-2026-10-10.tar.gz) has SHA-256
`f5340dac1e587fe3d8f83087a9c5ea7bb47f1bd81a71da36a88c31c4b20f8b83`;
every entry was read back against its manifest. Earlier loaded runtime images
and source were preserved in private backups.

The Windows process provider also receives a maintained SDK overlay. A deadline
can expire just before the child exits; the immediate recheck must collect that
exit instead of reporting I/O failure. A deterministic test fails on the pinned
provider and passes with the overlay, covering six cases and three repeated-status
checks. Timeouts and genuine wait/status failures retain their error codes. This
fix addresses the reproduced provider race; the precise timing of the earlier
intermittent generated-media export failure was not captured.

Nested pictures and compound waveforms remain unavailable. Track/audio-filter automation, animated speed,
larger interactive nested-project acceptance, sustained A/V synchronization and
complete professional editing acceptance remain open. Animated fade trim/Split
refusals retain their existing `GA_TRIM_CONTEXT` / `GA_SPLIT_CONTEXT` safeguards.

## Recursive compound pictures on 2026-10-10

Compound clips now render children in postorder, then apply their enclosing clip's
ordered picture effects to the completed child. Transparent FP32 RGBA coverage
survives child fitting, fades, masks, transforms, blur, blends and transitions;
the root is flattened onto black once. The ordinary flat renderer retains its
legacy mode. Native child subtitles and title-only children are included.

Owner time maps to child time using source-in, effective rate, reverse and the
owner/child FPS ratio. Each placed instance owns separate bounded scratch names.
The planner validates cycles, missing sequences, geometry, history and resource
limits before raster work. Parent Stabilize requires unavailable group history
and refuses with `GA_VIDEO_NESTED_HISTORY`. Existing transition-layer restrictions
remain in force.

Compound timeline bitmaps use the isolated clip picture plan. Their manifests
retain both mapped frame identity and document revision, so descendant edits
retire completed strips. An intermediate worker refusal now restarts its session:
a failed child canvas cannot contaminate the next ordinary preview. Specific
worker diagnostic codes survive both text replies and picture connection failures.

| Candidate gate | Evidence |
|---|---|
| Planner | Six cases / 44 checks on Windows and Linux; existing spatial-canvas gate has four cases / 107 checks. Audio/export control suffix remains byte-identical. |
| Native compositor | 604,160 independent channel comparisons, worst error `1.73e-7`; 42 byte-exact legacy comparisons against the previous accepted worker. Twelve blend modes, eleven transitions, alpha fitting, Gaussian blur, bilinear transforms, root flattening and three encoder canvas guards are covered. |
| Allocation recovery | 104 native checks, including 16 injected allocation failures, prospective 4 GiB refusal, four-canvas eviction and zero live resources after shutdown. |
| Saved project pictures | 26 independently authored cases: 416 native 16-bit master frames, 208 preview requests and 26 exact frame-zero rewinds. Seven coded refusal cases preserve project bytes and publish no output. A nonlinear parent-on-sum oracle differs from the incorrect per-leaf result by `0.0617647`. |
| Picture/audio mapping | 25,600 NUT stereo sample frames match the authored PCM exactly. This covers that fixture's sample mapping, not every container or long-running device synchronization. |
| Actual filmstrip | 128 asynchronously rendered compound bitmaps cover mixed FPS, reverse, trim/rate and descendant brightness changes. Three cases / 17 checks also preserve flat six-field manifests and recover the canvas after a coded refusal. |

The full independent picture gate used application
`6cf8a58a956670c224374ac5bea70148715eed80f9534f902ab0cbdffe7c4f51`
and worker `e8354f1845985a9cf12697887fc5ddf48b590277649cf8394492ea4fd216eb73`.
The [native candidate UI receipt](../archive/native-compound-candidate-ui-2026-10-10.json)
records a reloaded window using a private copy of the supplied flat 4K project:
playing pictures/time and stereo meters, stopped silence, nonblank frame-zero
rewind, a fitted full filmstrip and embedded waveform, and completed scrubs at
`00:01:23:46` and `00:03:01:49` with matching marker/time/scopes. The earlier
unsaved user window and original project were preserved. A separate 30-second
compound placed that source and its AAC audio inside a 480x270 child sequence:
native child/parent pictures and filmstrip appeared, playback had active stereo
meters, Stop cleared them, parent gain changed `1 -> 0.95 -> 1` through Undo,
and a completed scrub at `00:00:11:14` matched its green-snake filmstrip scene
and program scopes. Rewind returned to a visible frame zero. These bounded
window checks do not establish larger compound projects or sustained 4K60 cadence.
Native source fitting is checked against independently decoded/scaled codec pixels;
completed-group fitting and compositing use independent math. The strict native
error bound remains five 16-bit codes. Title acceptance covers timing, transparent
background and grayscale coverage; font glyph shape is outside that oracle.

At this compound-picture checkpoint, native canvases and FP32 disk intermediates
prioritized picture correctness; one 4K group was 126.6 MiB. The later GPU snapshot
checkpoint below removes internal group files. Smooth compound 4K60, larger interactive compound projects,
compound waveforms and complete professional editing acceptance remain open.
At this checkpoint, the separate audio audit also reproduced a PCM Matroska trim defect:
timestamp-based selection against millisecond packet PTS shifts sample boundaries.
Both the released and candidate workers reproduce it; independently authored NUT
mapping passes and independent FFmpeg sample-count selection is exact. Origin-based
sample selection required a separate decoder checkpoint, now covered below.
Late audio-seek latency remains open.

Focused checks (use binaries built from the matching current source):

```powershell
python tests/nested_picture.py --binary .\Genesis-AIR.exe --worker .\genesis-gcompose.exe --report .\build-windows\nested-picture.json
python tests/nested_timeline_bitmaps.py --client .\build-windows\native\bin\Release\genesis-nested-timeline-bitmaps.exe --worker .\genesis-gcompose.exe --report .\build-windows\nested-timeline-bitmap-pixels.json
python tests/compound_pixels.py --worker .\genesis-gcompose.exe --report .\build-windows\compound-pixels.json
```

`build-windows.ps1 -RunTests` registers these gates plus the planner and native
OpenCL canvas harness. `-CompositorSource` selects a private compositor source for
acceptance without migrating the canonical checkout. Export stays at native
sequence dimensions, and Genesis continues to reuse MM-AIR's codec runtime.

The complete isolated Windows build/gate passed with freshly generated AIR C,
including these compound gates, existing HDR/large/spatial picture checks,
ordered filters and titles, all audio/automation/nesting/cancellation gates,
native device clock, project recovery, retained painting and 749 control clicks.
The installed root application is
`0ae78ad228199d00f415bc0994e82a2444244ba41b3d802b6f04b7560d3d605c`;
its worker is `e8354f1845985a9cf12697887fc5ddf48b590277649cf8394492ea4fd216eb73`.
All six root runtime files match the accepted payload hashes. A cold native
window from that root build opened the private 4K project with visible frame-zero
source/program pictures and video filmstrip. The saved candidate QA window and
its workers exited; the earlier unsaved user window remains intact.

Canonical migration changed only GPU, FFI and worker-main sources. The other
four maintained worker source blocks remain byte-identical, and the full overlay
passes its reverse check against pinned worker
`5e26dc2203540f3c2996dba7506f5da18d4065ac`. The maintained overlay SHA-256 is
`3418035f56a2305e036e2f7f8a9b5fea2db78767a8dbcb3b1be9019e54975f9c`.
Earlier root images and canonical sources were preserved in private backups.

The 35-entry [sanitized acceptance bundle](../archive/compound-pictures-2026-10-10.tar.gz)
has SHA-256 `c8369251f84c3e5dba9bc84ebcb5b85c76304752994c464a966de005814814c1`.
Each entry was read back against its manifest; the bundle includes production
source fingerprints, full-gate output, independent picture/bitmap/resource
receipts, the before-fix canvas failure and the retained Matroska audio gap.

## GPU picture snapshots and source audio boundaries on 2026-10-10

Internal compound-group and ordered-filter FP32 passes now stay in native GPU
snapshots. The alloc-only AIR lowering pass binds a fresh executor-chosen epoch,
assigns immutable IDs to intermediate outputs and drops each snapshot after its
last input use. Old epochs, dropped IDs, incompatible exact canvases and malformed
references refuse with `GA_VIDEO_SNAPSHOT_*`; terminal output, abort, failure and
worker shutdown release owned snapshots. Same-size siblings remain independent,
and snapshots survive eviction from the four retained-canvas slots. The combined
snapshot/canvas allocation budget is 4 GiB. A native store validates finite pixels
and compound alpha through a four-byte status readback; no full FP32 intermediate
picture crosses to host memory. Final preview readback, external FLOAT output and
encoder quantization retain their existing contracts.

Source audio selection now counts decoded samples at the native source rate
before resampling. Its origin is the first decoded frame timestamp after decoder
skip/edit handling, rather than coarse packet PTS or the first packet timestamp.
Positive origin offsets contribute leading silence; negative offsets skip
pre-zero samples. Reverse uses the same native interval selection before
resampling. Child buses preserve their full-history processing before root seek
slices. Picture and audio mapping retain the saved owner/child frame-rate domains.

| Gate | Evidence |
|---|---|
| Native snapshot lifecycle | 23,627 checks: same-size immutable siblings, exact dimensions, finite/alpha validation, injected allocation recovery, four-canvas eviction, prospective shared 4 GiB refusal, dropped/stale IDs and zero live resources after shutdown. GPU validation reads four bytes rather than the FP32 picture. |
| Snapshot protocol and pixels | 20 cases / 92,302 checks: independent straight-alpha equations, nonlinear parent-on-sum, both brightness/contrast orders and duplicate filters, portrait fit, stale/inactive references, abort/EOF, external FLOAT, PREVIEW, exact PREVIEWTCP identities/pixels and independently decoded lossless ENC output. |
| Existing picture contracts | 26 authored compound cases plus seven coded preview/export refusals, the native compound pixel gate and 128 actual asynchronous filmstrip bitmaps pass with the new worker. Existing flat paths and ordered-filter/title gates pass. |
| Corrected installed audio baseline | 91 cases / 364 comparisons, with 102 failed Matroska outcomes; WAV/NUT controls pass. The oracle rounds seconds through the existing microsecond duration parser before native-sample selection and does not use Genesis output as its reference. |
| Fresh source boundaries | 130 cases / 664 checks pass: 520 project PCM outcomes have maximum error `0.500481367111206` PCM units, and all 144 mono decoder comparisons are exact. Authored sample-coded 48/44.1 kHz WAV/NUT/Matroska, whole output, uneven chunks, fresh seeks, reverse, mixed FPS, nesting and gain/fade context are covered. Independently decoded first-frame PTS proves positive/negative origins and AAC skip/edit cases. Source/project bytes remain unchanged; Stop/join leaves no owned nested cache. |
| Native UI | Fresh candidate Play advances pictures with stereo output meters; Stop is silent and rewind restores visible frame zero. A distant `00:00:12:41` seek updates Program picture/timecode, status/playhead and histogram, RGB parade and luma waveform. This functional check adds no sustained cadence or physical-hearing claim. |

The complete isolated Windows build/gate passed with freshly generated AIR C,
including the snapshot lifecycle/protocol, compound/filmstrip gates, existing
picture/export/audio gates, project recovery, native device clock, retained
painting and 749 control clicks. The new source-boundary registration was added
after that invocation parsed its script, so a separate fresh native-client run
then passed all 130 cases / 664 checks against the same final app/worker.

The installed application SHA-256 is
`2DD0C3938EDD3DE5C061B91839092179EC016F5F8F1175CCEFD8B1075B892912`;
the worker is `C2947D934F00EC9CFA0509F9215015BFE4D19AC3CF814A8C9F2B55B3A62FBEAB`.
The fresh source-boundary client's SHA-256 is
`4E7081AC93CC4DE1E802F9AF54A78047818CFB25ED962E043C3218D2FA40BC0A`.
The seven-file maintained worker overlay passes pinned forward/reverse and LF
round-trip checks; its SHA-256 is
`3f25d5d1b55b03acee5b561e7c26c8ff47f59e2b5e9276a8a3f5e571ae19b831`.

A separate sequential headless 4K compound comparison retains native 3840x2160
child/root canvases inside a 1280x720 ordinary-editor canvas with fitted 480x270
monitors. It uses three warmup pictures and twelve measured serial pictures:

| Measurement | Accepted disk intermediates | Snapshot prototype |
|---|---:|---:|
| Program median latency | 788.89 ms | 66.50 ms |
| Whole serial pipeline median | 799.46 ms | 72.22 ms |
| Reciprocal whole-pipeline mean | 1.175 pictures/s | 12.928 pictures/s |
| Observed FP32 group files | Two, 132,710,400 bytes each | None |

The accepted measurement uses app
`0AE78AD228199D00F415BC0994E82A2444244BA41B3D802B6F04B7560D3D605C`
and worker `E8354F1845985A9CF12697887FC5DDF48B590277649CF8394492EA4FD216EB73`;
the prototype uses app
`0ABDFF80F6494BDE8D7AB030A28BF7A04478AA2172ADFD279B9310A06B75F7D4`
and worker `2DC132F4C39EBE57A4719AB806AAE197F10CCA6216DA8093E6B99E0784CF7856`.
The final worker retains that GPU implementation and adds the source-audio fix;
this timing does not belong to the final integrated app hash. The comparison
excludes audio, native presentation and paced playback. The last profile argument
is a picture count, not seconds; the file observation is not a physical disk-I/O
measurement. Protected source/project and measured binaries retain their hashes.
These results are well below sustained compound 4K60.

The native functional receipt is
[`archive/native-picture-memory-ui-2026-10-10.json`](../archive/native-picture-memory-ui-2026-10-10.json).
The 45-entry [checkpoint bundle](../archive/picture-memory-audio-boundaries-2026-10-10.tar.gz)
was sanitized and read back against its manifest; its SHA-256 is
`fa5a0a08a435dbbc21ade6301ea3fc96c7544e118baa3999e3cc646e807a64b7`. All six installed runtime
payload files match their accepted hashes. Canonical migration changes five
worker source blocks and preserves the other two byte for byte; the overlay
reverse check passes. A cold root launch opened the private 4K-source compound
with visible beach pictures in both monitors at frame zero and a complete
30-second filmstrip in the ordinary maximized Audio-tab window.

Remaining limitations: the missing-first-PTS refusal path is not independently
fixture-proved; later timestamp discontinuities are not repaired. Decoding from
the origin makes fresh distant audio seeks O(seek). A fresh 44.1 kHz reverse seek
regenerates the shortened interval's resampler EOF phase instead of slicing full
clip history, while nested seeks slice their processed bus. Compound waveforms,
larger interactive projects, sustained compound 4K60, zero-drop native cadence and
physical speaker/display alignment remain open. Native compound canvases are
still conservative; no lower-resolution spatial-effect shortcut was introduced.

Focused acceptance commands:

```powershell
python tests/picture_memory_pixels.py --worker .\genesis-gcompose.exe --report .\build-windows\picture-memory-pixels.json
python tests/audio_source_boundaries.py --binary .\Genesis-AIR.exe --client .\build-windows\native\bin\Release\genesis-audio-nested.exe --worker .\genesis-gcompose.exe --report .\build-windows\audio-source-boundaries.json
```

## Compound waveforms and native upload on 2026-10-10

Compound clips now display processed stereo peaks alongside their filmstrip.
The strip worker defines the complete child/parent audio tree and queries one
root bus through `NESTENV`. This includes child sums, track/clip gain and pan,
fades, audio effects, trim, reverse, rate, repeated instances and mixed FPS.
Bucket boundaries are exact floor partitions of the complete clip-local 48 kHz
output. Peaks retain raw float headroom above one; a held picture produces silence.

Document and media revisions travel in `WAVEFORMS 2` publications and are checked
again by the painter. A descendant edit invalidates peaks even when the root's
source ID, length and endpoints stay unchanged. Invalid/nonfinite data and incomplete
generation markers cannot replace current entries. Matching content/time/bucket
metadata reuses peaks on zoom/scroll requests, so viewport navigation does not
reconstruct unchanged audio. Cold changed buses still require full background
materialization and temporary disk storage; large interactive project latency
remains open. Flat waveforms retain the existing source-envelope approximation.

| Gate | Evidence and scope |
|---|---|
| Historical omission | An immutable `df5a887` client with the accepted worker omits all 20 compound waveform rows; both direct-source DC/silence controls pass. |
| Independent actual cache | 23 authored cases compare exact processed stereo bucket maxima and mapped endpoints. Cases include cancellation/antiphase, spikes, raw headroom, parent-on-sum compression, trim/rate/reverse, mixed FPS, mute/solo, repeated instances, automation and a held fractional-rate compound. The oracle starts from authored sample arrays, not Genesis audio output. |
| Publication and display | 26 native cases / 84 checks cover actual cache population, descendant retirement, pixel evidence of current versus stale painted waves, malformed/partial refusal, reuse with an unavailable worker, content invalidation and held silence without a worker. |
| Envelope protocol | Four exact partitions include one bucket, uneven three, more buckets than samples and 65,536. Eleven refusal/recovery stages cover invalid roots/counts, output ownership, pending transactions and nonfinite/truncated caches. Successful peak files remain caller-owned after worker close. |
| Real cancellation | Stop and supersede interrupt genuine long RF64 cache construction, leave no owned worker/cache/partial peaks, and a fresh request recovers with independently expected peaks. The focused final run joins in 0.173/0.180 seconds. |
| Native upload | The OpenCL harness performs 810,071 checks across all 65,536 u16 codes in all three slots, immediate host-buffer overwrite and resource lifecycle. Fifteen worker cases compare 12,029,256 FP32 channels exactly, require actual fast-path entry, and cover RGB/NV12/PQ/HLG, fitted/odd fallback, seek/EOF/rewind and software/forced-FP32 controls. |

The upload borrows the decoder's existing reference-color-transformed RGBA64 buffer,
finishes a blocking transfer, and expands it with the same FP32 conversion constant.
It uses existing budgeted GPU scratch; no extra native canvas buffer or lower-resolution
effect calculation is introduced. Fitted/odd/spatially incompatible frames retain the
previous path. `GENESIS_NATIVE_U16_UPLOAD=0` selects that path explicitly.

The separate short ABBA prototype benchmark reduces mean serial native-4K compound
latency from 73.19 to 67.28 ms, about 8.1%, or 13.66 to 14.86 reciprocal pictures/s.
Run variation is substantial; audio, native presentation and sustained paced cadence
are excluded. These timings belong to the upload-only candidate hashes documented
in [GPU preview notes](FFMPEG_GPU_PREVIEW.md#native-16-bit-upload-and-processed-compound-waveforms),
not a fresh timing of the combined waveform build. Native decode and reference
HDR/color processing remain major costs; responsive compound 4K60 is still unproved.

The [cold candidate UI receipt](../archive/native-waveform-u16-ui-2026-10-10.json)
records visible compound peaks/filmstrip, advancing Play and stereo meters, silent
Stop, visible rewind to frame zero and a completed distant seek at `00:00:12:26`.
The user stopped desktop testing with Escape. The later held/cache fixes have native
regression evidence; this earlier UI binary does not establish their interactive
behavior or add a new scopes observation. The older unsaved user window was preserved.

Focused acceptance commands:

```powershell
python tests/nested_waveforms.py --client .\build-windows\native\bin\Release\genesis-nested-waveforms.exe --worker .\genesis-gcompose.exe --report .\build-windows\nested-waveforms.json
.\build-windows\native\bin\Release\genesis-native-u16-upload.exe
python tests/native_u16_upload.py --worker .\genesis-gcompose.exe --report .\build-windows\native-u16-upload.json
```

The final full Windows build/test suite passed with exit zero, including the
130 source-audio cases / 664 checks, 749 control actions, async waveform/bitmap
publication, native audio clock/cancellation, titles and transitions. The installed
root application SHA-256 is
`73f8f7daf2a0d153c90a6a82ae069ed6cf406123f0f4c4c55e9ddc4a8ff6b03c`;
worker SHA-256 is
`4d9dfd6dd4d0f592d0cc3bcd90729eef95ad9715ce6d7cce4efd2a61b4cd0d7d`.
The maintained overlay is
`e92df242cda5c7eb7a7d8153a13fdcce2c070f3b292d5b417bc50035031a5881`.
Canonical migration preserves the three unrelated worker files byte for byte and
passes the reverse patch check. MM-AIR runtime configuration, OpenCL and protected
original project/media retain their hashes.

The sanitized 47-entry [checkpoint bundle](../archive/compound-waveforms-native-upload-2026-10-10.tar.gz)
was read back against every manifest entry; its SHA-256 is
`8856361491f9f3b69ab183ea2e95f62fa706813561c015e6dd5507c1dac6ebfa`.
The manifest records both LF-normalized Git source hashes and raw tested worktree
hashes. A fresh root headless process produces a visible 640x360 beach preview.

After the user requested a reload, a fresh **installed root** process also passed
the [native UI check](../archive/native-waveform-u16-root-ui-2026-10-10.json):
Play advances picture/time/playhead with responsive stereo meters; Stop clears
meters; rewind restores frame zero. A paused seek settles at `00:00:18:51` and a
drag settles at `00:00:02:10`, with matching program timecode, status and marker.
The histogram, RGB parade and luma waveform visibly change with the corresponding
sloth/beach pictures. Fit publishes 23 compound bitmap rows and 512 finite processed
peaks. The older unsaved user window is preserved. This uses 480x270 compound
canvases and fitted scopes in the ordinary editor; it establishes no physical
hearing/alignment, full native 4K scan or sustained 4K60 acceptance. Flat processed
waveforms and larger interactive projects remain open at that historical checkpoint.

## Processed direct waveforms and vertical tracks on 2026-10-10

Direct clips now define a complete processed stereo leaf inside a neutral bus and
query its exact clip-local 48 kHz body through the existing `NESTENV` protocol.
This replaces the mono, downsampled source-envelope approximation. Trim, reverse,
static rate, gain, pan, fades, static audio effects and complete gain/fade curves
retain the same history as playback. There is no final device limiter in waveform
peaks. Disabled, inaudible and held contributions are zero. Unsupported audio-filter,
pan or speed automation returns `GA_AUDIO_CLIP_ENV` rather than an approximation.

The focused native gate passes 33 authored cases and 153 checks. Independent
stereo bucket maxima differ by at most `3.7252903e-9` under a `2e-6` threshold.
Retained uneven playback pulls and full processed bodies agree within one PCM
code across 3,433,248 channel samples. The independent DSP adapter reads the
authored source file and trims native samples before resampling and `atempo`;
repacketizing raw samples changes `atempo` output, so raw-file packet assumptions
are not used as its oracle. Failed adapter receipts are preserved; tolerances
are unchanged. The existing 23-case compound gate also passes with the direct
mono control updated for playback's equal-power mono-to-stereo rematrix.

Only clips intersecting the requested time viewport are scheduled. Matching
cache entries remain usable with an unavailable worker; offscreen missing media
is untouched. Stop and supersede interrupt real cache construction, join owned
workers, remove their temporary data and recover with independently expected
peaks. Cold changed clips still materialize a full body, and every audio-only
worker currently performs OpenCL initialization. Per-clip semantic reuse after
an unrelated document edit remains a performance opportunity.

The vertical track viewport uses shared AIR state and the existing timeline
model for both painting and pointer dispatch. Header wheel and Up/Down reach
lower tracks; timeline-body horizontal navigation and Ctrl zoom retain their
behavior. A reserved footer keeps lane pixels and hit targets clear of the
navigation buttons. The native 24-track fixture passes four cases / 32 checks:
bottom-lane pointer selection at 640x480, exact lane capacity, bitmap/waveform/
transition pixels, document/time/revision preservation, resize, hidden tracks,
sequence changes, add/remove and Undo.

Windows acceptance combines the unchanged media/native prefix from the initial
full run with a passing controls/media tail rerun. The initial run exited one
because the diagnostic treated disabled Up/Down buttons as enabled controls.
The repaired diagnostic actually clicks them and verifies unchanged state;
all four tabs now report 757 outcomes, including eight disabled-button checks.
`tests/windows.ps1 -ControlsOnly` reruns that tail without repeating the expensive
unchanged prefix. The original failed log is retained alongside the passing
resume log; this is not presented as a single full-suite exit-zero run.

The installed root application SHA-256 is
`0928f1c3feec847f88ea0b02be61ad40f6762766eaefe6c6132382af0d5edb4b`.
Its [fresh native UI check](../archive/native-direct-tracks-root-ui-2026-10-10.json)
uses a private 26-track project with the original 4K source and a 480x270 canvas.
Header scrolling and footer buttons reach the direct V1 clip. Fit publishes
23 frame bitmap rows and 512 finite processed peaks. Play advances picture,
time and marker; embedded-audio mute clears the meters and unmute restores them.
Stop clears meters; Start restores visible frame zero. Timeline and monitor
drags settle at `00:00:19:03` and `00:00:03:12`, with matching Program timecode,
status and marker. Histogram, RGB parade and luma waveform change with the frames.
The original unsaved window and original project/media remain intact. This
fitted-editor check establishes no sustained native 4K60 or physical audio alignment.

Separate historical helpers frozen at `36d41fb` pass 13 whole-project semantic
comparisons with 1,040 and 2,064 clips, including rejected Save/Open and history
recovery. Their fake-provider compact preview/paint cycles have medians of
4.115 and 5.260 ms; cold snapshots take 168.489 and 322.591 ms, and changed
snapshots 184.015 and 350.813 ms. The larger snapshot is 1,849,607 bytes and
is accepted. These are CPU/model measurements on that frozen helper, excluding
real media, audio devices, native window presentation and this later scrolling
build. Large interactive projects still need device/UI acceptance.

Focused reproduction:

```powershell
python tests/direct_waveforms.py --client .\build-windows\native\bin\Release\genesis-direct-waveforms.exe --worker .\genesis-gcompose.exe --report .\build-windows\direct-waveforms.json
.\build-windows\native\bin\Release\genesis-timeline-track-scroll.exe .\build-windows\track-scroll-check
```

Native 4K HDR shader work remains an independent private prototype. The accepted
worker, shared MM-AIR runtime, original project and source media are preserved.
This checkpoint does not establish sustained compound 4K60, physical audio latency,
universal automation support or complete professional-editing acceptance.

The sanitized 71-entry [direct-waveform/track checkpoint bundle](../archive/direct-waveforms-vertical-tracks-2026-10-10.tar.gz)
was read back against every manifest entry. Its SHA-256 is
`3058a55d97130ec83811780080af0b9a728a052118dba71974c52f902040438d`.
It retains the failed initial diagnostic, passing resume, focused/native reports,
tested source and payload hashes, and explicitly historical large-project helpers.

## Visible strips, lazy GPU and qualified HDR candidate on 2026-10-10

The combined candidate passes one complete exit-zero Windows run, separately
from the previous direct-waveform checkpoint's prefix plus repaired tail.
Its application SHA-256 is
`AD8985B4311EA74A673A615893B9ADE3491C065575AF97F518E909CE0ED7A5EC`;
the worker is
`378685335B4C17AE44B5A03C892F0008B85C172CFBE6EA57FB20339BB377552F`.
The root now publishes the `52A6` secondary-button guard. Acceptance combines a
complete Windows suite on `80A6` with targeted controls/probes/failures and native
checks on `52A6`, plus its separate root playback below. It does not claim a full
suite rerun on the final binary. The `C524` large-project workflow and earlier
media/viewport candidate retain their exact identities and bounded scope.

| Path | Evidence and scope |
|---|---|
| Visible strips | Nine-field native requests add first displayed lane and logical body height while retaining legacy 3/5/6/7-field APIs. Shared reversed SDK lane order and horizontal intersection select clips; a partial last lane receives data. Vertical scrolling and resize reschedule without changing authored time or revisions. |
| Bitmap budget | At most 32 tiles commit. Visible lanes/clips get turns before their next tile; dense upper clips cannot consume every first turn before a lower visible lane. More than 32 visible clips receive a bounded deterministic subset. Source/frame/time metadata and 80x45 pixels remain aligned. |
| Processed peaks | Only visible clips are constructed/published. Matching retained peaks are reused; current offscreen entries are omitted from the publication. Changed visible clips still materialize their full bodies. Unrelated semantic edits can still invalidate otherwise reusable entries. |
| Strip failures | Waveform reserve/data/generation writes are checked before success. `GA_TIMELINE_PUBLISH` preserves prior owned cache/foreign bytes on blocked publication. The first failed bitmap returns `GA_TIMELINE_SOURCE` plus worker detail and stops further timepoint attempts. Bad metadata returns `GA_TIMELINE_RANGE`. Same task/retained CPU process recovery and request-generation error retirement pass. |
| Lazy OpenCL | Audio-only commands and CPU thumbnail/source-count work start without compositor initialization. First picture composition initializes once; later CPU/audio commands preserve picture/scopes history. Initialization/readback fault recovery uses coded errors, removes owned caches and publishes no encoder output. |
| Qualified HDR | Supported even full-native P010/PQ D3D11 previews use a shader only after qualification of CPU capabilities and actual loaded shared color modules. Master/reference, unsupported/fitted dimensions, unknown runtime and resource faults retain exact fallback. This preserves the shared MM-AIR runtime boundary. |

The persistent CPU-only strip task/channel gate passes six cases / 40 checks.
It reproduces legacy offscreen 32-tile starvation, exercises actual nine-field
files, header-wheel scrolling, dense two-lane fairness, partial-row selection
and same-revision stale-result rejection. It reads committed bitmap pixels and
checks selected source/frame mapping. A blocked waveform temporary path keeps
the old TSV and foreign sentinel, commits no new generation and recovers when
repaired. An opt-in CPU process wrapper refuses one source decode with an owned
diagnostic, then returns exact pixels through the same retained process/PID.
Tiny legacy zoom near the signed endpoint remains bounded without time wrapping.
This gate does not constitute native-media or native-window acceptance.

Lazy-GPU validation includes 21 malformed audio commands, 512 exact PCM channels
with zero OpenCL initialization, real CPU thumbnail pixels, retained audio and
scopes after picture initialization, nested-cache cleanup and injected init/read
failures. The full suite retains HDR/master, shared-runtime, source-sample,
waveform, stream, cancellation and 757-control checks.

The shader's zimg coefficient provenance/license is maintained beside its
source. Qualification checks AVX512/AVX2/FMA3, module file fingerprints and
loaded-image identity while retaining the qualified files. Twelve authored
cases preserve the existing five-u16-code bound; accelerated maxima are below
two codes, all values finite, and fallback paths byte-exact. Eight selected
real 4K frames, including EOF/rewind, add 265,420,800 channel comparisons and eight
actual shader entries with the same maximum. Native-u16/snapshot ownership,
resource refusal and recovery separately pass 810,083 checks. Selected-frame
color correctness does not establish sustained native 4K60.

Four private paired headless runs measure 12 warmed samples each (three warmups).
Reference serial compound means are 90.304/64.147 ms; native shader means are
38.356/38.317 ms. Those native 3840x2160-canvas measurements exclude audio,
native presentation and sustained pacing; the ordinary monitor is 480x270.

The fresh actual regular 1080p60 window uses a 2560x1316 surface and fitted 480x270
monitors. The first playing epoch spans 60.147 seconds and shows 3,591 changed
pictures at 59.74/s, eight skipped positions and two startup/EOF drained-queue
presentations. The complete profile remains retained. Excluding exactly the
first 1.0 second and final 0.5 second gives 3,502 changed pictures over 58.463 seconds
at 59.88/s, six skipped positions, no observed drain and a 29.55 ms maximum gap.
Steady device drift is -0.9881 ms and after-presentation metadata lag is generally
two frames / 33.33 ms. No early or over-two-frame stale pictures are observed.
These are native handoff/EndDraw and device sample-clock observations, excluding
speaker/photon latency and independent identity of every source pixel.

EOF retains a visible picture; Start restores frame zero. Paused seeks to frames
266 and 1777 align Program time, marker and histogram. Fit publishes 32 bitmap rows
and 512 processed peaks; embedded mute/unmute and Stop change audio meters.
The larger private project has 1,032 placements, 32 root tracks, 24 compounds,
8,192 keys, 1,600 filters and 64 titles. Visible Busy V1/A1 lower-lane bitmaps and
peaks publish, and 21 seconds of paired-AAC playback with responsive lane scrolling
are observed. Every clip is two seconds and at most one video/audio pair is
active; this does not test 1,032 simultaneous decodes.

That native large-project check found a title-text dispatch defect. The repaired
input candidate's native typing/selection observations and the separate
clipboard adapter checks are recorded below, followed by the `C524` native paste,
history, whole-graph roundtrip and bounded cancellation/retry receipt. The final
wheel-modifier repair's separate native observations follow, then the published
secondary-button guard's combined acceptance and root profile.
Historical 36d41fb model timings and 15a148c receipts retain their earlier scope.
No fullscreen 4K, zero-drop 60fps, physical audio alignment,
sustained compound 4K60 or complete professional-editing acceptance is claimed.

### Native prompt text and Windows clipboard candidate

The native Text event now reaches the shared prompt controller instead of being
discarded. Physical key actions and committed Unicode text use separate paths:
letters append once, while shortcut/control-character text cannot duplicate
Backspace, Return or Ctrl+A. Ctrl+A selects the seeded value and paints a visible
highlight; subsequent text replaces it. Backspace removes complete UTF-8
characters, including supplementary characters and a base with combining marks.
Draft text creates no document revision or Undo entry; Enter commits through the
controller, and Escape discards the draft.

The focused inspector suite passes 21 cases / 197 checks, including 23 prompt
checks: rendered selection, Unicode deletion, one title transaction, complete
Undo/Redo restoration, private Save/Open and cancelled-draft preservation. These
are native CPU/painter/controller checks, separate from interactive acceptance
of the larger project.

In the actual large-project window, the private input candidate beginning
`70CA` opens filter `100002`'s title prompt, Ctrl+A highlights `PRIVATE CUT0`,
and physical Shift+E replaces it with `E`. Escape cancels; the private fixture's
SHA-256 remains `4CCE055803E5E8DEA02025A75FD4F374A4CAAAAAF3DDD752C797B89C192E480E`.
Automated bulk text injection did not enter text in that window, so this observation
establishes physical typing/selection only.

`patches/air-ui-text-windows.patch` extends the reusable AIR Win32 canvas adapter.
Ctrl+V, Shift+Insert and WM_PASTE borrow CF_UNICODETEXT and enqueue committed
Unicode scalars through the same ordered event queue; Genesis keeps text-editing
policy in the shared application source. The adapter bounds reads to 524,288
UTF-16 units and the clipboard allocation, rejects missing terminators/oversize
input before partial publication, replaces malformed surrogate sequences and
balances clipboard lock/close operations.

`tests/ui_clipboard_windows.c` passes 1,044 CPU checks against the patched adapter
with injected clipboard APIs. It covers Latin/CJK/supplementary Unicode,
1,000-scalar queue growth and event order, Shift+Insert, AltGr exclusion, surrogate
state, unavailable/malformed clipboard data and borrowed-byte preservation.
The test opens no actual window and accesses no user clipboard. The overlay is
registered in the Windows build/test path. Actual paste acceptance is recorded
separately below, followed by the published root guard's acceptance.

### Native large-project text, roundtrip and export on C524

`native-text-export-ui.json` records the application
`c524a472bee8c13c6e42d080702d3e48cd4d5b810ed835a111c2de00d2e57fc3`
and worker `378685335b4c17ae44b5a03c892f0008b85c172cfbe6ea57fb20339bb377552f`.
In the actual private large-project window, Ctrl+A selects `PRIVATE CUT 0`;
native paste replaces it with `PRIVATE EDIT CONFIRMED`. Enter commits, and the
asynchronous Program preview renders the complete replacement title. Moving
Brightness Down places it below Contrast. Two Undo actions restore the title
and order; two Redo actions restore both edits.

Native Save As, Open and a second Save As compare the complete independently
declared graph with zero unexplained differences: 1,032 clips, 8,192 keys,
1,600 filters, 64 titles and all other saved fields. The comparison resolves
parameter IDs through each document's own name pool, retains the complete pool
and preserves array order except canonical key storage order. Only explicit
transport/selection state has a separate ledger. Ctrl+S after the export tests
again produces zero graph differences. Protected inputs remain unchanged.

The actual native Render range uses an exclusive mark-out. Exporting `[0,240)`
reaches 58%; Escape acknowledges cancellation, the export child exits, and the
partial movie, nested sidecars and cancellation signals are removed while the
preview child remains. A `[0,12)` retry completes, but its original source frames
0..11 are silent, so the strict audible-content oracle refuses that result.
That failure remains in the evidence.

A second private copy changes only the first video/audio source-in to 600. Its
12-frame retry independently matches source frames 600..611, title-glyph
interiors and outside-title grade-order math. Processed AAC is compared with
native source samples `[441000,449820)` under the authored compressor/key/track
gains: 9,600 output sample frames, zero-shift correlation 0.99997586 and RMSE
0.00056555. No output-derived alignment or gain correction is used. The video
oracle uses fixed lossy bounds and glyph interiors, rather than claiming exact
anti-alias raster equality.

The audible oracle preserves a bounded byte ledger: its project hash is
`e29d8d61a5544608f1b0673fb900ad44e4d940121dacdf2db9abcce9c47bc6c2` before and
after decoding. Subsequent native Ctrl+S has a separate serialization hash,
`f7be82889d1a3e428ae9613dbdb47bd7a11d80d81a26d00a94783f330673bab0`.
The post-export comparison records zero graph differences and equal canonical
graph hash `f3ec44843b1e40b2d42fa1cbe8c7a72eb36167275d7cc2d529528a71afc0eb06`.
Oracle-input immutability and later native save are separate steps; the later
serialization is not claimed byte-identical to the oracle input.

Input-plus-immediate-capture acknowledgements are 162 ms for paste, 249 ms for
title commit, 237 ms for reorder, 293 ms for Save As, 473 ms for reopen, 291 ms
for the reopened save and 166 ms for cancellation. These single observations
include automation/capture overhead; they exclude asynchronous picture
completion and photon latency and are not a latency distribution.

The same run exposes stale Ctrl state after a native picker: a plain header
wheel zooms instead of scrolling. An event-local modifier/pointer-coordinate
repair is independently observed in `80A6` below. Its full suite passes before
the main-only `52A6` guard is accepted by targeted/native gates and published.
`C524` workflow acceptance and `AD8985` playback
measurements retain their own scope. Initial project open also briefly clears
monitors while the asynchronous preview arrives. The source's full 21-minute
body, full large-project playback cadence, physical A/V alignment and fullscreen
4K remain outside this bounded acceptance.

### Final event candidate native playback and wheel checks

The final event candidate is application
`80A6F2C1423BE6DBD591CB98463A3391900DE96CBB2073266110709C16591F38`, with the
same worker `378685335B4C17AE44B5A03C892F0008B85C172CFBE6EA57FB20339BB377552F`.
Its own first-epoch snapshot and `analysis.json` belong to the
`native-regular-event-1080p-ef7ec3885ad8453ab895f932174d6fb1` run. The snapshot
hash is `446C5AD63ABACF4E0B38FBE2308C81B2BC93A0A89938401C9A4593B8CBDCCFD2`.
The original `AD8985` profile above remains historical.

The actual surface is 2560x1316 with ordinary fitted 480x270 monitors. The first
contiguous playing epoch spans 60.164 seconds: 3,590 changed pictures at 59.73/s,
eight skipped positions, one repeated presentation and two startup/EOF drained
presentations. Its maximum raw gap is 157.72 ms. Explicitly excluding the first
1.0 second of device samples and final 0.5 second of authored duration gives
3,502 changes over 58.463 seconds at 59.884/s, six skipped positions and no
observed drained queue. Two four-frame jumps are 1500→1504 and 2964→2968; the
maximum steady picture gap is 34.90 ms and p95 is 16.94 ms. There are no early,
over-two-frame stale or overwritten pictures. Device interval drift is -0.9696 ms;
median paint is 1.2448 ms and present is 14.1318 ms. After-presentation metadata
lag remains two frames / 33.33 ms. The raw epoch and exclusions are retained;
these rates do not establish zero-drop 60fps or physical speaker/photon alignment.

The actual window retains EOF at `00:00:59:59` and a nonblank Start frame zero.
Settled scopes at frame zero, seek 266 (`00:00:04:26`) and Fit/seek 1768
(`00:00:29:28`) align Program picture, time, marker, RGB histogram/parade and luma
waveform. Fit publishes 32 filmstrip tiles and processed waveform peaks. Live
mute produces silent meter peaks; unmute restores them. Stop remains nonblank
at `00:00:59:18`, Start returns to frame zero, and a private Ctrl+S/close succeeds.
These are settled asynchronous observations, not synchronous seek-latency proof.

In the 1,032-placement private project, plain header-wheel inputs of 800 and 600
after Ctrl+O and the native picker scroll Tracks while the ruler remains 0..7.
Lower-lane bitmap/waveform data is visible and complete. Ctrl+A and native paste
replace the title with `FINAL PASTE CHECK`; Escape preserves the original value.
This validates the event-local wheel-modifier repair in that bounded native path.
A subsequent source review finds that pointer-metadata masking can turn a
secondary-button Down/Up into a primary control action. A shared main-loop guard
now excludes secondary Down/Up from primary actions. Its published `52A6`
acceptance is recorded below. The 80A6 profile/UI observations are historical for
that exact binary; neither its performance nor the C524 export workflow is
relabeled as a final-binary measurement.

### Published root guard and manually stopped playback

`viewport-hdr-final-publication.json` records installed root application
`52A63D75EFF8750091BD33AB576A30A71939E7DF4897B28BDB16377ECAA020C9`
and unchanged worker `378685335B4C17AE44B5A03C892F0008B85C172CFBE6EA57FB20339BB377552F`.
The complete Windows suite exits zero on `80A6`
(`viewport-hdr-event-full-windows.log`). Only `src/main.ai` changes afterward;
27 other frozen production/test source hashes remain identical. The final `52A6`
ControlsOnly run passes 757 control outcomes plus probes/failure checks
(`viewport-hdr-final-controls.log`). Those two gates and final native checks form
the combined acceptance. No complete full-suite run on `52A6` is claimed.
Loaded old images are moved safely to an exact backup; no user process is killed.
The root retains the shared MM-AIR manifest and packages no separate FFmpeg copy.

Actual `52A6` native right-click Mute and Save have no action. Primary Mute is a
positive control: it changes selected/dirty state and removes processed peaks;
right-click leaves that selected state unchanged, and primary unmute restores it.
Private Ctrl+S compares the whole graph with zero differences. After the native
Open picker, plain header-wheel input reaches populated lower-lane bitmaps and
waveforms while the 0..7-second ruler stays unchanged. Ctrl+A/paste becomes
`GUARDED PASTE CHECK`; Escape retains the original title and clean project.
`viewport-hdr-final-ui.json` keeps these separate from historical export evidence.

The actual published-root launch opens `Regular 1080p60.air`, SHA-256
`7d9e045225e1a236237b85c22342f612c1be92e2cfd298e47df58df8014c9ba0`.
Its 76,701-frame / 1,278.35-second source is measured only through manual Stop
at `00:01:15:33`. The immutable first-epoch snapshot in
`viewport-final-root-launch-21d65d55b308488aafa26f0b35cf0b08` has SHA-256
`D1C85B34E42599F4FABD8C0C92BA192E1B610815F8C490FD8B24CE924EAE1E32`;
its separate `analysis-launch.json` preserves the original launch receipt.

The raw 75.711-second playing epoch has 4,521 changed pictures at 59.75/s,
13 skipped positions, one repeated presentation and one startup drained-queue
presentation. Maximum raw gap is 150.69 ms. Explicitly excluding device startup
1.0 second and the final 0.5 second before the observed manual Stop gives 4,434
changes over 74.025 seconds at 59.885/s, eight skips and two five-frame jumps
(707→712 and 2002→2007). Maximum steady gap is 48.58 ms and p95 is 16.95 ms;
no early, over-two-frame stale, drained-queue or overwritten-packet observations
occur in that interval. Device drift is -1.2236 ms; median paint/present costs
are 1.2486/14.1638 ms. After-presentation metadata lag is two frames / 33.33 ms.
This is a manual Stop boundary, not an authored EOF or a full 21-minute cadence
measurement. Raw startup/late-Stop skips remain retained.

Stop leaves the picture visible and meters zero. Start restores a nonblank frame
zero and scopes. Fit populates 32 filmstrip tiles and the processed waveform;
a settled ruler seek to frame 12773 (`00:03:32:53`) aligns marker, Program time,
picture, histogram, parade and luma waveform. Start restores frame zero again.
The personal project bytes remain unchanged. At this checkpoint Fit clamps zoom at
0.05 px/frame: this full clip exposes only about the first 5.5 minutes in the
current window even though status says Fitted. Its fixed 512 waveform buckets
represent roughly 2.5 seconds each. Full-duration Fit and finer/zoom-responsive
waveform detail remained concrete gaps at that checkpoint; the next update below
addresses them. No fullscreen 4K,
zero-drop cadence, physical A/V alignment or full large-project acceptance follows.
Acceptance bundle location: `archive/viewport-lazy-native-color-input-2026-10-10.tar.gz`.
The sanitized source/receipt manifest retains exact app identities, original and
sanitized hashes, explicit exclusions and per-member readback verification; its
local bundle receipt records the archive hash. Media, QA pixel buffers, codec DLLs
and application binaries are excluded. This bundle records the bounded evidence
above, not complete professional-editing acceptance.

## Long timeline Fit and fine waveforms on 2026-10-10

The published aligned native app is `1bd1bccfbf08c30945a1b6e69f8799d8420c9ecf5d25e9ddcc1389597031abe9`.
The worker remains `37868533...`, using the existing MM-AIR runtime without a
separate Genesis codec bundle. The complete Windows suite passes on this exact
application and combined source, including all 757 control outcomes and
153 saved headless facts. Its root payload is hash-verified; loaded user images,
original media and both personal projects are preserved.

| Check | Bounded result |
| --- | --- |
| Timeline navigation | Eight cases / 80 checks cover full 76,701-frame Fit at several widths, a sparse billion-frame ruler and seeks, signed endpoints, nonfinite zoom, wheel bounds, and unchanged project/selection/history. |
| Peak cache | Six cases / 32 checks cover fixed duration-based detail, all-target promotion before eviction, pan/zoom reuse, fair quotas, failed incoming updates and semantic revision invalidation. |
| Waveform pixels | Six cases / 34 checks cover first/interior/last sparse transients, dense max reduction, visible bins, lane clipping and invalid peaks/ranges. The initial fractional-coverage failure is retained; pixel alignment fixes it with unchanged assertions and thresholds. |
| Processed audio | All 34 independent direct and 24 compound cases pass, including a real 33-second sparse stereo source and 600 cells on a 30-second clip, retaining the existing fixed 2e-6 peak tolerance. |
| Actual native window | The ordinary maximized full project fits completely. Seek 72,733 (`20:12:13`) aligns picture, time, marker and histogram/parade/luma. End 76,700 (`21:18:20`) matches an independently decoded black source frame; Start restores visible frame zero. |
| Audio and strips | V1 embedded controls are enabled. Play advances picture/time with active stereo output; Mute silences output and waveform, Unmute restores them, and Stop at `01:00:06` retains the picture with zero output. Fit publishes 23 mapped bitmaps and 25,567 peaks; zoom request 3 to 4 preserves exact waveform TSV hash `a416f520...`. |

All valid current cached targets are promoted before a missing target can evict
them. Incoming peak arrays are validated before changing the cache; requested
generations are published only when every target is retained. The per-clip cap
is 65,536 and the shared budget is 262,144 f64 peaks, or 2 MiB of scalar payload.
Metadata, container overhead, in-flight results and full audio bodies are outside
that bound. Cold preparation still processes complete clips; a changed eligible
clip count can alter quotas and require regeneration.

The private native check ran alongside the regression suite and supplies no new
cadence benchmark. Its saved test project is disposable; original projects,
media and user windows remain preserved. No fullscreen 4K, zero-drop or full
21-minute playback, physical A/V alignment, sustained compound 4K60, or complete
professional-editing acceptance follows.

The [sanitized checkpoint bundle](../archive/long-timeline-fine-waveforms-2026-10-10.tar.gz)
contains maintained source, indexed-source hashes, the full Windows log, native
receipts and measurement rows, and the retained initial raster failure and
unchanged-threshold pass. Every member is checked after writing. Media, pixel
buffers, personal projects, executables and codec DLLs are excluded.

## Clip content and streamed direct waveforms on 2026-10-10

The old clipboard stored only source/range. Paste dropped retiming, fades,
mix settings, filter instances and automation; compound Cut removed the clip
without creating a usable clipboard. The shared editor overlay now owns a
complete clip snapshot and transactionally instantiates it with fresh IDs,
remapped scoped keys and preserved signed/off-body context. Selection and group
links are intentionally fresh. Compound children remain live same-project links.
The application routes audio Paste to an unlocked audio lane and records one
history step only after successful Cut/Paste. Resource removal irreversibly
retires the clipboard reference until another Copy, including Undo branches
that reuse the original numeric source/sequence ID.

Windows and Linux focused command/model gates pass 11 cases/59 checks. Their
oracle walks the raw document arrays rather than calling the snapshot function.
It checks disabled/duplicate filters, Unicode text, legacy and scoped keys,
original edits/deletion, repeated Paste, Undo/Redo and Save/Open, locked/wrong
lanes, missing resources, sequence cycles, cross-FPS targets, exhausted IDs,
unrepresentable occupied survivors, and exact document/history/clipboard
preservation on refusal. The pinned editor overlay passes independent clean-base
forward application, reverse check and exact normalized-source roundtrip.

The media oracle uses independently authored source pictures and PCM, not
pre-paste Genesis output. Five cases cover direct reverse/rate/title/duplicate
grades, audio Cut with gain/pan, post-group compound effects, and a single bottom
grade beneath an upper layer in both child and ordinary sequences. Its baseline
records three graph/media losses and two compound Paste refusals. Focused
candidate comparisons pass 60 lossless master frames, 20 paused preview requests,
five audition/master audio bodies and five command/history/project cases.
Maximum error is below 0.494 RGB16 code, 0.501 PCM16 code and one PCM24 LSB,
within unchanged two-code RGB16 and one-code PCM16/PCM24 limits. An explicitly
hashed bold Windows face supplies the title witness: solid white coverage,
position and exact stored text/parameters are checked separately from background
color math; its bounded glyph region is excluded from that color comparison.

This test exposed a separate planner bug: a lone bottom-clip grade occupied the
worker's shared post-composition fields. It consequently graded the upper clip.
The existing bottom-clip prepass now also runs when two or more layers are
visible. Prepared effects are suppressed from the final composition fields;
ordinary single-visible clips keep the fast path. Parent compound effects still
apply to the complete child picture. The no-clipboard reproduction separates
this renderer defect from clipboard copying.

Direct waveform preparation uses a narrowly validated `NESTPEAK` terminator for
one direct leaf plus its exact neutral wrapper. It streams the existing decoder
and effect history in five-second blocks, applies the existing leaf envelope,
and reduces stereo maxima into the same floor partitions. It pads/truncates to
the authored body and retains float headroom. No full-body RF64 files are made
for that route. Compound `NESTCOMMIT`/`NESTENV` and the direct cached-bus PCM
reference remain unchanged; unsupported streamed trees explicitly refuse.

The focused worker protocol gate passes 16 numerical cases and 11 coded refusals,
including 1/600/25,567/65,536 cells, a real block seam, cells outnumbering samples,
headroom/fades, EOF padding and truncation. Streamed peak bytes match the untouched
cached-bus path. All 34 direct processed-waveform and 24 nested cases pass the
unchanged 2e-6 peak bound; direct maximum error is 3.73e-9 and retained PCM differs
by at most one code. Stop and supersede cancel after a genuine completed
240,000-frame DSP block, join in 0.141 seconds, remove owned workers/cache and
partial outputs, and permit a fresh independently checked request. Protocol
refusals preserve accepted cache data and recover in the same worker.

Cold preparation still processes the complete clip; distant-origin decoding,
reverse prefix work and complete-history audition/export caches remain. This
update introduces no codec, color converter, export or native-presenter change.
The `1BD1` ordinary 4K baseline retained above belongs to the preceding published
binary: its two-frame lateness gate fails. Component tests establish neither
zero-drop/fullscreen 4K, full 21-minute cadence, sustained compound 4K60 nor
physical speaker/display alignment.

The combined native candidate is `C6D2E44B` with worker `AA40B96C`. Its actual
Windows editor was checked against disposable copies of the regular 1080p60
project. Copy/Paste at frame 3599 changes one 3600-frame clip into two clips with
duration 7199; one Undo restores the original and one Redo restores the paste.
Fit shows both mapped thumbnail strips and fine processed waveforms. Ruler seek
to frame 1786 aligns Program time `00:00:29:46`, its picture, marker and updated
histogram/parade/luma. Playback advances pictures and shows active stereo meters
on the V1 embedded-audio mixer; Mute silences them, Unmute restores them, and
Stop pauses with zero output. Start restores the nonblank first frame. Only the
disposable project was saved and its window closed.

On the unchanged full 76,701-frame private project, Fit completes with 25,567
processed peak cells and 23 mapped thumbnails. The waveform bytes exactly match
the preceding cached-bus receipt. Late seek to frame 72,497 aligns changed
picture/scopes with `00:20:08:17`; End shows the source's black last frame at
`00:21:18:20`, and Start restores frame zero and populated scopes. No RF64
intermediate remains in this direct-waveform session. These are functional
checks alongside background regressions, with no new cadence or physical A/V
synchronization claim.

The fresh combined Windows build and complete `tests/windows.ps1` suite pass on
this exact application/worker pair: 153 saved application facts plus three
native-drop checks, 757 reported control outcomes with all four dock overlap
checks, and the real Windows media/Unicode and coded-failure paths. The root
clipboard oracle passes all 11 cases/59 checks; all five independent authored
graph/picture/PCM cases pass on the final application. Direct 34, nested 24 and
streamed 16 numerical/11 coded-refusal waveform gates pass, alongside the
existing GPU HDR, frame identity, retimed timeline bitmaps, audio history,
project/recovery isolation and export cancellation checks. No expected outputs
or numerical limits were rebaselined.

The checked native executable, native DLLs and worker were published in the
Genesis root folder. Existing loaded images were preserved without terminating
user windows; protected projects and both media inputs keep their original
hashes. The MM-AIR runtime manifest, fonts and SDK/worker pins remain unchanged,
with no separate Genesis FFmpeg executable/DLL bundle.

The [sanitized checkpoint bundle](../archive/clip-content-streamed-waveforms-2026-10-10.tar.gz)
contains maintained and indexed source hashes, the complete build/Windows logs,
focused and final receipts, raw native profile/strip metadata, and the preceding
4K lateness failure. Every archive member is verified after writing. Media,
personal projects, pixel buffers, executables and codec DLLs are excluded. This
checkpoint is accepted for its stated fixes; broader professional editing and
sustained 4K60 acceptance remain open.

## Locked editing and playback reserve experiments on 2026-10-10

New safety checks refuse locked Lift, Ripple Delete and track removal while
preserving project bytes, selection, dirty/revision state and full Undo/Redo
branches. The seven-case/29-check fixture passes in Windows native, Linux native
and the AIR interpreter. A disposable native 1080p project also verifies painted
and keyboard refusal paths, unlocked Lift/Ripple and Undo.

The separate 9676 private window check covers Fit thumbnails/processed waveforms,
scrubbed Program time/picture and histogram/RGB/luma scopes, stereo audio, live
gain/pan edits, Mute/Unmute, clip-boundary playback, Source audition, Stop, both
frame-zero rewinds and an unchanged saved project hash. It does not establish
authored EOF or full-project professional acceptance.

Ordered preview windows pass the focused retained-worker and socket/FIFO gates,
but their three-picture native timing run still fails the existing two-frame
lateness gate. That build remains private. The subsequent eight-picture reserve
and recovery checkpoint is recorded below. Existing 757 controls and 153 application plus three native-drop
expected facts remain unchanged. See [exact evidence and limits](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md).

## Native playback reserve and recovery on 2026-10-10

Application `1A49B8AF32B9A9169DFCDEBB78D4F523BF742C4C34A006F90551C2B8251EB4B6`
and unchanged worker `AA40B96C631C82CFC834D027678E95A00BD8D5F61DB54F15E7C7ECEFCF74228C`
pass the coherent `cadence-reserve-gain` Windows gate, native editing/export,
exact-binary cadence, publication and fresh installed-root readiness checks.

| Gate | Current evidence |
|---|---|
| Complete Windows release suite | Exit zero; 757 control outcomes across four tabs, 153 application facts plus three native-drop checks, and existing picture/audio/project/export gates |
| Actual reserve and ownership | Fixed eight total owned/reserved pictures; producer windows/FIFO each at most two. Readiness needs actual consecutive pictures, not issued requests. Queue model 20 cases/303 checks; clock 18/3,329 on Windows and Linux; the earlier 17/3,326 interpreter proof remains separate |
| Producer/FIFO and profile schema | Persistent producer eight cases/228 checks; socket FIFO eight/93; cache eight/2,527, including all original profile fields and seven appended request/credit descriptors |
| Destructive edit safety | Seven cases/29 checks on Windows, Linux and the interpreter; locked Lift/Ripple/removal refusals preserve complete document/history state |
| PCM completion and retirement | Three scenarios with 2.4 million exact quantized source-PCM comparisons; completion before GUI receipt, in-flight cancellation and correct same-path reuse. These are headless ownership proofs, not physical sound checks |
| Native 1080p editing | Two fitted clips, 24 mapped thumbnail rows, 1,199/1,200 processed waveform points; live Gain/Pan, Mute/Unmute, natural EOF, independent Source, scrubbed time/picture/scopes, native Open Cancel held over two seconds, locked refusals, Split/Undo/Redo and authored-content Save/Reopen |
| Native export and retry | 1,032 clips/8,192 keys; cancel 240-frame export at observed 29%, encoder exits while preview remains alive, no final/partial/signals. Twelve-frame retry independently checks title/grade/background and AAC correlation 0.9999758635 with no padding; native Save/Reopen preserves the authored graph |
| Native 4K-source cadence | Raw 133.8901633 s; steady 132.1706172 s, 7,923 changed pictures at 59.9376788/s. Zero steady repeats, skips, jump above one, backward/early pictures, lateness above two frames, drains or overwrites; gaps median/p95/max 16.67895/17.4692/24.1018 ms |
| Installed root | Publication passes, old loaded images/user processes preserved, original assets/runtime unchanged. Fresh root opens the 76,701-frame project paused with both pictures nonblank, whole Fit, 23 mapped bitmaps, 25,567 processed peak cells and populated histogram/RGB/luma scopes |

The cadence analyzer and fixed first-one-second/final-half-second exclusions are
unchanged. The raw epoch retains two frame-zero repeats, two startup drains and a
171.3431 ms maximum gap. The prepared steady reserve has median six and p95 seven;
owned plus reserved never exceeds eight. Native Stop silences output and retains
the picture; Start restores nonblank frame zero. This measures ordinary maximized
480x270 fitted monitors from a single AV1/PQ 59.94-fps source, not fullscreen,
whole five-minute or compound 4K60, independent pixels for every presentation,
physical A/V synchronization or complete professional editing.

Earlier failed runs, the capped incomplete 8892 attempt, the private qualified
retry and BDF3's live-Gain failure remain retained. BDF3's initiating producer-exit
cause is still unknown; passing recovery tests do not establish that cause.
The [validation record](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md) binds exact
receipts and restrictions. The [sanitized archive](../archive/native-playback-reserve-2026-10-10.tar.gz)
preserves those receipts and staged source; its digest is recorded in the archive
receipt and publication commit.

## Linked lanes and loaded audio preflight on 2026-10-10

V-only clips show pictures/bitmaps and A clips show processed waveform peaks;
paired video imports contribute sound exactly once. Selecting V routes both
Audio and Properties audio controls to its A mate. Group retains existing mates;
paired static Rate/Reverse, moves, trims, cuts, Slip, Roll/Slide and clipboard
edits commit once or refuse atomically. Multi-lane edits that would desynchronize
an unselected follower refuse with `GA_LINKED_RANGE`; independent linked Speed
filter/key edits refuse with `GA_LINKED_SPEED`. The focused shared-control/model
fixture passes 28 cases / 784 checks, including pointer actions, full graph and
Undo/Redo comparisons, pure-video control omission and offline/disabled audio
control availability. No desktop acceptance is claimed by that fixture.

Native migration is in-memory and requires Save; an unsafe conversion leaves
Open available with the original graph and a diagnostic. New placement respects
A-lane mixer intent. See [linked-media contracts](LINKED_MEDIA_WINDOWS_2026-10-10.md)
for stream masks, source routing, clipboard and explicit limits.

Contributing clip Speed curves, curves on enabled audio-filter instances and clip
Pan curves in front of a stateful audio filter report
`GA_AUDIO_AUTOMATION_UNSUPPORTED`; this is explicit refusal, not animated DSP
support. Since R22, clip Pan curves over memoryless chains (Gain/Pan/Volume/Mute
filters only) render exactly as a per-sample output balance; see the
[R22 checkpoint](PRO_EDITING_R22_2026-10-13.md). Audible offline leaves, including compound descendants and original
Source audition, report `GA_AUDIO_SOURCE_OFFLINE`. Supported clip Gain/Fade curves
retain their existing processing. Disabled clips, muted or sequence-local
solo-excluded lanes, inactive/unreferenced sequences, no-audio or video-only
branches, and half-open nonoverlap remain noncontributing. Static held clips are
silent, but an enabled stored Speed curve still refuses: it could make a held
clip progress. Disabled filter curves stay dormant. Hidden/locked tracks remain
audible; scalar zero gain is not a bypass for positive Gain keys. Compound
preflight includes the selected child history needed by cached DSP. Direct peak
failures retain `GA_AUDIO_CLIP_ENV` and the underlying cause.

The focused 61-case background oracle compares 1,536,000 PCM16 values (maximum
0.735521 code at the unchanged one-code limit) and 384,000 independently decoded
lossless-master values (maximum normalized error 1.207935e-7 at the unchanged
2e-6 limit). Masked picture branches, source audition, refusal recovery, owned
cache/partial cleanup and preservation of external sidecars are included. The
prechange silent-loss failure and later fixture-authoring corrections remain
retained. These are focused receipts, not native-device or desktop acceptance.

Audio-plan failure stops the device before the next paint; export rejects the
plan before acquiring output/cleanup ownership. No codec, DSP, color or worker
change is introduced, and Genesis continues to use MM-AIR's runtime without its
own FFmpeg executable/DLL bundle.

The shared preview channel also has a focused backpressure repair: separate
credit-poll/frame-write deadlines preserve reliable framing within a bounded
two-second window-message budget. Four real-TCP cases / 18 checks and four exact
wire oracles pass, including a 200 ms write stall, resumable no-credit expiry and
fatal partial-frame refusal. The earlier BDF3 initiating cause remains unknown;
these component checks do not qualify the changed application. See the
[retained failure and protocol proof](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md#linked-lane-background-follow-up).

The transport candidate passed media/audio fixtures but failed the existing
Nudge success-message contract. The fresh contract candidate restores `nudged`;
paired edit/refusal behavior is unchanged. A separate 757-control/four-tab tail
passes; the coherent final result is recorded below.

The final `linked-lanes-contract-final` build and full BackgroundOnly Windows
gate pass; the verified application `06af1ab848cf1225c3bbb7f9896dd6dbdfa3148df95b8ed9f5241c9b20ca687b` is published with unchanged AA40
worker/runtime. Acceptance includes linked controls 28/784, channel 4/18 plus
four exact TCP wire oracles, retained preview 8/229, track scrolling 8/83,
153 headless facts plus three native-drop checks, 757 four-tab control outcomes,
the 61-case PCM/master preflight and exact 181-second / 37-chunk continuity.

A separate three-case / 22-check real-1080p shared-source helper renders V-only
tiles/A peaks and changing Program/scopes at frames 0, 90 and 179. Inspected
background surfaces are not desktop or speaker tests. The initial SDK driver
path error was repaired before launch without changing the candidate, and all
failed gate/fixture/transport evidence remains retained. See the
[complete validation scope](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md#linked-lane-background-follow-up).

Publication preserves protected originals and terminates no user application.
Desktop clipboard, live audio/device clocks and sustained cadence remain
deferred; older 1A49 timing cannot qualify this binary. Complete professional
editing acceptance remains open. The
[1,287-member immutable bundle](../archive/linked-media-windows-2026-10-10.tar.gz)
has SHA256 `b822ed35284be3961abead18381aed7f23bb55aaafae2701d28c33d73ecd87bb`; the
[receipt](validation/linked-media-windows-2026-10-10.json) binds its exact scope.
