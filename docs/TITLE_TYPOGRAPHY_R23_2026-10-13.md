# R23: title typography (2026-10-13)

Prefix `pro-native-edit-export-r23-2026-10-13`, built coherently on the R22
publication and published to the repository root (worker unchanged).

## What a title can do

New Text filter parameters, shown in the inspector with the current font name and
alignment:

| Parameter | Range | Default | Keyframes |
|---|---|---|---|
| Font | 0 Default, 1 Arial, 2 Georgia, 3 Times New Roman, 4 Impact, 5 Consolas, 6 Verdana | 0 | no |
| Bold, Italic | 0/1 | 0 | no |
| Align | 0 centre, 1 left edge at X, 2 right edge at X | 0 | no |
| Red, Green, Blue | 0..1 | 1 (white) | yes |
| Outline | 0..12 px at 1080 height, scaled with the canvas | 0 | yes |
| Shadow | 0/1 (2 px drop shadow) | 1 | no |
| Box opacity | 0..1 translucent black panel behind each row | 0 | yes |

The chosen face is loaded first, with the configured default chain behind it for
characters it lacks (Linux uses DejaVu equivalents). A missing font file falls back
to the default face. Out-of-range values are refused with coded messages before
any output is written. Default settings draw exactly as before.

## Evidence

`tests/title_typography.py` renders real 1280x720 titles through `preview` and
lossless `export`, decodes the master independently and requires the preview to
equal the nearest-fitted master (≤ 2 codes). It is part of the background suite
(R23 `bg1`: PASS, full suite exit 0,
`build-windows/pro-native-edit-export-r23-2026-10-13-bg1-background-receipt.json`).

| Check | Result |
|---|---|
| Default title vs installed R22 | byte-identical master and preview (`--baseline` run) |
| Explicit default values | identical to omitted parameters |
| Red text | 7,549 red pixels, 0 white |
| Shadow off / outline 4 | 0 dark pixels / 8,542 dark pixels (shadow alone 1,774) |
| Box 0.6 | panel pixel (32,44,56) = 40% of background exactly |
| Align centre / left / right | centred on 640; left edge 641; right edge 636 |
| Bold | 1.84x the glyph ink of regular |
| Italic | differs from regular |
| Seven families | seven distinct rendered widths |
| Keyed Green 1→0 over 10 frames | white at frame 0, magenta at frame 10 |
| Font 7, Bold 0.5, Red 1.5, Outline 20 | refused, no output file |

Showcase: `build-windows/long-project-r20-2026-10-13/typo-showcase/costa.png`.

## Not included

Per-character styling within a row, choosing arbitrary installed fonts, letter or
line spacing, gradient fills, and animated text presets.
