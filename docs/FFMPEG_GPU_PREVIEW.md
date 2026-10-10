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
Other formats, Vulkan/software frames, native-size renders and explicit HDR
masters use the reference CPU graph. Every application export also passes
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

Cold changed waveforms still materialize a full audio body. The current `--serve`
worker eagerly initializes OpenCL even for audio-only work; lazy audio startup
remains future optimization. Native-resolution HDR shader experiments remain
private and are not part of this installed checkpoint. No new sustained native
4K60 or physical audio-latency claim follows from these waveform/viewport checks.

The installed direct-waveform app (`0928f1c3...`) also passes a fresh native check
of Play, embedded-audio mute/unmute, Stop, frame-zero rewind, timeline/monitor
scrubbing and changing fitted scopes. The 26-track test publishes 23 bitmap rows
and 512 processed peaks. See the [UI receipt](../archive/native-direct-tracks-root-ui-2026-10-10.json)
and [sanitized acceptance bundle](../archive/direct-waveforms-vertical-tracks-2026-10-10.tar.gz),
which preserve the initial disabled-control diagnostic failure and passing tail
rerun alongside the unchanged production/media prefix.
