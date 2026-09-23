# Control acceptance ledger

The target is every control Genesis AIR currently exposes. A control is complete when its
document edit, saved/reloaded state, preview, export, and failure behavior agree. The 594-click
UI gate proves hit testing and command dispatch; it does not by itself prove media output.

## Video filters (31)

| Status | Kinds | Remaining gate or implementation |
|---|---|---|
| Mapped to the worker wire | brightness, contrast, saturation, gamma, hue, sharpen, blur, glow, grain, levels, lift_gamma_gain, rotate, flip, mirror, denoise | Pixel change and preview/export parity for each parameter value, including animation and every visible lane. |
| Mapped with limits | white_balance, vignette, sepia, mono, invert, crop, size_position, chroma_key, opacity, blend, mask, speed | Base and overlay opacity have preview/MP4 pixel gates. The centered base mask has feather/invert preview/MP4 center and edge gates. Speed multiplies clip Rate and has a generated 24-to-30 fps, 2x picture/audio/15-frame export gate; animated speed remains unsupported. Tint, softness, fractional look amounts, asymmetric crop, overlay rotation/masking, other non-overlay uses, and blend modes 8–11 need real implementations. Existing unsupported values fail explicitly. |
| No media mapping yet | text, timer, stabilize, lut3d | Implement the advertised behavior and exercise it in preview and export. |

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
| Timeline, pool, tracks, transport, undo/redo | Command/state gate, save/reload, drag undo step; generated-media preview/export and X11 Play/Pause for representative cases | Media outcomes for every edit operation, nested sequences, all transition kinds and overlap seams, fast interactive preview. |
| Inspector and keyframes | Every control is clicked; clip-local opacity and brightness keyframes change the render wire; keyed picture fade and base opacity have preview/MP4 pixel gates; K creates a missing filter in one undo step and refuses known unsupported automation | Full mapped video parameter coverage, remaining keyframed clip properties, unsupported video filters, and audio automation. Per-layer filter support still needs to be reflected at the K action. |
| Subtitles and text | Two timed ASCII caption cues appear in preview and MP4 | Non-ASCII text, placement/typography controls, the `text` and `timer` filters. |
| Export and audio | Generated MP4 pixel/audio checks; WAV mix, spaced output path, and X11 audio start/stop | Asynchronous export progress/cancel, precise audio/video sync, live scrub sound. |
| Frame rates | AIR editor native-to-sequence bounds, pure-AIR wire sampling, and generated 24-to-30 fps preview/export/audio gate | Sequence export rates other than 30 fps. |

Keep this ledger with the implementation. Add a measured output assertion when closing a
row; a document mutation or successful worker reply alone is insufficient.
