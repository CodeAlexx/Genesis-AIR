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
default stays D3D11: merely changing the decoder leaves the full-resolution
readback and CPU HDR conversion in place. The next performance step is integrating
GPU color/scaling into our exact-frame request loop and existing export color
contract, including seek/reset and fallback behavior.

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
