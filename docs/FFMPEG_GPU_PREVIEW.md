# Native GPU decode and the shared MM-AIR media runtime

Genesis calls the codec/filter libraries from its native C compositor. It does not
launch `ffmpeg.exe` to play or compose a frame. Windows setup now installs one
versioned native library set under `MM-AIR/share/media`, reuses MM-AIR's existing
`ffmpeg.exe`/`ffprobe.exe` for metadata and diagnostic tools, and writes locations
to `genesis-media-runtime.txt`. Genesis's application folder contains neither
FFmpeg executable nor codec DLLs. The pinned SDK remains a build dependency.

Use `setup-windows.ps1 -MmAirRoot C:\path\to\MM-Air` for another installation.
`MM_AIR_ROOT` supplies the same default. The three UTF-8 config lines are the
native DLL directory, FFmpeg tool and ffprobe tool. Native startup can override
the first line with `GENESIS_FFMPEG_RUNTIME`. Relocating MM-AIR requires refreshing
this location file; missing libraries fail with `GA_MEDIA_RUNTIME`, and a major
ABI mismatch fails with `GA_MEDIA_ABI`.

MM-AIR's current installed command-line build is static. It cannot supply DLL
exports to the compositor, so the shared directory holds the existing pinned
native library build. Setup does not overwrite MM-AIR's tools. A conflicting
library in that versioned directory is refused. MSVC import libraries are built
from the pinned DLL exports: the supplied GNU archives bypassed delay loading.
The worker therefore selects and loads the shared runtime before any codec call.

## FFmpeg source examined

