# Genesis AIR Windows handoff — 2026-10-13

## Current state

R19 is the installed and published **core editing checkpoint**. The tested
workflow covers linked video/audio editing, preview and transport, project
Save/Open, representative rendered effects/titles, and cancellable export.
Broader professional features and validation gaps remain below. The archive
explicitly records `complete_professional_editing_acceptance: false`.

- Repository: `C:\Users\Alexn\Documents\Codex\2026-09-28\Genesis-AIR-windows-native`.
- Branch: `windows-native`; remote: `https://github.com/CodeAlexx/Genesis-AIR.git`.
- Local HEAD and remote branch both verified as
  `481090d3158646a1d075945325ba00c575a856b8`.
- Commit: **Make native Windows editing playback and audio endpoints dependable**.
- Product executable: `Genesis-AIR.exe` in the repository root. Root output is
  required; the default conversation directory is the unrelated AirFetch checkout.
- Working tree was clean before this handoff. This new local handoff is unstaged,
  uncommitted, and outside the already published R19 archive.
- No Genesis editor or compositor process was running at handoff verification.
  Audio, editing and playback agents have completed; no jobs need joining.
- Handoff creation only inspected files/processes and wrote this document.
  It did not restart implementation, builds, tests, decoders or desktop sessions.

## Constraints to preserve

- Windows must use native Win32/Direct2D and Windows audio. **GTK is forbidden.**
- Keep shared AIR application, controller, UI and theme source. Isolate platform
  differences in reusable adapters; preserve the shared `std.*` theme direction.
- Reuse the existing MM-AIR media runtime. Do not add a separate Genesis FFmpeg
  executable or codec DLL bundle. The user's final choice supersedes the earlier
  request to remove all FFmpeg components.
- Fullscreen 4K is explicitly deferred. Ordinary maximized fitted-preview tests
  do not authorize describing native-resolution fullscreen 4K as qualified.
- Linked media must have V1 pictures/thumbnails and separate A1 sound/waveforms,
  synchronized edits, and a single audio contribution. Source transport is independent.
- On an explicit pause/stand-down request, stop owned work and release the desktop
  immediately. Resume only after the user requests it. This handoff does not
  authorize starting the remaining backlog.
- Keep failed measurements and earlier receipts with their original scope.
  Do not weaken numeric/cadence thresholds or infer native acceptance from model tests.

## Installed identities and dependencies

Root hashes were freshly compared with the published archive receipt:

| Artifact | SHA256 |
|---|---|
| `Genesis-AIR.exe` | `a2d950cb2ae9a6b922e0e7d7efa78265ca477def639baeeb47924472adcd77c1` |
| `genesis-native-audio.dll` | `f6885bec959c0e29b3583af5cab28dcb28a07996b2c356b860ed1cda097829d9` |
| `genesis-gcompose.exe` | `079171d5d625e6acb36bcd80809279e43838278b5dd9bc21d7403ce1ec4c81d3` |
| Frozen receipt | `46dbc02762d260ca2385b48e5f22c342fad24075fc038c67cc25b3da0e4ac66d` |
| Build receipt | `70173a79abfe6b739f7d3e0a0767b798e829dbe033cd82de7b6d406767942fb8` |

SDK HEAD: `df80f270dd28af76674b6e80a4f08970c081be3e`.
Compositor source HEAD: `5e26dc2203540f3c2996dba7506f5da18d4065ac`.
Both were freshly checked; applied overlays are additionally bound by the freeze.

`genesis-media-runtime.txt` points to:

```text
C:\MM-Air\share\media\ffmpeg-n9.0.2-17-g2a571b6068-win64-gpl-shared-9.0\bin
C:\MM-Air\ffmpeg.exe
C:\MM-Air\ffprobe.exe
```

D3D11 is the default native decoder; Vulkan is opt-in. Supported downscaled
P010/BT.2020/PQ previews use compute color conversion with a reference fallback.
Exports retain the declared reference path. These checks do not establish full HDR finishing.

