# R22 checkpoint: long projects, animated pan, wide stabilization, RTL titles (2026-10-13)

Prefix `pro-native-edit-export-r22-2026-10-13`, built coherently against the R19
publication and published to the repository root.

| Payload | SHA-256 |
|---|---|
| `Genesis-AIR.exe` | `6988c9b70d60b6de…` |
| `genesis-gcompose.exe` | `9c5c8057b49c4c40…` |
| `genesis-native-audio.dll` | `3eb1b1d80a37b115…` |

Full identities: `build-windows/pro-native-edit-export-r22-2026-10-13-publication.json`.

## Qualification

- Coherent build: PASS (frozen source verified before and after).
- Full `tests/windows.ps1 -BackgroundOnly`: PASS in attempt `bg2`, 223 fresh JSON
  reports / 2,606 bound files
  (`build-windows/pro-native-edit-export-r22-2026-10-13-bg2-background-receipt.json`).
  Attempt `bg1` ran the same suite to completion with every gate passing, but the
  new receipt helper rejected copied DLLs whose modification times predate the run
  and the wrapper then wrote exit 1. The helper now checks creation times; `bg1`
  is preserved unchanged.
- Earlier candidates are preserved with their causes: R20
  (`build-windows/pro-native-edit-export-r20-2026-10-13/OUTCOME.md`, stale
  animated-pan test contract) and R21 (`…r21…/OUTCOME.md`, oracle lacked the Gain
  filter).

## Animated clip pan (audio)

Clip Pan curves are now rendered instead of refused when every enabled audio
filter on the clip is memoryless and per-channel (Gain, Pan, Volume, Mute). The
curve travels as a `PANKEYS:` token beside `GAINKEYS:` in both flat
`AUDIO/AUDIOSTREAM` lines and nested `NEST*` envelopes, replacing the static clip
pan stage. The worker evaluates the same 38 SDK curve modes at absolute rounded
sample positions and applies the FFmpeg `stereotools` output balance per sample
(`L *= 1 - max(0,b)`, `R *= 1 + min(0,b)`), which equals the static stage that
follows reverse/tempo for those chains. Track pan stays a static stage.

Pan curves before a stateful filter (compressor, gate, EQ, delay, reverb, ...)
keep `GA_AUDIO_AUTOMATION_UNSUPPORTED`. Speed curves and curves on enabled audio
filter instances remain refused.

Evidence: `audio_plan_preflight.py` 63 cases (accepted animated pan and pan over a
Gain filter, refused pan before a compressor; PCM24 max error 1.2e-7) and
`direct_waveforms.py` 37 cases (hold/linear pan curve with static track pan, pan
over a Gain filter; independent per-sample stereotools oracle, max peak error
3.7e-9), both inside the R22 suite.

## Stabilization beyond 24 pixels

The translation estimator is now coarse-to-fine: an 8x8 box-mean search covers
the whole window, then full-resolution RGB refinement picks the exact pixel. The
window scales with the canvas (24 px minimum, 96 output pixels at 1080p and
above); margins always exceed the window, and the flat-shot and scene-cut refusals
are unchanged. Independent A/B (`build-windows/long-project-r20-2026-10-13/stab_check.py`):

| Case | Installed R19 | R22 worker |
|---|---|---|
| ±12 px jumps: residual jitter / export vs preview | 0 / 0.52 | 0 / 0.52 |
| ±60 px jumps: residual jitter / export vs preview | 32 / 16.6 | 0 / 0.53 |
| Flat textured shot, max code difference vs no filter | 4 | 4 |

(Measured in 640x360 pixels; reports `stab-r19/`, `stab-r21/` with the identical
worker.) Rotation, perspective and long camera-path smoothing remain unimplemented.

## Right-to-left and Arabic titles

`src/bidi.ai` converts each title and caption row from logical to visual order
before coverage checks, measurement and drawing: a simplified Unicode
Bidirectional Algorithm (first-strong paragraph level, W1-W7, N1-N2, I1-I2, L1
trailing whitespace, L2 reordering, L3 mark placement, L4 bracket mirroring) after
Arabic joining through Presentation Forms-B, including lam-alef ligatures, used
only when an installed face covers the form. Right-to-left captions keep the same
margin from the right edge. `tests/bidi_layout.ai` (10 hand-derived cases) runs in
the suite; `long-project-r20-2026-10-13/rtl-compare.png` shows R19 versus the new
rendering. Explicit embeddings/isolates and OpenType GSUB/GPOS shaping (Indic
reordering, general ligatures, mark positioning) are not implemented.

## Long-project validation

Private copies of the protected fixtures (originals untouched); evidence in
`build-windows/long-project-r20-2026-10-13/`.

- Full-length exports (installed R19 payload, `export-receipt.json`):
  4K HDR AV1 → 3840x2160 H.264, 18,808/18,808 frames, audio 313.780125 s versus
  video 313.780133 s, 2,694 s; worker private memory 7.32–7.55 GiB with no growth.
  1080p60 linked → 76,701/76,701 frames, audio and video both 1278.350 s (source
  audio is 0.19 s longer and correctly trimmed), 2,705 s; private memory
  2.57–2.63 GiB. Both outputs decode with zero errors.
- Whole-source headless playback (R22, real device, `playback-r22/`):

| Source | Seconds | Pictures presented | p95 lag | Max picture gap | Underruns | Device drift |
|---|---|---|---|---|---|---|
| 4K60 HDR AV1 | 313 | 13,855 of ~18,760 | 108.0 ms | 463.5 ms | 0 | −5.2 ms |
| 1080p60 | 1,278 | 76,321 of ~76,620 | 16.8 ms | 110.7 ms | 0 | −21.4 ms |

  Every structural assertion held (monotonic clocks, no early pictures, timeline
  equals displayed frame, picture queue ≤ 2). The 4K source does **not** sustain
  full cadence through this headless profile path (about 74% of frames shown);
  this is an open performance finding, distinct from the shorter native cadence
  receipts.
- Repeated cold seeks (`SEEK-FINDINGS.md`): 12 seeks per source including both
  ends. 4K: 10 frame-exact, 2 ambiguous, 0 wrong. 1080: mostly static content;
  exact alignment proven at the end of the source; one oracle-sensitivity verdict
  investigated and shown not to be a wrong frame.

## Findings outside this scope

- `tests/real_media.py` (manual gate) fails on the installed R19 payload at its
  Speed-filter export frame count (16 frames, expected 15) and also needs a
  `GENESIS_WORKER_WRAPPER` harness; it is not part of the background suite.
- Not started this round: rotated (PiP) transition sides / overlay rotation, which
  needs an affine overlay transform in the GPU compositor; save/reopen cycle
  automation on the long fixtures.