The source review used FFmpeg commit
[`361174e5ea6bd65e34554afa1d098dda2a9bcbba`](https://github.com/FFmpeg/FFmpeg/commit/361174e5ea6bd65e34554afa1d098dda2a9bcbba):

- [Vulkan AV1 decoding](https://github.com/FFmpeg/FFmpeg/blob/361174e5ea6bd65e34554afa1d098dda2a9bcbba/libavcodec/vulkan_av1.c).
- [libplacebo GPU rendering](https://github.com/FFmpeg/FFmpeg/blob/361174e5ea6bd65e34554afa1d098dda2a9bcbba/libavfilter/vf_libplacebo.c), including scaling and HDR conversion.
- [D3D11 scaling](https://github.com/FFmpeg/FFmpeg/blob/361174e5ea6bd65e34554afa1d098dda2a9bcbba/libavfilter/vf_scale_d3d11.c).
- [OpenCL hardware mapping](https://github.com/FFmpeg/FFmpeg/blob/361174e5ea6bd65e34554afa1d098dda2a9bcbba/libavutil/hwcontext_opencl.c) and [OpenCL tone mapping](https://github.com/FFmpeg/FFmpeg/blob/361174e5ea6bd65e34554afa1d098dda2a9bcbba/libavfilter/vf_tonemap_opencl.c).

The native decoder now admits `GENESIS_VIDEO_BACKEND=vulkan`, using libavcodec's
Vulkan hardware device and exact matching hardware pixel format. `auto` and
`d3d11` retain the existing Windows default; `software` requests the software
decoder. `GENESIS_SOFTWARE_DECODE` still overrides hardware selection. Unsupported
hardware configurations retain software fallback; invalid backend names are
reported with `GA_VIDEO_BACKEND`. This is native library execution, using the
same frame selection, EOF drain, 16-bit/FP32 color transform and compositor.

Vulkan is an additional tested backend, not a claimed speed improvement. The
default stays D3D11. Vulkan retains full-resolution readback and CPU HDR conversion;
the D3D11 preview path now performs selected-frame GPU color conversion and scaling.

## Native D3D11 HDR preview

`windows/hdr-preview.c` and its embedded `hdr-preview.hlsl` operate directly on
the selected decoded P010 texture. Compute converts limited-range BT.2020 YUV,
resamples encoded RGB, applies PQ/100-nit linearization, BT.2020-to-709 primaries,
Hable and display-referred Rec.709 gamma. The output uses FP32 math with 16-bit
channel quantization. Only the fitted preview-sized float buffer crosses back
to the CPU; skipped decode pictures stay on the GPU.

The transform follows the existing zscale/tonemap chain. That chain clears source
HDR metadata while changing transfer, so its linear-frame peak fallback is 10.
FFmpeg's RGB desaturation uses the sum of channels; zimg's display-referred
Rec.709 output uses Rec.1886 gamma. These details explain the darker default
libplacebo appearance. Extended-range PQ and the Hable rational limit stay finite,
including range excursions that previously turned limiting white black.

The fast path requires D3D11, P010, PQ, BT.2020 nonconstant luminance, limited
range and left/unspecified chroma siting. Both fitted dimensions must be smaller
than the source, at least two pixels, with at most 32:1 shrink in each dimension.
Other formats, Vulkan/software frames, native-size renders outside the qualified
candidate path below, and explicit HDR masters use the reference CPU graph.
Every application export also passes
`--reference-color`, preserving that graph for downscaled SDR sequences even
when `GENESIS_GPU_PREVIEW=1` is set. Resource/shader failure reports
`GA_GPU_COLOR` and falls back. `GENESIS_GPU_PREVIEW=0` disables this preview path.
The Windows system shader compiler is loaded from System32; Genesis bundles no
shader-compiler DLL or separate FFmpeg runtime.

Color and spatial resampling have separate acceptance evidence. 512 generated
uniform color-patch samples agree within 0.016/255; all pixels of eight PQ range
excursions agree within 0.004/255. The supplied footage's first twelve 640x360
pictures average roughly 0.216/255 RGB difference, with p99 around 1.23 and
maximum edge differences 15–24/255. Later selected frames have larger isolated
edge differences. The preview scaler is therefore not bit-identical to zscale;
master transforms and explicit HDR output retain exact reference fallback.

## Measurements and rejected shortcuts

On an RTX 5080 / driver 617.14, the supplied 3840x2160, 59.94 AV1/PQ clip processed
1200 frames with FFmpeg's Vulkan decoder and libplacebo Hable conversion to
Rec.709, followed by 16-bit RGBA readback:

| Output | Elapsed processing | Frames/second |
|---|---:|---:|
| 1280x720 preview | 3.442 s | 348.63 |
| 3840x2160 picture | 9.504 s | 126.26 |

These command-line pipeline measurements include startup and readback; they
exclude Genesis's request protocol, effects, retained canvas, audio and native
presentation. They establish GPU headroom, not completed editor playback at
60 fps. No fullscreen window was used. Reproduce the pipeline with MM-AIR's
existing tool; change the two dimensions to 3840/2160 for native pictures:

```powershell
& C:\MM-Air\ffmpeg.exe -nostdin -hide_banner -init_hw_device vulkan=vk:0 `
  -filter_hw_device vk -hwaccel vulkan -hwaccel_output_format vulkan -i LOCAL_CLIP.mp4 `
  -vf 'libplacebo=w=1280:h=720:format=rgba64le:colorspace=gbr:color_primaries=bt709:color_trc=bt709:range=full:tonemapping=hable:peak_detect=0,hwdownload,format=rgba64le' `
  -an -frames:v 1200 -benchmark -f null -
```

The default libplacebo output does not match Genesis's existing HDR appearance:
frame zero differed by 41.11 mean RGB channel units at 8-bit display precision.
It is not enabled as a substitute for the current color path. GPU color work
must resolve that difference and preserve preview/master agreement.

The stock D3D11 scaler failed texture allocation on this GPU. A native preview
adaptation with individual render-target textures could resize P010, but matching
PQ-to-PQ processing was reported unsupported and produced black. Forcing matching
Rec.709 processor labels returned pictures but changed highlight/detail pixels
by as much as 181/255 across ten source frames. One twenty-second editor diagnostic
also delivered 45.75 pictures/s versus the current 53.65 baseline. That adaptation
is rejected, preserved with source/reproduction/results in
`archive/ffmpeg-d3d11-preview-probe-2026-10-03.tar.gz`, and absent from production.

Direct FFmpeg D3D11/OpenCL frame mapping admits NV12 rather than the P010 required
by this clip; it is not a ready HDR interoperability shortcut.

A custom libplacebo OUTPUT hook reproducing the existing color math reduced the
first twelve 1280x720 frames' mean difference to 0.989/255, but p99 was 11.156/255 and
maximum 102.105/255. Linear-domain resampling was worse. This shortcut is also
rejected. Minimal sources, commands and measurements are preserved in
`archive/hdr-gpu-color-probes-2026-10-09.tar.gz`; raw pixel buffers and binaries
are excluded.

## Verification

`tests/shared_media_runtime.py` checks six fresh-process cases from an isolated
folder containing only the worker and OpenCL loader. It verifies native delayed
imports, a valid shared runtime, Unicode installation/runtime paths, the explicit
runtime override, missing libraries, malformed UTF-8 and missing configuration.
The standard Windows gate includes it when a shared runtime is configured.

`tests/video_transfer.py --vulkan` exercises generated NV12/P010/PQ/HLG media,
fractional timestamps, B frames, seek/skip/EOF/rewind and software fallback using
the unchanged color path. A separate supplied-HDR check also compares actual
RGBA and FP32 pictures between D3D11 and Vulkan. The combined run passes 504
exact picture/reference comparisons across six hardware cases, with only the
selected frames read back. The full Windows gate, 4K ProRes/portrait/multicam
gate and retained-precision/HDR/long-audio gate pass with the shared runtime.

A fresh twenty-second ordinary-editor diagnostic on the supplied 4K clip delivers
1078 pictures (53.90/s), with 11.63 ms median picture delay, 27.87 ms p95, no early
pictures and no observed audio underruns. It uses the real silent device,
asynchronous preparation and retained 1600x980 paint, excluding native presentation
and physical speaker latency. The preceding baseline delivered 53.65/s. This is
consistent with preserving current playback behavior, not a new 60 fps result.

The initial native compute preview and consecutive-future-picture queue candidate
delivered 1133 pictures in 20 seconds (56.65/s), with 11.62 ms median picture delay,
25.03 ms p95, 5.83 ms median program preparation and 3.49 ms project-snapshot work.
It observed no early pictures or audio underruns and held at most two prepared
pictures. This uses the same silent native device and retained-paint scope above;
native presentation and speaker latency remain excluded. Per-frame request work
was the next measured bottleneck. This is not a completed interactive 4K60 result.

Retaining the project snapshot and sending small frame/time commands reduces
median snapshot work to 0.13 ms. The twenty-second candidate delivers 59.25
pictures/s with 10.71/16.46 ms median/p95 picture delay. A ninety-second supplied
4K run delivers 5,241 pictures (58.23/s; 58.25/s during seconds 1–89), with
10.75/16.83 ms median/p95 delay, at most two prepared frames, no early pictures
or observed audio underruns, 18 audio boundaries and -1.49 ms device-clock drift.
Four large gaps coincide with 89–124 ms native program renders while snapshot
work stays near 0.11 ms; worst observed picture gap is 110.62 ms and maximum
picture lateness 128.83 ms. Those renderer/decoder tails remain open. These runs
include normal retained paint and silent device playback, with native display
presentation and speaker latency excluded.

`tests/hdr_preview.py --require-gpu` requires the hardware path locally and checks
color patches, range excursions, selected small readbacks, finite/opaque pixels,
seek/skip/EOF/rewind, odd-canvas letterbox edges and exact native-size/HDR master
fallback. The ordinary Windows gate permits exact CPU fallback on unsupported
hardware. `tests/video_transfer.py` explicitly selects the reference color path
to isolate decoder/readback equivalence from the new spatial preview kernel.
The candidate also passes 4K ProRes fine-detail/exact PCM length, portrait/multicam,
1024 distinct 16-bit master values and PQ title/HEVC metadata checks.

## Native-window measurements on 2026-10-09

The loopback-pixel candidate uses a bounded packet with frame identity checks instead of
writing the final Program bitmap to disk. At that checkpoint, float intermediate
passes and exports retained their existing paths; the later GPU snapshot stage
below removes internal FP32 group/filter disk passes. A twenty-second retained-painter/device run delivered
1,189 pictures (59.45/s), with 4.53/16.05 ms median/p95 program preparation.
This excludes native display presentation.

The same candidate was then measured in the ordinary maximized Windows editor
with the supplied 3840×2160, 59.94 fps AV1/PQ source and its audio. After a one-second
warmup, the Scopes tab delivered 2,970 changed pictures over 52.87 seconds
(56.17/s); the Audio tab delivered 6,190 over 110.54 seconds (55.99/s).
Median/p95 picture gaps were 16.70/33.25 ms and 16.70/33.27 ms respectively.
Both intervals had no observed drained audio queues or early pictures, with at
most two prepared frames. Device-clock drift was -0.86 ms and -1.85 ms.
The rates count changed pictures rather than repeated window presentations.
Physical speaker latency and display scanout are outside this measurement.

Paused ruler scrubbing changed the Program picture and timecode to two seconds;
Start restored frame zero with a visible picture. Timeline filmstrip bitmaps,
live stereo meters, histogram, spatial RGB parade and luma waveform were visible.
The user's project file retained its original SHA-256 after these checks.

These results establish working native controls and expose remaining redraw
pressure; they do not establish sustained interactive 4K60. A subsequent change
limits clock/meter-only redraws while keeping new pictures and input immediate;
the first native Audio-tab run delivered 3,540 changed pictures over 64.31 seconds
(55.03/s) at 2560×1316, with no duplicate presentations and one-frame picture
lateness throughout the measured interval. There were no observed drained queues
or early pictures. This improves stale-picture delay, while throughput remains
below 4K60; the viewport differs from the earlier run and is not an exact paired
comparison.

The final Audio-tab candidate retains pending meter changes, skips unchanged
Source painting and repaints only the output-meter region when the remaining
Audio controls are unchanged. Its 2560×1316 native interval delivers 4,496 distinct
pictures over 79.20 seconds (56.76/s), with 16.58/28.37 ms median/p95 picture gaps
and a 41.33 ms maximum gap. Median/p95 picture lateness after presentation is zero;
the maximum is one frame (16.68 ms). No early pictures or drained audio queues are
observed, and device-clock drift is -1.33 ms. Median painting is 1.42 ms, compared
with 7.47 ms in the preceding held-Source candidate at the same viewport. Native
presentation takes 5.06 ms median. This is a sequential comparison, not an
alternating paired benchmark. Stop holds the picture and clears the meters; Start
restores visible frame zero. The original project bytes remain unchanged.

The measured application SHA-256 is
`6BE80865F46091CC92605E4F0A0180479DDB1A143C85934D3EAD2E59B8BDDE8A`;
the worker is `66EE15B507E15EEC67E69999411654C4893A0F9FF3EA8ACCBD1224CC5B62FD9C`.
Retained painting is independently compared byte for byte with complete painting
in 32 cases/656 checks, including scrolled meters, narrow/short windows, Source
replacement and all three UI scales. The final source also fixes the status bar's
expanded erasure at short-window track boundaries and clips narrow timecode text
to its refreshed monitor band; these two subsequent paint fixes have pixel-exact
acceptance, while the timing above belongs to the measured application hash.
Sustained native 4K60 and complex effect-stack throughput remain open.

A five-minute transport fixture reached
all 18,000 exact picture identities but required one worker restart, so that run
failed the no-restart requirement. Two subsequent five-minute diagnostic runs each
passed all 18,000 identities in one worker with zero refusals/restarts; observed
port reuse rules out deterministic exhaustion in those runs. The original failure
remains unexplained and retained. `GA_PROGRAM_RECOVERY` now records a retry's
original cause, child process identity and request number. Fullscreen 4K remains deferred.

The window measurement is opt-in through `GENESIS_WINDOW_PROFILE`. Use
`tests/window_timing.py PROFILE.tsv --require-active --report REPORT.json` to
check frame identity, prepared-frame limits, timing and audio-clock observations.
The TSV includes document/media revisions and viewport geometry so edits and
resizes can be separated from steady playback intervals.

For explicit long transport acceptance, set `GENESIS_TEST_PREVIEW_INPUT=1` and run
`genesis-preview-input.exe FRESH_SCRATCH genesis-worker-wrapper.exe 18000`.
The paced fixture checks every picture at 60 requests/second and requires one
worker with no refusal. It writes `preview-lifetime-tests.json`, port receipts and
a Winsock error receipt when available. Routine Windows gates retain the shorter
fault suite; this five-minute check is separate.

## Native window recovery on 2026-10-10

Three successive native Audio-tab measurements use the same 4K/59.94 AV1/PQ
source, compositor, stereo output device, 480x270 fitted monitors and maximized
2560x1316 editor canvas. Every row records request identity, completed packets
and both prepared frame positions. Reports are flushed after closing each
isolated measurement process, and exclude one second of playback warmup.

| Queue behavior | Measured seconds | Distinct pictures/s | Skipped positions | Picture gap p95 |
|---|---:|---:|---:|---:|
| Existing future requests | 83.13 | 55.76 | 347 | 30.90 ms |
| One outstanding future request | 101.28 | 56.97 | 301 | 24.69 ms |
| Also recover a one-frame delay at the current frame | 131.88 | 59.87 | 8 | 18.26 ms |

The baseline loses 283 delivered frames while two future pictures already fill
the queue, 63 requested frames have no receipt, and one stored frame is
superseded when two become due. Reserving one outstanding future decode removes
the capacity and undelivered losses. Small late completions then reveal a
separate problem: catch-up jumps directly to the future lead. Recovering a
one-frame delay at the current wanted frame preserves nearly the full cadence.
Larger delays still use the existing bounded catch-up and avoid a decode backlog.

The final interval has 7,897 distinct pictures and 7,899 successful presentations.
All 7,896 warm completion events match receipts, with zero packet overwrites,
mapping errors, or full queues containing another outstanding request. Its eight
omissions are two intentional four-frame catch-up jumps following native
presentation/event-wait delays. Median after-presentation lateness is 16.68 ms,
p95 33.37 ms, maximum 83.42 ms; native presentation frequently crosses an audio
frame boundary. Median paint/presentation times are 1.24/14.19 ms. The device
interval differs by -2.19 ms over the measured run, with no observed drained
queues or early pictures. Stop silences output; Start restores nonblank frame zero.
The original project file is unchanged.

This establishes near-full input cadence for the supplied source and ordinary
editor view. Zero-drop playback, physical speaker/display alignment, complex
effect-stack throughput and fullscreen 4K remain open. The measured recovery
application SHA256 is `BF975EEE6D5EBEAD0EC3775EFA2E3BB7A949DE440A013F35FAD71320DC957F6B`;
the worker is `66EE15B507E15EEC67E69999411654C4893A0F9FF3EA8ACCBD1224CC5B62FD9C`.
The subsequent combined application adds the shared trim safeguards and skips
request publication on a newly handled preview error; its acceptance is separate.

`tests/window_loss.py PROFILE.tsv --report REPORT.json` reproduces omission
categories from actual request-to-frame mappings, including source mode, and
checks packet/receipt conservation. IDs are not inferred from numeric gaps.
The loss reader has four independent synthetic tests; the timing reader retains
compatibility with prior 32-column profiles and has four tests. Queue acceptance
passes nine native cases/77 checks. Raw numeric profiles, hashes and sanitized
reports are retained in `archive/trim-playback-2026-10-10.tar.gz`.

The combined Windows build and full gate passed with application SHA256
`0878CC77DE9F626FB4D08BAD0334B37C58F78CA9687BA1A04A002190FB30BB8F`,
including native audio continuity, project safety, preview/master pixels,
trim history, frame-zero rewind and timeline bitmap identities. A final bounded
main-only change clears error deduplication after recovery, allowing an identical
generation-zero channel failure to be reported again. The final application
SHA256 is `D8CAD5EC8CF0B2100134EAA9C13BD1F38C2292D780C0041D2DC2DF32ADAB829C`;
its demo render smoke and all ten native stream cases passed after that change.
The full media suite was not repeated after this reset. The archive distinguishes
these applications from the measured playback candidate.

The final root executable was launched with the supplied project after publication.
Its native-window check showed advancing Program playback with live stereo meters,
silent Stop, a nonblank frame-zero Start, timeline seeks at `00:00:02:49` and
`00:00:07:14`, corresponding Program pictures/timecodes, and changing histogram,
RGB parade and luma waveform. Filmstrip bitmaps remained visible; Source stayed
at zero while Program moved. Six shared-runtime process cases also passed against
the published worker, with no separate Genesis codec bundle. The original project
SHA256 stayed `480D82E310BA6F231FAB2C0C0DB9945DAB193D63073CB63FE053019A13AEB143`.

## GPU picture snapshots on 2026-10-10

Compound groups and ordered video-filter passes now retain immutable FP32 GPU
pictures between passes. The AIR plan remains a pure description; executor-side
lowering assigns a monotonically increasing epoch per physical worker and IDs to
internal outputs. `PICBEGIN` starts an epoch, a `FLOAT` pass can store to
`GPU:<epoch>:<id>`, and later passes consume exact-canvas `GPU`, transparent-fit
`GPUDIM`, or black-flattening `GPUOPAQUE` references. `PICDROP` follows the last
input use, while `PICABORT`, failures, terminal preview/encoder/external FLOAT
output and shutdown release remaining snapshots. IDs cannot be redefined after
Drop, and old epochs cannot alias new same-numbered IDs.

Snapshot buffers remain separate from the four retained canvas slots, so changing
canvas dimensions or evicting a canvas cannot overwrite a sibling/group picture.
Both use one prospective 4 GiB allocation budget. Store-time finite/alpha
validation returns a four-byte status word; internal pictures avoid full RGBA
readback, host upload and scratch-file writes. Native child canvases and existing
spatial/filter semantics remain conservative. Final preview readback and actual
encoder output retain their format and precision contracts. This uses OpenCL
through the existing native compositor and the shared MM-AIR codec runtime.

The native lifecycle oracle passes 23,627 checks, including injected allocation
failures, prospective budget refusal, finite/alpha rejection, LRU survival and
zero live objects at shutdown. The independent protocol oracle passes twenty
cases / 92,302 checks, including stale references, same-size siblings,
noncommutative/duplicate filters, nonlinear group filtering, portrait fit and
actual preview/encoder pixels. The full isolated Windows suite and its compound,
ordered-filter, filmstrip, audio and control gates pass. Source-boundary acceptance
is a separate fresh 130-case / 664-check run against the same final app/worker.

A short sequential headless benchmark uses native 3840x2160 root and child
canvases, a 1280x720 ordinary-editor canvas and fitted 480x270 monitors:

| Measurement | Disk intermediates | GPU snapshot prototype |
|---|---:|---:|
| Program median / p90 latency | 788.89 / 1006.32 ms | 66.50 / 94.37 ms |
| Whole serial median / p90 | 799.46 / 1015.45 ms | 72.22 / 100.12 ms |
| Reciprocal whole serial mean | 1.175 pictures/s | 12.928 pictures/s |
| Observed group files | Two at 132,710,400 bytes each | None |

The command is `profile-preview REPORT PROJECT 1280 720 12`: three warmup
pictures precede twelve measured serial pictures. `12` is not a duration.
This excludes audio, native display presentation and paced sustained playback;
file observation is not a physical disk-I/O benchmark. No fullscreen window was
used. The supplied source and protected original project retained their hashes.
The improvement removes a large transfer bottleneck, but this result remains
far below sustained compound 4K60.

The accepted benchmark app/worker hashes are
`0AE78AD228199D00F415BC0994E82A2444244BA41B3D802B6F04B7560D3D605C` /
`E8354F1845985A9CF12697887FC5DDF48B590277649CF8394492EA4FD216EB73`;
the prototype hashes are
`0ABDFF80F6494BDE8D7AB030A28BF7A04478AA2172ADFD279B9310A06B75F7D4` /
`2DC132F4C39EBE57A4719AB806AAE197F10CCA6216DA8093E6B99E0784CF7856`.
The final integrated app/worker are
`2DD0C3938EDD3DE5C061B91839092179EC016F5F8F1175CCEFD8B1075B892912` /
`C2947D934F00EC9CFA0509F9215015BFE4D19AC3CF814A8C9F2B55B3A62FBEAB`.
They retain the tested GPU implementation and include native audio selection
before resampling, anchored to first decoded PTS after AAC skip/edit handling.
Positive origins insert silence and negative origins skip pre-zero audio; the
[acceptance ledger](CONTROL_COVERAGE.md#gpu-picture-snapshots-and-source-audio-boundaries-on-2026-10-10)
details the independent sample oracles and remaining missing-PTS, discontinuity,
seek-cost and fresh-reverse phase limits. The prototype timings must not be
attributed to this final integrated application.

The [native functional receipt](../archive/native-picture-memory-ui-2026-10-10.json)
records advancing Play with stereo meters, silent Stop, visible frame-zero
rewind and a distant seek with synchronized picture/time/playhead/scopes. It
adds no new sustained native-display or physical-hearing measurement. The
45-entry [checkpoint archive](../archive/picture-memory-audio-boundaries-2026-10-10.tar.gz)
was sanitized and read back against its manifest; SHA-256 is
`fa5a0a08a435dbbc21ade6301ea3fc96c7544e118baa3999e3cc646e807a64b7`. The installed root payload
matched these earlier checkpoint hashes, and a cold ordinary-window launch restored
frame-zero pictures and the compound filmstrip.

## Native 16-bit upload and processed compound waveforms

Even, full-source native canvases can now upload the decoder's existing RGBA64
color-transform result directly. A blocking OpenCL transfer consumes the borrowed
view before the decoder can reuse it, then expands it into the usual FP32 source
slot using the identical `f32(1/65535)` factor. The expansion uses existing budgeted
scratch storage. A native 4K upload falls from 132,710,400 to 66,355,200 bytes;
canvas size, decoder frame selection, reference HDR/color transform and subsequent
compositor math are unchanged. Fitted, odd-sized and spatially incompatible paths
retain the FP32 upload. `GENESIS_NATIVE_U16_UPLOAD=0` explicitly disables the seam.
`GENESIS_GPU_PHASE_LOG` is opt-in local command/decode/upload diagnostics.

The maintained native harness checks every 16-bit code across all three source
slots, immediate host-buffer reuse and resource lifetime. The worker oracle compares
15 native/fitted/odd/RGB/PQ/HLG cases against forced FP32 and software decoding,
checks frame identities and verifies actual fast-path entry. Its optional
`--reference-worker` also compares an accepted older worker. These tests establish
pixel accuracy, not playback cadence.

A short alternating ABBA headless comparison uses the accepted worker
`C2947D934F00EC9CFA0509F9215015BFE4D19AC3CF814A8C9F2B55B3A62FBEAB`
and the upload-only candidate
`B237C452ED9E15F1FBD6BB2764EAE49CE28B28ADE8F14F462616ECBE4537C558`,
with app `2DD0C3938EDD3DE5C061B91839092179EC016F5F8F1175CCEFD8B1075B892912`.
Each of two runs per worker has three warmup and twelve measured pictures, native
3840x2160 compound canvases, fitted 480x270 monitors and a 1280x720 ordinary editor
canvas. Mean whole serial latency is **73.19 to 67.28 ms**, about 8.1% lower;
reciprocal mean throughput is **13.66 to 14.86 pictures/s**. Individual runs vary
substantially. This excludes audio, native presentation and sustained paced playback;
it is not a measurement of the final combined app/worker. Native decode and reference
HDR/color processing remain substantial; sustained compound 4K60 remains unfinished.

Compound waveforms now use `NESTENV` on a complete processed nested stereo bus.
Each bucket takes the maximum absolute channel value in
`[floor(k*N/B), floor((k+1)*N/B))`; empty buckets are zero. Intermediate headroom
above one survives until the painter's display scaling. Peaks cover clip-local
audio after child mixing and authored parent processing, rather than a leaf source
envelope. Changed buses are constructed on the background strip worker and their
exclusive temporary cache is removed only after worker shutdown. Stop and supersede
poll the request markers during pipe waits. Held pictures produce silent peaks
without opening a media worker. Viewport-only requests reuse matching peaks.

The versioned waveform mailbox carries document and media revisions plus clip/time
mapping. Descendant edits retire stale peaks both on import and during painting;
malformed, nonfinite and partial publications are refused without replacing current
cache entries. Headerless legacy data is accepted only for direct-source clips.
At this compound-only checkpoint, flat waveforms retain their source-envelope
behavior. The later direct-waveform checkpoint below replaces that approximation.
Full-history changed compound caches still
have startup and disk costs. See the
[acceptance ledger](CONTROL_COVERAGE.md#compound-waveforms-and-native-upload-on-2026-10-10)
and the [candidate UI receipt](../archive/native-waveform-u16-ui-2026-10-10.json)
for evidence and the exact limits of the cold reload test.

The final integrated root app (`73f8f7da...`) and worker (`4d9dfd6d...`) pass the
complete Windows suite and a subsequent fresh native root reload. Playback audio
meters, Stop, rewind, paused seek/drag, filmstrip/waveform publication and changing
histogram/parade/luma scopes are recorded in the
[root UI receipt](../archive/native-waveform-u16-root-ui-2026-10-10.json).
The test retains fitted 480x270 compound canvases; it does not qualify native
4K60. Full gate evidence and source/binary hashes are preserved in the
[checkpoint bundle](../archive/compound-waveforms-native-upload-2026-10-10.tar.gz).

## Processed direct waveforms and track viewport

Direct-source clips now reuse the existing native processed-audio tree and
`NESTENV` bucket query. A neutral root bus measures the clip's complete authored
stereo body before the final program/device clamp. Gain, pan, supported audio DSP,
trim/rate/reverse and gain/fade history follow playback. The maintained gate
compares independent stereo peaks and uneven retained PCM; the mono control
uses playback's equal-power stereo rematrix. Unsupported audio automation
refuses with a coded error rather than fabricating an envelope.

Strip requests select the visible time range before launching media work and
reuse matching peak caches. Vertical track navigation changes the shared timeline
model used for rendering and pointer dispatch. Neither change adds a new codec
runtime. The accepted `4d9dfd6d...` compositor and shared MM-AIR manifest remain
unchanged. See the [direct-waveform and track acceptance ledger](CONTROL_COVERAGE.md#processed-direct-waveforms-and-vertical-tracks-on-2026-10-10).

Cold changed waveforms still materialize a full audio body. At this historical
direct-waveform checkpoint, `--serve` eagerly initialized OpenCL even for
audio-only work, and native-resolution HDR experiments were private.
The newer candidate below changes those paths. No new sustained native
4K60 or physical audio-latency claim follows from these waveform/viewport checks.

The installed direct-waveform app (`0928f1c3...`) also passes a fresh native check
of Play, embedded-audio mute/unmute, Stop, frame-zero rewind, timeline/monitor
scrubbing and changing fitted scopes. The 26-track test publishes 23 bitmap rows
and 512 processed peaks. See the [UI receipt](../archive/native-direct-tracks-root-ui-2026-10-10.json)
and [sanitized acceptance bundle](../archive/direct-waveforms-vertical-tracks-2026-10-10.tar.gz),
which preserve the initial disabled-control diagnostic failure and passing tail
rerun alongside the unchanged production/media prefix.

## Qualified native HDR candidate on 2026-10-10

The combined candidate app `AD8985B431...` and worker `378685335B...` pass the
full Windows gate as the initial staged build. The later published root guard's
combined acceptance is recorded below. This evidence is separate from
the earlier installed direct-waveform checkpoint and its prefix/tail rerun.
Shared MM-AIR runtime selection and the absence of a separate Genesis FFmpeg
bundle remain unchanged.

`windows/native-hdr.c` and `native-hdr.hlsl` implement a selected-frame RGBA16
preview path for even, full-native-canvas D3D11 P010, limited-range BT.2020
nonconstant-luminance / ST2084 PQ with supported chroma placement. This is not
a replacement for the fitted scaler, SDR/HLG conversion or HDR master graph.
The shader adapts zimg coefficient tables pinned in
[`native-hdr-zimg-provenance.json`](../windows/native-hdr-zimg-provenance.json),
including their FMA evaluation order; the accompanying license is retained.

Qualification requires AVX512/AVX2/FMA3 and checks the exact loaded avutil,
avfilter and swscale reference modules: file fingerprints, loaded images and
retained file handles. An unknown runtime or forced CPU/reference path declines
the shader. Unsupported formats/dimensions, HDR working output and allocation,
resource or readback failures keep reference fallback. The Windows shader
compiler is loaded from System32. No shader-compiler DLL or additional codec
runtime is packaged. `GENESIS_NATIVE_HDR_COLOR=0` disables this native-size
path; `GENESIS_GPU_PREVIEW=0` disables preview acceleration by default.

The maintained gate passes 12 authored qualification/fallback cases. Native
channels differ by at most 1.9999695 u16 codes under the existing five-code
bound; reference, HDR-master, fitted, disabled, CPU, unknown-runtime and fault
paths remain byte-exact. The additional real-source gate selects eight
3840x2160 Costa Rica frames `[0,1,2,100,500,1000,18807,0]`, observes eight
shader entries and compares 265,420,800 channels with the same maximum below
two u16 codes. All values are finite and the source hash is unchanged.
Native-u16/snapshot lifecycle validation separately passes 810,083 checks.

Four private paired headless runs each measure 12 warmed samples with three
warmups, not 12 seconds. Serial native-4K compound pipeline means are
90.304/64.147 ms for the reference pair and 38.356/38.317 ms for the shader
pair. These measurements use 480x270 monitors in a 1280x720 headless painter,
exclude audio/native presentation and do not establish sustained paced playback
or compound 4K60. Their protected inputs and historical baseline are retained.

## Lazy compositor and current native-window scope

Audio-only commands and CPU thumbnail/source-count requests no longer construct
OpenCL at worker startup. The first composition operation initializes it;
later audio commands preserve retained picture/scopes history. Fault gates
prove coded `GA_COMPOSE_GPU_INIT`/`GA_COMPOSE_GPU_CHECK`, cache cleanup, retained
published envelopes and absence of encoder output on failure. CPU source-frame
requests remain usable after failed compositor initialization.

The current 15-second regular 1080p60 device/headless run delivers 899 pictures
with no early pictures or observed audio underruns, two audio-buffer boundaries
and -0.2447 ms interval drift over 13.988 seconds. It excludes native display,
speaker latency and per-picture pixel identity. A separate actual native window
uses a 2560x1316 surface and fitted 480x270 monitors: its first 60.147-second
playing epoch shows 3,591 changed pictures at 59.74/s, eight skipped positions
and two observed drained-queue presentations at startup/EOF. Excluding exactly
the first second and final half-second produces 3,502 changes at 59.88/s over
58.463 seconds, six skips, no observed drain and a 29.55 ms maximum picture gap.
Steady device drift is -0.9881 ms; after-presentation metadata lag is generally
two frames (33.33 ms). The complete epoch is retained; no photon/speaker latency
or independent source-pixel alignment claim follows.

Native EOF, rewind, seeks, changing histogram/time/marker, fitted filmstrip and
processed peaks, mute/unmute and Stop are observed. The 1,032-placement private
project reaches lower busy lanes and plays paired AAC for 21 seconds while
scrolling remains responsive. A separate input candidate repairs title Text
dispatch; actual Ctrl+A highlighting and physical-key replacement are observed.
Its reusable AIR Win32 clipboard overlay passes 1,044 injected-adapter CPU checks
for committed Unicode events, bounded reads and clipboard ownership. It changes
no media decoder, color shader, shared MM-AIR runtime or FFmpeg packaging.
The separate `C524` native window accepts paste/title preview, filter-order
Undo/Redo and full-graph Save/Open with zero unexplained changes. A 240-frame
export cancels at 58% with output/sidecar cleanup. After an intentionally retained
silent-source retry failure, a second private 12-frame audible retry passes
independent source-frame, title, grade-order and processed-AAC checks.
These results are bounded workflow acceptance, separate from the `AD8985`
playback profile. The final `80A6` candidate independently verifies plain header
wheel after a native picker, lower-lane strips, native title paste/cancel and
settled scopes/time/marker seeks. Its fresh regular-source native epoch measures
59.73 changed pictures/s raw. Explicit startup1s/tail0.5s exclusions give 59.884/s
with six skipped positions, two four-frame jumps and a 34.90 ms maximum gap;
no early or over-two-frame stale pictures, observed steady audio drain or packet
overwrite occurs. Steady device drift is -0.9696 ms and after-present metadata lag
is two frames. The full raw epoch remains preserved, including startup/EOF.
The main-only `52A6` secondary-button guard is now published with targeted
757-control/probe/failure and actual native acceptance after the complete `80A6`
Windows suite. The `80A6` timing, prior `AD8985` profile and `C524` workflow
receipts retain their own app identities. A separate final-root profile below
measures the published binary directly. No fullscreen 4K,
zero-drop cadence, sustained compound 4K60 or complete professional-project
acceptance follows. See the
[current ledger](CONTROL_COVERAGE.md#visible-strips-lazy-gpu-and-qualified-hdr-candidate-on-2026-10-10)
for the bounded viewport/publication tests and remaining scope.

### Published root playback scope

The installed `52A6` application has a distinct native first-epoch profile on the
full 76,701-frame regular source. The epoch ends with manual Stop at `01:15:33`,
not authored EOF: 75.711 wall seconds, 4,521 changed pictures, 59.75/s raw and
13 skipped positions. Startup1s and observed-Stop-tail0.5s exclusions yield
4,434 changes at 59.885/s over 74.025 seconds, eight skips, two five-frame jumps
and a 48.58 ms maximum gap. No early, over-two-frame stale or steady drained
queue is observed; device drift is -1.2236 ms and after-present metadata lag
is two frames. This measurement applies to the published root binary directly.
Earlier profiles retain their own identities, and no full 21-minute cadence or
physical speaker/photon alignment is claimed.

Stop/Start, settled scopes and a frame12773 (`03:32:53`) seek align picture,
time and marker in the actual window. Fit populates filmstrip/processed peaks,
but that checkpoint's 0.05 px/frame minimum zoom prevents fitting the entire long clip;
only about its first 5.5 minutes is visible in that surface. Fixed 512 peaks on
this source have about 2.5-second bucket resolution. Those timeline limitations
are addressed by the subsequent long-timeline update and are not decoder/color acceptance.

### Long timeline navigation and processed peak detail

The published native `1BD1` app removes the unrelated minimum zoom that prevented
full-duration Fit. Its ordinary full-project window shows all 76,701 frames,
with mapped filmstrip tiles and 25,567 processed peak cells. Pan and zoom reuse
the complete peaks; fitted rendering takes the maximum across subpixel cells
and aligns transient bars to visible columns. Seek `20:12:13`, End/Start and
histogram/parade/luma updates agree with Program time and picture. Embedded
stereo meters and Mute/Unmute/Stop respond. The complete Windows suite passes
on this exact build, and its verified payload is installed at the root.
No decoder, codec, color, DSP or runtime change is
introduced by this update.

The peak cache is bounded, but cold changed waveform preparation still processes
the complete clip. Changed eligible clip counts can change quotas and regenerate
results; clips beyond the 65,536-cell cap have coarser detail. This functional
native check ran alongside the regression suite and adds no playback cadence,
physical A/V, full 21-minute playback or sustained 4K60 claim. See the
[long-timeline ledger](CONTROL_COVERAGE.md#long-timeline-fit-and-fine-waveforms-on-2026-10-10).

### Ordinary 4K baseline after the long-timeline update

A separate serial native-window run measures the published `1BD1` app with the
supplied AV1/PQ 59.94 fps source, embedded stereo audio, a 2560x1316 ordinary
maximized editor and fitted 480x270 monitors. It uses a private project copy;
the source and original project remain byte-identical. Fullscreen 4K remains
deferred. The complete first playback epoch lasts 134.174 seconds and records
8,027 changed frame positions at 59.854/s, with seven skipped positions and a
105.965 ms maximum startup gap.

The fixed startup-one-second and manual-Stop-tail-half-second exclusions retain
132.521 seconds: 7,941 changed positions at 59.915/s, four skipped positions,
a maximum two-frame jump and a 33.553 ms maximum gap. After-presentation metadata
lateness has a one-frame median, a two-frame p95, and 30 three-frame observations
(50.05 ms). **The two-frame lateness gate fails.** No early pictures, steady
drained queue, queue overwrite, audio-cache rebuild or filmstrip request is
observed during that interval. Device-clock drift is -2.205 ms. Median painting
is 1.231 ms and synchronous presentation is 14.191 ms.

Manual Stop retains the picture and zeros output meters; Start restores frame
zero. This bounded direct-source baseline establishes neither zero-drop
playback nor a full five-minute/compound 4K60 interval, and measures metadata
clock alignment rather than physical speaker/display latency. Its raw first
epoch and failing result are retained; the exclusions and gate are unchanged.

## Ordered decode windows and actual picture reserve

The [native validation record](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md) retains
five subsequent ordinary-window runs and their failures. A two-frame producer
window and ordered packet FIFO eliminate latest-packet overwrite, but a shared
three-picture budget still exhausted its actual reserve during decoder waits.
The 179.276-second private run averaged 59.8456 changed pictures/s and had five
presentations beyond the two-frame lateness limit; its timing gate failed.

The published 1A49 application prepares eight actual consecutive future pictures
(or the available short tail) before first PCM, then refills within that fixed
owned/reserved budget. Each
producer window and completed-packet FIFO remains capped at two. This changes
application scheduling and ownership, with the same AA40 native worker and
MM-AIR codec runtime. It adds no FFmpeg copy, decoder DLL or GPU backend. Native
timing acceptance now passes for the bounded ordinary editor scope below.

The coherent Windows gate and native 1080p editing/modal/export checks pass on
`1A49B8AF32B9A9169DFCDEBB78D4F523BF742C4C34A006F90551C2B8251EB4B6` with worker
`AA40B96C631C82CFC834D027678E95A00BD8D5F61DB54F15E7C7ECEFCF74228C`.
Its serial native 4K-source run lasts **133.8901633 seconds raw**. The unchanged
first-one-second and final-half-second exclusions retain **132.1706172 seconds**,
**7,923 changed pictures at 59.9376788/s**, zero steady repeats/skips/backward/early
pictures, no jump above one frame, no presentation beyond two heard frames, and
no queue drain or overwrite. Steady gaps have median/p95/maximum
**16.67895/17.4692/24.1018 ms**. Actual prepared futures have median six/p95 seven;
the observed owned/reserved total is bounded by eight.

The full raw trace retains two frame-zero repeats, two startup drains and its
**171.3431 ms** maximum gap. This is a supplied AV1/PQ 59.94-fps source with live
embedded stereo audio, fitted 480x270 monitors and an ordinary maximized native
window. Manual Stop at `00:02:13:32` silences output with a nonblank picture; Start
restores nonblank frame zero. It does not prove the full authored five minutes,
compound 4K60, fullscreen 4K, a pixel oracle for every presented picture or
physical speaker/display alignment. A fixed reserve cannot guarantee recovery
from arbitrary stalls or persistently slower decoding. Headless preparation
benchmarks remain separate evidence.

Installed-root publication and readiness pass with the shared runtime and original
assets unchanged. Prior failed/incomplete runs and BDF3's unknown initiating
producer-exit cause remain in the [native validation record](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md).
The [sanitized evidence archive](../archive/native-playback-reserve-2026-10-10.tar.gz)
preserves source and receipts; its digest is recorded in the archive receipt and
publication commit. Broader professional editing acceptance remains incomplete.

## Linked lanes and audio refusal preflight

This application slice separates V thumbnails from A processed waveforms and
suppresses the V half's duplicate sound. It changes shared planning, controls and
SDK document routing; the AA40 worker, codecs and GPU/color path remain unchanged.
Properties audio edits target the A mate, and grouping retains linked mates.
No new headless throughput or native cadence result is inferred from these edits.

Contributing clip Pan/Speed curves and curves on enabled audio-filter instances
report `GA_AUDIO_AUTOMATION_UNSUPPORTED`; this is explicit refusal, not animated
DSP support. Audible offline leaves, including compound descendants and original
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