## Validation receipts

Prefix: `pro-native-edit-export-r19-2026-10-13`.
Private base: `build-windows/pro-native-edit-export-r19-2026-10-13/`.
Paths in the table are relative to that base unless they start with `build-windows/`.

| Gate | Result and receipt |
|---|---|
| Coherent build | PASS; 69 generated C inputs and 90 native binary artifacts. `build-windows/PREFIX-build-receipt.json`, where PREFIX is the exact prefix above. |
| Full background suite | PASS; 92 fresh isolated reports, exit 0, no root-report substitution. `build-windows/PREFIX-background-receipt.json`; SHA `83491dd2b58e707f525af3e51f8f841d125235b438988721b8ec484034626959`. |
| Linux recorder component | PASS; 14 cases/2,770 checks. `linux-recorder-1/receipt.json`. Shared model scope only. |
| Actual audio device | PASS; stereo/pan/silent levels, immediate Stop, zero drain/resume shortfalls; owned clients closed. `device/receipt.json`. |
| Native paired editing | PASS; split at 120, head trim to 150, single Undo/Redo, Save As/reopen. Locked A1 returns `GA_LINKED_SPLIT` without changing saved bytes or consuming pending Redo. `native-workflow/edits-attempt1/native-workflow-receipt.json` and `saved-graph-verification-1.json`. |
| Unicode title and master | PASS; multiline `café\nCUT`, Undo/Redo, Save As/reopen and lossless master. All 30 pictures, glyph interiors and 48,000 stereo PCM frames independently checked. `native-title-export-1/rendered-receipt.json`. |
| Active Cancel and same-target retry | PASS; Cancel at 2%, target/sidecars absent and export worker joined before retrying the identical filename. All 12 RGB16 pictures and 9,600 stereo PCM frames checked independently. `native-workflow/edits-attempt1/same-target-export-receipt-2.json`. |
| Native 1080p60 cadence | PASS; 154.6858228 steady seconds, 9,282 changed pictures, 59.999034/s, no steady omissions/repeats or late-over-two-frame presentations. `cadence-1080/attempt1/accepted-summary.json`. |
| Native fitted 4K59.94 cadence | PASS; 165.3517818 steady seconds, 9,912 changed pictures, 59.938876/s, same zero steady faults. Ordinary fitted 480×270 preview. `cadence-4k/attempt1/accepted-summary.json`. |
| Actual root-ready | PASS; root app/audio modules, separate V1/A1, scrub/time/marker/scopes, green postmix meters, Follow, Pause/Stop, visible first-frame rewind, new private Save As and normal owned Close. `build-windows/PREFIX-root-ready.json`; SHA `c791b500a716ac44b74a6d1f12cee8a2a3a765e967c53c4435708474fb1029ac`. |
| Six native tail exports | PASS; native actions, saved graphs and independent RGB16/PCM checks. `native-tail/six-qualification-summary-1.json`; SHA `1c59d588978f0b53e79c13f11a23394eabda355d5b04913a60b2e89b6afc1c0e`. |

Tail export counts (unmarked / marked body / tail only):

| Effect | Pictures | Stereo PCM sample frames |
|---|---|---|
| Delay | 71 / 60 / 7 | 112800 / 96000 / 10400 |
| Reverb | 69 / 60 / 5 | 109152 / 96000 / 6752 |

Tail RGB16 error is 0 within the unchanged five-code bound; maximum PCM float
error is below `1.19e-7` within `2e-6`. Delay trace records 19 actual 70→0 resets,
18 with full 112800-sample witnesses; the resumed-origin reset is distinguished.
Source progresses 0→59 while Program holds 38. Reverb Loop remains unqualified.

The cadence parser retains its fixed first-second/final-half-second selection
and all raw rows, including input rows. These bounded software presentations
do not prove whole-source cadence, physical scanout or speaker/display alignment.
Fresh root functional checks are separate from the longer staged cadence runs.

