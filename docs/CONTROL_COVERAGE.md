# Control acceptance ledger

The target is every control Genesis AIR currently exposes. A control is complete when its
document edit, saved/reloaded state, preview, export, and failure behavior agree. The 594-click
UI gate proves hit testing and command dispatch in its representative panel states;
state-dependent controls also need focused checks. It does not by itself prove media output.

## Video filters (31)

| Status | Kinds | Remaining gate or implementation |
|---|---|---|
| Mapped to the worker wire | brightness, contrast, saturation, gamma, hue, sharpen, blur, glow, grain, levels, lift_gamma_gain, rotate, flip, mirror, denoise | Upper-clip brightness now has two- and three-lane preview/MP4 pixel gates proving lower clips stay unchanged. Pixel change and preview/export parity for the remaining parameter values and animation are still required. |
| Mapped with limits | white_balance, vignette, sepia, mono, invert, crop, size_position, chroma_key, opacity, blend, mask, speed, lut3d, text, timer | Base and overlay opacity have preview/MP4 pixel gates. White-balance temperature and tint have preview/MP4 color gates, including gain composition with Color Grading. LUT3D accepts a `.cube` path through the filter panel, stores it in revision 2 projects, validates the grid, and has a full-strength preview/MP4 channel-swap gate, a half-mix preview gate, and keyed Amount preview endpoints. Text renders stored content with keyed Size/X/Y, and Timer renders a clip-local timecode with Size; both use AIR's vector font and have generated preview/MP4 gates. Non-ASCII text is refused. All 12 displayed blend modes have generated formula and preview/MP4 pixel checks. Four independent Crop margins have asymmetric preview/MP4 edge gates; cropping an upper clip remains refused because the worker paints cleared pixels black without changing transparency. The centered base mask has feather/invert preview/MP4 center and edge gates; upper mask and rotation are refused for the same transparency reason. Speed multiplies clip Rate and has a generated 24-to-30 fps, 2x picture/audio/15-frame export gate; animated speed remains unsupported. Softness, fractional look amounts, overlay rotation, and other non-overlay uses need real implementations. Existing unsupported values fail explicitly. |
| No media mapping yet | stabilize | Define and implement the advertised stabilization behavior, then exercise it in preview and export. |

## Audio filters (20)

Gain, pan, three-band EQ, ten-band EQ, compressor, gate, normalize, reverb, delay, pitch,
low pass, high pass, tremolo, bass, treble, notch, chorus, flanger, phaser, and limiter
have AIR-to-worker mappings. The real-media suite applies each and checks for audible
output. Parameter-specific signal measurements, animated parameters, and long-timeline
playback timing remain acceptance work. The gate's stored `hold` is presented as release
time because that is what the worker filter implements.

## Other exposed controls

| Area | Verified | Still required |
|---|---|---|
| Timeline, pool, tracks, transport, undo/redo | Command/state gate, save/reload, drag undo step; generated-media preview/export and X11 Play/Pause for representative cases; all 11 named transition kinds have spatial preview/MP4 gates on touching cuts; overlap and short-gap seams have midpoint crossfade gates; incoming and outgoing Text titles are checked through a crossfade | Media outcomes for every edit operation, nested sequences, non-touching seams for every kind, fast interactive preview. Incoming transition opacity, fade, and overlay-only effects currently fail explicitly. |
| Inspector and keyframes | Every control is clicked; clip-local opacity and brightness keyframes change the render wire; keyed picture fade and base opacity have preview/MP4 pixel gates; LUT3D Amount has keyed preview endpoints; K creates a missing filter in one undo step and refuses known unsupported automation | Full mapped video parameter coverage, remaining keyframed clip properties, unsupported video filters, and audio automation. Per-layer filter support still needs to be reflected at the K action. |
| Subtitles and text | Two timed ASCII caption cues appear in preview and MP4; Text content, Size/X/Y, and Timer timecode/Size have generated media gates | Unicode glyphs, richer typography, and subtitle placement. |
| Export and audio | Generated MP4 pixel/audio checks; WAV mix, spaced output path, and X11 audio start/stop | Asynchronous export progress/cancel, precise audio/video sync, live scrub sound. |
| Frame rates | AIR editor native-to-sequence bounds, pure-AIR wire sampling, a generated 24-to-30 fps preview/export/audio gate, and a 24 fps sequence preview/9-frame MP4/audio gate | More sequence rates, especially fractional rates, and long-timeline audio sync. |

Keep this ledger with the implementation. Add a measured output assertion when closing a
row; a document mutation or successful worker reply alone is insufficient.
