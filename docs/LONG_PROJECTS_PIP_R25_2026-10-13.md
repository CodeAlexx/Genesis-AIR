# R25: long-project editing, rotated picture-in-picture, 4K playback findings (2026-10-13)

Prefix `pro-native-edit-export-r25-2026-10-13`, built coherently on the R23
publication. Earlier attempt R24 is preserved with its cause
(`build-windows/pro-native-edit-export-r24-2026-10-13/OUTCOME.md`).

## Long projects: save/reopen cycles and razor-cut scaling

`tests/long_project_cycles.ai` (background suite) synthesizes a 21-minute 60 fps
linked picture/sound take, cuts it 1,000 times through the normal razor command,
adds titles (with the R23 styling) and gain keys to every eighth clip, then runs
20 save → reopen cycles through the native linked open path. Every reopen must
reproduce the encoded document exactly, unchanged saves must reproduce the file
bytes, and edits between cycles must survive: 2,010 clips, 86 checks, about 5 ms
per save and 62 ms per reopen.

The test exposed a real scaling defect. Every edit re-validated linked
video/audio pairs by scanning the whole document for each clip, so one razor cut
cost O(n²) and a session of cuts O(n³):

| Cuts (clips) | Before: cut phase | After |
|---|---|---|
| 400 (≈800) | 2.6 s | 0.12 s |
| 800 (≈1,600) | ~25 s | 0.43 s |
| 2,000 (≈4,000) | over 10 min (stopped) | 2.8 s |

One cut on a 1,600-clip project went from 85 ms to 1.3 ms. Mates are now computed
once per validation by bucketing clips by start time with an O(n log n) merge sort,
and pair lookups use binary search; the pairing rule is unchanged. Adding a filter
or editing title text stays linear (about 5 µs per clip).

## Rotated picture-in-picture

Size & Position Rotation now renders on upper-lane clips instead of being refused,
including clips that are sides of an upper transition. The compositor turns the
placed rectangle about its own centre (positive = clockwise, as the base Rotate
filter); rotation 0 keeps the previous kernel path and output byte-identical.
Rotation is keyable. Values beyond ±360° are refused. The frame wire gained one
trailing value (older shorter wires stay valid).

`tests/pip_rotation.py` (background suite): unrotated output byte-identical to R23;
90° swaps the covered long-axis points; 30° proves the clockwise direction;
keyed 0→90° equals a static 90° frame; a full turn differs only on rectangle-edge
pixels (395, none interior); a 45° rotated side renders inside an upper crossfade;
400° is refused. Preview equals the lossless master in every case.

Rotated sides of *base* (lower-lane) transitions keep their existing coded refusal.

## 4K whole-source playback: investigated, not fixed

The headless whole-source profile shows about 83% of 4K60 frames from a cold
start, falling to roughly 55–65% after about three minutes. Measured and ruled out:
memory growth (app ~72 MB, worker ~630 MB, flat), GPU saturation or heat (NVIDIA
decoder 17–43%, 56 °C; OpenCL already prefers the discrete GPU), CPU throttling
(105–108% of nominal throughout), and source bitrate (flat 24.8 Mbps). The worker
completes 60 pictures per second for the whole run; the slowdown is in the app's
presentation loop (iterations per second fall ~15% after ~3 minutes while a request
phase rises from 0.1 to 3.1 ms). This headless harness also software-paints a
1600x980 frame per iteration that the Direct2D window does not, so the result is a
finding for further work, not a measurement of the native window. Evidence:
`build-windows/long-project-r20-2026-10-13/playback-r23/`.