## Implementation pointers

- `src/main.ai`, `src/window_profile.ai`: R19 buffers timing rows in owned RAM
  chunks during playback and flushes after both logical transports and native
  audio retire. The 46-column schema, 50,000-row cap and strict gates stay unchanged.
  This removes the synchronous recorder flush implicated in R18's 4K stutter.
- `src/provider.ai`, `src/preview.ai`, `src/preview_link.ai`, picture queue/memory:
  persistent picture transport, frame identity and retirement.
- `src/audio_endpoint.ai`, `src/audio_playback.ai`, `src/timeline_media.ai` and
  `windows/gcompose-windows.patch`: exact accepted endpoints and processing history.
- `src/timeline_follow.ai`, `src/view.ai`, `src/waveform_view.ai`: completed-frame
  Follow, thumbnails and separate A1 reference waveform. Manual scrolling suspends Follow.
- A1 reference waveforms neutralize the owning track mixer for display. Clip
  processing remains visible; actual output meters follow the complete postmix.
  Mute/Gain 0/Solo exclusion retain a dimmed, labelled waveform.
- `patches/air-editor.patch`: shared supported edits and transactional refusals.
- `tests/windows.ps1`, `tests/run_tests.py`, endpoint/tail/picture/waveform tests:
  meaningful shared and media gates. Three known blank-at-EOF warnings remain in
  `program_picture_control.ai`, `program_picture_protocol.ai`, `upper_transition_media.py`.

## Protected originals

Do not modify, overwrite, delete or stage these originals for test edits. Use new
private copies and native Save As into a newly named candidate directory.

| Original | SHA256 |
|---|---|
| Root `Costa Rica 4K.air` | `480d82e310ba6f231fab2c0c0db9945dab193d63073cb63fe053019a13aeb143` |
| Root `Regular 1080p60.air` | `7d9e045225e1a236237b85c22342f612c1be92e2cfd298e47df58df8014c9ba0` |
| Root `Regular 1080p60 linked.air` | `97d28812e5bd1a8f9bf6d86df87726809bc1e3cd5842686b72b0ff685d61369b` |
| `C:\Users\Alexn\Downloads\AirFetch\COSTA RICA IN 4K 60fps HDR (ULTRA HD).mp4` | `bff7165e6704e7188fee82b990e5128fe87c3ce9c5ef7eeb85bd1bb0da42c6da` |
| `C:\Users\Alexn\Downloads\AirFetch\Which is The Best Qwen3.8-27B_.mp4` | `061d76990215c31e6dc58d22f4ecd09ac92d414fdc73061e8dfcb502cee3f11d` |

1080 fixture: 1920×1080, 60 fps, 76701 frames, 44.1 kHz stereo audio.
4K fixture: AV1 Main, 3840×2160, P010/BT.2020/PQ, 60000/1001 fps, 18808 frames.
These recorded protected hashes were rechecked by final R19 qualification;
handoff creation did not rehash the large source media or replay it.

Preserve R19 frozen/source/generated/native/runtime trees, receipts, private
projects, failed attempts, runtime backups and archive bytes. Older native
projects/exports are evidence, not expendable output or current acceptance.

## Archive and retained failures

Published bundle: `archive/pro-native-edit-export-r19-2026-10-13.tar.gz`.
Receipt: `archive/pro-native-edit-export-r19-2026-10-13.json`.
Bundle SHA256: `c5117ed663866ec00531708805cbfd58c4cd79c820b9d9306341b81e65263cf9`.

Archive verification passed: full member readback, current installed payload,
Git-index-equal source/docs and final identity checks. There are 16677 physical
members and 12614 explicit verified-byte aliases in `manifest.json`; each
selected original keeps its own provenance. Follow `entry_aliases` when locating
deduplicated additional evidence. No product binaries, media, private project
files or complete SDK/runtime trees are bundled.

Preserved distinctions:

- R18 fitted 4K failed with five omissions; its long synchronous recorder step
  motivated R19. R17 repeats and R16 omissions/repeats remain failures.
- R15 original wrapper failure and separately recovered suite result remain distinct.
- The original same-target verifier failed on ffprobe `%+.21`; helper4 changes
  only that argument to `%+0.21`, keeping the independent oracle and thresholds.
- Tail preparation metadata repair preserves original bytes and the initial failure.
- Archive attempts 1–3 failed on SDK inclusion/text budget. The final packaging
  helper excludes verify-only trees and deduplicates equal additional evidence
  with full-byte checks. The sanitizer, acceptance gates and 512 MiB text budget
  remain enforced; final `archive-final-4.log` records success.
- Private final archive entry point: `build-windows/PREFIX/run-final-archive-content.py`.
  These are exclusive qualification outputs; do not rerun into existing filenames.

## Remaining work, in priority order

1. **Long-project validation:** whole-source playback and full-length export,
   multitrack compositions, compound 4K60, repeated seeks and save/reopen cycles.
   Current measured steady intervals cover roughly three minutes.
2. **Audio implementation/performance:** track/audio-effect automation, live
   scrub sound and faster cold audio preparation. Extend native checks for
   effect-tail edits and Reverb Loop; supported Delay/Reverb export tests already pass.
3. **Effects/transitions:** finish refused nested/reverse/animated tail-history
   combinations, rotated or compound transition sides, and base incoming
   overlay-only edits. Verify every exposed parameter/order/curve interactively.
   Normalize remains body-capped and supported tails have a five-second total budget.
4. **Titles/stabilization:** complex-script shaping, right-to-left layout,
   richer typography; stabilization currently covers local translation within
   24 output pixels, not rotation/perspective/path smoothing.
5. **Finishing/release validation:** physical A/V alignment, reference-monitor
   HDR/scene-linear processing, and clean-machine setup against the shared MM-AIR
   runtime. Native Linux UI parity remains separate from passing shared models.

Fullscreen 4K stays deferred until the user changes that instruction.

## Resume sequence

1. Wait for a user request to resume product work. Confirm desktop availability
   before interactive testing if another session is using the machine.
2. Enter the Genesis repository above; inspect current Git status/HEAD, installed
   identities and `docs/PRO_EDITING_ACCEPTANCE_WINDOWS.md` plus
   `docs/CONTROL_COVERAGE.md`. The handoff is the only expected new local file;
   preserve any later changes from other sessions.
3. Choose the next bounded item: long-project validation and audio are recommended.
   Distinguish missing implementations from cases that merely lack native proof.
4. Use a fresh candidate prefix and private outputs. Normal Windows entry points
   are `build-windows.ps1`, `windows/build-worker.ps1` and `tests/windows.ps1`.
   The local coherent wrapper `build-windows/run-pro-native-r16-build.ps1` requires
   an explicit fresh `-Prefix`; setting only its environment variable is insufficient.
   Review its baseline/overlays and prepare appropriate new report contracts first.
   R19 `bg-ready/run.ps1` and native recorders enforce R19-specific identities;
   do not blindly repoint them to R20 or weaken their guards.
5. Compile application and worker coherently into stage, verify the new freeze,
   run affected meaningful tests and required full gates. Existing green R19
   receipts do not qualify changed code. Preserve failed attempts under new names.
6. For native checks, use the computer-use skill's official Windows API and
   fresh window identities. Old PIDs/HWNDs in receipts are historical only.
   Work with private project copies; record actual actions and loaded modules;
   normally close owned apps/workers and prove exit.
7. Publish a newly qualified coherent payload to root, check the actual root
   copy, update docs, archive scoped evidence, commit and push when authorized.

No builds, tests, publication or agent wakeups are required to finish this handoff.
