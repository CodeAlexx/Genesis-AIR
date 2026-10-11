# Windows professional editing acceptance

This ledger follows the complete active goal: responsive real-media preview and
audio, dependable timeline edits and project persistence, rendered effects and
titles, reliable cancellable export, native AIR architecture and shared themes,
root product output, documentation and published source. Passing one component or
one bounded playback interval does not establish the whole goal.

## Current evidence and remaining work

The r5 root products are now published: application
`b07975912822d2d8a19fbcc4ac89ec21f4a7e7f797f041ad94b66e25173b4b74`,
audio DLL `75f931f6313ffab3fa10d1b5bb49a68c7d643b2126094fd6131dd555e9d7d4ba`
and unchanged A8E worker. Publication and fresh root-ready pass. The
[acceptance archive receipt](../archive/pro-native-edit-export-r5-2026-10-11.json)
binds this checkpoint's source and installed payload. The prior committed checkpoint is
`690aa8b192043173890c5e43ab636347b399467a` on `windows-native`, application
`3b5eee99965db27e0604fb6408109245edd9b0b8b1e50b62c75361edb0cc7093`.
The [native workflow](NATIVE_WORKFLOW_WINDOWS_2026-10-11.md) and
[hash-bound acceptance bundle](../archive/pro-native-pixel-credit-2026-10-11.json)
identify each measured binary, source, test and limitation. Later candidates must
qualify their changed behavior and bind their own build and runtime identities.

| Requirement | Authoritative evidence | Completion assessment |
|---|---|---|
| Native Windows application and root products | Root publication and live loaded-module records; shared application/controller source, Win32/Direct2D and Windows audio adapters; GTK forbidden by build configuration | Verified for the installed checkpoint. Any new helper must be part of the root product and exact build receipts. |
| Shared AIR theme and readable text | `src/view.ai` consumes the shared theme; `src/ui_text.ai` uses loaded native font metrics | Installed editor evidence remains valid. The unpublished r4 native workflow also verifies shared title pointer editing, Unicode and cancellation. |
| Real-media preview, audio and transport | Exact first-epoch native 1080p and fitted 4K/59.94 traces, unchanged strict parser, separate audio-device proof, native Play/Stop/rewind/scrub observations | Bounded recorded steady intervals pass. This does not prove whole-source or physical speaker/display synchronization. Fullscreen 4K is explicitly deferred by the user. |
| Linked video/audio lanes, frame bitmaps, time and scopes | Native V1 filmstrip/A1 waveform, click/drag seek with matching Program time/picture/histogram; retained raster and independent frame-identity gates | Verified for the installed checkpoint and tested mappings. |
| Dependable timeline editing with authored processing | Shared editor/linked-lane model checks, independent trim/copy/cut media gates and continuous-audio comparisons | The prior installed dynamics-cut defect is reproduced. Durable processing contexts, compound child padding and inward-edit repair pass r4/r5 combined suites and independent model/PCM checks below; r5 is now published. Delay/Reverb tail limitations remain explicit. |
| Save/open, undo, recovery and cancellation preserve authored work | Native private Save/Open plus shared project-safety, atomic-save, recovery and ownership gates | The r4 native workflow verifies idempotent Save/Open, title Cancel and one Undo/Redo; combined transaction and ownership gates pass. This is scoped to the tested workflows. |
| Titles can be corrected and rendered | Earlier 056E evidence plus separately bound r4/r5 native editing and independent glyph/source-picture/audio export checks | Shared caret/selection passes focused Windows/Linux checks. Both native workflows verify pointer editing, Unicode, Cancel and Undo/Redo; each 178-frame export passes independent checks at three authored picture positions. |
| Effects and automation are usable through exposed controls | [Control acceptance ledger](CONTROL_COVERAGE.md), per-effect worker mappings, parameter, ordering, precision, transition and export gates | The r4 native workflow verifies gain keys, Ease interpolation, Previous/Next and exact-key Delete; independent saved/reloaded preview/master comparisons also pass. Transition management is still missing. Unsupported animated audio parameters and complex-script text retain explicit limits. |
| Export is cancellable, preserves other files and can retry | Controlled ownership/publication regressions, background cancellation cases and r4 native output inspection | Exclusive ownership, no-replace publication and long-path checks pass. A long native export cancels and cleans up; reloading the saved short project and starting a fresh export succeeds. This does not prove same-target native retry. |
| Documentation, source and installed binaries agree | Exact r5 frozen source/build/publication/root-ready identities and accompanying archive's Git-index equality | R5 is installed after qualification and fresh root-ready passes. The publication commit is identifiable through Git history; the archive records the exact tested source. |

## Confirmed baseline defects and qualification work

The dynamics reproduction on the prior installed 3B5E application and AA40 worker
compares every intended stereo PCM value with an independently processed full
source. Original clips and unfiltered split/head-trim controls match exactly.
The accepted processed edits diverge at the edit boundary: Compressor differs by
up to 16,840 PCM16 codes, Gate by 1,383 and Limiter by 8,231. The retained private
reproduction receipt is `67570bed8c13bbc635fd391b532b745c699f40d197a48033e4ca6dd29e71780d`.
An unchanged model graph or an audible-output check cannot qualify those edits.

The r4 combined suite and native workflow now cover the implemented title,
keyframe and export changes. Independent PCM comparisons cover durable audio
history, including child shortening and subsequent inward 2x edits. The failures
that motivated those changes remain preserved below.

1. Implement transition selection, type, duration and removal through supported
   video-boundary controls, with transaction and independent pixel checks.
2. Resolve the remaining Delay/Reverb tail and unavailable full-history retime
   workflows without silently discarding authored processing history.

These are remaining parts of the original goal, not a smaller substitute goal.
The broader professional editing objective remains active until its requirements
are supported by current, appropriately scoped evidence.

## Candidate qualification and retained history

The completed unpublished candidate is `pro-native-edit-export-r4-2026-10-11`. Its
coherent build, full background suite, exact audio-device gate and native workflow
pass. R4 was not published because both cadence attempts fail the duration
requirement below. R5 subsequently qualifies the recorder-only repair and is
installed with its own exact identities and fresh root-ready passes. Its
accompanying archive retains the source and scoped qualification evidence.

The r4 application is
`396781b8fafca5e0f936628c3459cbe8b2b80068426ddb73483417cd9d1ef5a3`,
worker `a8e662712fd9812011b783b3abe8b239a17b1bddbb45434a2bf974c34a4495b7`
and audio DLL `8d9fadb12685e165af2b1197eeb2acc76d4b4236758280b019aa3d4f90ea6140`.
The following retained receipts bind those exact identities:

| r4 proof | Receipt SHA-256 |
|---|---|
| Coherent build | `94698679544f387743c4944beeb66f9d4d6b688a45d4829778cee99c8c2c47d5` |
| Full background suite, 72 fresh reports | `eba32d58adcf1b911d05877f65db2176d0426f5376c5fb5bf5308ea51ca764fa` |
| `device/receipt.json` | `c49add53bc58625b8aae0141e23d4de789643be9f317da9464e4e01016569fb1` |
| `native-workflow/receipt.json` | `b1022fb0c61e1b1fce2b544fd19befdcd9c2d8d938adcb8e47c2d9d64ad16550` |
| `native-title-export/attempt2/receipt.json` | `020d41bbdd587f154eb1e71997da94cd3d585d3953e374a2fb70609151aab8d2` |

The build/background receipts use the prefix
`build-windows/pro-native-edit-export-r4-2026-10-11`; device and native receipt
paths are inside the directory of that name. The device comparison reports
−0.307 ms interval drift, 0.455 ms phase range and no drain/resume shortfalls.
It does not measure physical speaker/display alignment.

Native observations verify V1 filmstrip/A1 waveform, Play/mute/unmute/Stop,
nonblank rewind, scrub/time/scopes and zoom, gain-key Ease/Previous/Next/Delete,
idempotent Save/Open, title pointer editing, Cancel, Unicode and one Undo/Redo.
Independent inspection of the native 178-frame H264/AAC export checks three
authored picture positions, over 99.9% expected glyph-interior coverage,
142,400 audio sample frames with AAC correlation 0.9999744, and worker PCM
within one code. These lossy picture checks are not bit-exact glyph rasterization.
The first short cancellation attempt finished before Escape and is retained;
a longer export with out-mark 76,700 was actively cancelled and cleaned up.
Reloading the saved short project and exporting afresh succeeds. Same-target
native retry is not established by that sequence.

Both r4 1080p cadence attempts retain their immutable raw traces and parser
reports under
`build-windows/pro-native-edit-export-r4-2026-10-11/cadence-1080/attempt1`
and `attempt2`. The recorder reaches its 50,000-row cap after only 105.1847076
and 108.6679303 steady native seconds respectively. Both fail the unchanged
minimum of 120 steady native/device seconds; neither is an accepted sustained
cadence result. Within the captured steady intervals there are no skipped or
repeated positions, backward/early or more-than-two-frame late presentations,
audio-queue drains or packet overwrites. Raw startup behavior remains retained
and separate from those fixed-exclusion steady statistics.

The per-loop trace can exhaust its row budget before the required duration;
the previously accepted playback source hashes are unchanged. These failures
do not demonstrate a newly broken playback scheduler. The r5 change repairs
the recorder and passes fresh qualification without reducing the cadence
duration or timing requirements.

The r5 recorder source is frozen and its coherent build passes all 69 targets.
Its private
Windows and Linux component runs each pass 12 cases and 2,641 checks. The
baseline run retains ten passing cases, one failed case and one skipped case
with 2,640 checks; the repeated identical poll assertion expects one row and
observes two. The exact fixed proof is
`build-windows/agent-recorder-retention-r5/fixed3/receipt.json`
(`eb394ffde3651a8bd95b0aa4c9cd2a0bc11683edc757b4c24bc5efa4b5d9d767`).
It binds `src/window_profile.ai`
(`01d8135c4ad9ac11488644d5949061d4fc3945d8c074235d0bd90b4be828bd72`)
and `tests/window_cache.ai`
(`3619b0df6cc0fe45cb85c245b772a2581bbd302691bfd538fc444ac12f906b2f`).

Retention preserves every presentation attempt, including failed and repeated
presentations, every actual device sample and input batch, and changes to
semantic state. Only identical poll-only rows are coalesced. A 16 ms threshold
retains the next available loop; it adds no scheduler deadline. The internal
`clock_sampled` marker preserves even unsuccessful samples with zero counts
and unavailable heard-frame values. The trace still has 46 columns and the
same 50,000-row cap; append-failure retirement and Stop flushing are unchanged.

`build-windows/pro-native-edit-export-r5-2026-10-11/recorder-only-delta.json`
(`15185ad45c88d3f492d4d85ab9b6884273d6118fe955961ef67415466f9e9657`)
confirms that only those two files change from r4. SDK, worker, main/scheduler,
parser, shared runtime and protected assets remain identical. This component
proof is separate from the r5 combined build and does not establish its full
background suite, device, native workflow, cadence or publication result.

The r5 coherent build receipt is
`c6fa429d185c135b1c7a51236889a9aaacf563b76c901c75139b4b90304eab6d`.
It binds application
`b07975912822d2d8a19fbcc4ac89ec21f4a7e7f797f041ad94b66e25173b4b74`
and audio DLL `75f931f6313ffab3fa10d1b5bb49a68c7d643b2126094fd6131dd555e9d7d4ba`;
the A8E worker remains unchanged. Its first full background attempt stops before
the nested-edit-context cases: `tests/audio_nested_edit_context.py` correctly
refuses to replace the existing exclusive
`build-windows/audio-nested-edit-context.json`, which is the exact r4 report.
This is a report collision, not a nested PCM case failure. The failed log,
start/exit/frozen identities, 47 fresh partial reports and relocated stale report
are preserved under
`build-windows/pro-native-edit-export-r5-2026-10-11/background-failure`;
the immutable r4 background proof is unchanged.

A fresh complete invocation of the same `tests/windows.ps1` passes as repeat1,
with 72 fresh reports and exclusive alternate background receipts/logs. There
is no source or threshold change. The accepted receipt is
`build-windows/pro-native-edit-export-r5-2026-10-11-repeat1-background-receipt.json`
(`7037dd636eb1a8629c938f20de98c54ff852f1695679688af8e03155b31cef45`).
The original failed report-collision evidence remains separate and unchanged.
The exact r5 device gate passes:
`build-windows/pro-native-edit-export-r5-2026-10-11/device/receipt.json`
(`b3158f100cfe4d8861fa7cfcf6996f7e62d2552bea28eb495b7178575141d1bf`)
binds the B079 application and actually loaded 75F9 audio DLL. Its requested
20-second clock run records an 18.997-second measured interval, −0.320 ms drift,
0.430 ms phase range, no drain/resume shortfalls, restart at zero and resume
within one millisecond. This is an isolated waveOut clock/meters/Stop check;
it makes no physical hearing or speaker/display synchronization claim.

The r5 native workflow passes with receipt
`build-windows/pro-native-edit-export-r5-2026-10-11/native-workflow/receipt.json`
(`9aa1b8ee70775d44a4476da7b3e493cdaf20029596c2364c202f2d0d0de88210`).
It covers private legacy 1080p migration to V1 filmstrip/A1 waveform, Program
Play with active meters, A1 mute/unmute, Stop retaining the picture, nonblank
Start at zero, scrubbed Program/status at 4:21 with populated
Histogram/RGB/Luma scopes and zoom. Native Save/Open preserves the two-clip
linked layout idempotently. Title pointer selection and Cancel, replacement of
X with é, one Undo/Redo and Save as are observed. The owned process closes
normally and its absence is verified.

An active full-range native export cancels and cleans up. Reopening the saved
178-frame short range and exporting to the fresh, different destination
`Native title retry.mp4` succeeds. Fresh same-target native retry and new
keyframe GUI dispatch were not exercised on r5; those earlier keyframe
observations retain their r4 scope.

Independent inspection of the r5 export passes with receipt
`build-windows/pro-native-edit-export-r5-2026-10-11/native-title-export/attempt1/receipt.json`
(`b07488ac3442dec8b1a1befeded5957f285d97dcea1235f0f349e49d90ae67a6`).
The 178-frame 1920×1080p60 H264/AAC output is checked at picture positions
0, 89 and 177 against independently decoded source pixels and Segoe UI font
interiors. Expected glyph-interior coverage exceeds 99.9%; all three source
picture comparisons pass the existing bounds. AAC has exactly 142,400 sample
frames and zero-shift correlation 0.9999744232; worker PCM is within one code.
Project, source and exported movie hashes remain unchanged during inspection,
and the cancelled destination remains absent. This bounded lossy-output proof
does not establish bit-exact glyph anti-aliasing, whole-source verification,
physical hearing or playback cadence.

R5's first 1080p cadence attempt passes the unchanged strict gate:
`build-windows/pro-native-edit-export-r5-2026-10-11/cadence-1080/attempt1/accepted-summary.json`
binds raw trace `216460418ffb70760959e339adf77b2c848a58930a48e8feb1356b5c5a8aff22`.
The steady interval records 168.0685882 native seconds and 168.065770833 device
seconds, with 10,085 consecutive pictures at 59.999314 pictures/s and maximum
picture gap 30.2906 ms. Steady omissions, repeats, backward/early or late
presentations, empty audio queues and packet overwrites are zero; post-present
lag is at most one frame. This remains an ordinary editor fitted-monitor
measurement with fixed first-second/final-half-second parser exclusions and
the full raw trace retained. The raw selected epoch still records one repeated
presentation, two empty-queue rows and a 143.7372 ms maximum picture gap;
those are not relabeled as steady results. This is
not physical scanout, fullscreen 4K, compound 4K60 or whole-source acceptance.

R5's first fitted 4K/59.94 cadence attempt also passes:
`build-windows/pro-native-edit-export-r5-2026-10-11/cadence-4k/attempt1/accepted-summary.json`
binds raw trace `a1882e7a043a28beec934cf8b1f6db4a0382bfe5920692f57aadb8ac365348b5`.
Its steady interval is 199.4015194 native seconds and 199.398166667 device
seconds, with 11,953 consecutive pictures at 59.9393627 pictures/s and maximum
gap 24.9929 ms. Steady omissions, repeats, backward/early/stale presentations,
empty audio queues and overwrites are zero; post-present lag is zero. The two
input rows remain in the measurement without transport interruption. The raw
selected epoch retains three repeats, two empty-queue rows and a 248.3198 ms
maximum gap separately from steady results. The same fitted-monitor and
physical/fullscreen/whole-source limits apply. Its owned process closes
normally and is verified absent.

Exact r5 root publication passes with
`build-windows/pro-native-edit-export-r5-2026-10-11-publication.json`
(`8c2d22d900c0c3b6bd751c8dfc65702a261d8038b3f65783b3e6616a95549aa1`).
It binds B079/75F9/A8E and the B4A file-publication helper, selects the accepted
repeat1 background receipt/log/exit and preserves the original failed attempt.
Protected assets are unchanged; the shared MM-AIR runtime remains in use with
no separate FFmpeg bundle.

Fresh root-ready passes with
`build-windows/pro-native-edit-export-r5-2026-10-11-root-ready.json`
(`5ded0cb74e5a45540deef94841d5629e90af55e180f0f85e6ab8bfadf49b17db`).
The loaded-module record confirms the root B079 application and 75F9 audio
DLL. Native Open of the private saved linked 1080p project shows two clips,
V1 filmstrip only and A1 waveform only, with both monitors populated at zero.
Program Play changes the picture and advances time/status/playhead together
to 6:12 with active stereo meters while Source stays paused at zero. Stop
at 13:46 retains the picture and clears meters; Start returns to a nonblank
paused first frame. The root editor is left open paused on that project.
The accompanying archive records source and evidence; the publication commit is identifiable
through Git history. Passing these bounded checkpoints does not complete
the broader professional editing goal; the r4 keyframe GUI observations
remain separately scoped historical proof.

The r3 background run passes the repaired 128-bitmap compound gate and the
980-check audio-context model, but stops at the real preview-stream fixture.
The full failed log and partial reports are preserved; partial results do not
qualify the whole suite. The unchanged client reproduces the failure. Its
picture fixture ignored a refused 2x edit after retaining a 60-frame audible
processing window on a 60-frame physical source. The r4 fixture explicitly
authors a video-only clip and checks every reverse/trim/rate setter result;
its private native run passes all original pixel/time/deadline assertions.
The shared source still includes audio for the separate audio gates. The real
linked audio rate-after-trim restriction remains: an edit requiring unavailable
full-history source handles is refused rather than resetting processing.

The first `pro-native-edit-export-2026-10-11` combined build passed, but its full
background suite stopped at the independent compound timeline bitmap gate. A silent video-only nested
clip acquired an audio context after trimming, which refused its requested 1.25
speed edit; the renderer then correctly sampled the unchanged rate. The failed
run, binary identities and report are retained privately. The unchanged audible
compound waveform follow-up passes all 24 cases. The subsequent r2 build was
aborted before qualification to correct a portable test-registration typo; it
has no full-suite or native acceptance claim. Both histories are preserved.

The r4 source retains bounded descendant-audio inspection: silent video-only,
empty and masked children without potential audio effects do not acquire
fictitious processing history. Existing contexts are retained, and unknown/cyclic
or over-budget graphs are conservative.
The unchanged compound bitmap oracle passes 128 actual bitmaps with its original
pixel and source-time limits. That private bitmap proof is scoped to the first
descendant repair; the r4 full background suite also passes the integrated gate.

- Title caret, Unicode selection and middle insertion pass 266 checks on each
  of Windows and Linux. The r4 native workflow additionally verifies pointer
  editing, cancellation and saved Unicode text on the combined application.
- Exclusive export ownership and atomic publication pass 12 Windows and 13
  Linux cases, including late destinations, competing writers and cancellation.
- The shared audio-context model and codec now pass nine cases and 980 checks on
  each operating system, retaining all 795 original assertions and adding 185
  checks for silent/masked descendants, retained histories, child shortening,
  2x forward/reverse inward edits, Save/Open and Undo/Redo. The preceding private
  version fails the new inward-edit case. Revision 3 retains the
  original processing span; revisions 1 and 2 remain readable, and the original
  reader explicitly refuses revision 3.
- Independent nested processing comparisons pass 16 cases: 6,528,000 whole,
  retained-chunk and fresh-seek PCM values and 600 peak buckets match exactly.
  The authored 120-frame analysis window survives a child shortened to 90 frames;
  its missing suffix is zero-padded before parent DSP and the edited body is then
  cropped. Subsequent 2x head/tail edits preserve that history. Flat media handles,
  outward-new-history bounds, fractional phase, fade and key guards remain strict.
- Windows long-session-path handling passes 13 controlled export checks. The
  first deep-path failure is retained: an ordinary marker read failed at 262
  characters although an extended-path read found the same published session.
  Missing reports still fail; failed startup releases the reservation and joins
  its owned controlled worker. This does not constitute native export quality proof.
- The Win32 second-button capture regression fails on the original adapter and
  passes all 25 checks after repair. The fixture injects capture ownership into
  the actual native message handler; it does not operate the desktop.
- Keyframe navigation, deletion and interpolation pass eight cases and 463
  checks on Windows and Linux. Actual controller dispatch followed by save/open
  produces six exact preview pictures and 24 exact native master frames against
  independent source and curve references. Inspector compatibility remains
  27 cases and 266 checks. The r4 native gain-key workflow verifies Ease,
  Previous/Next and Delete through the combined candidate's controls.

- Clip-edge Snap passes eight cases and 322 checks on Windows and Linux. Actual
  pointer gestures cover interior grabs, both trim handles, linked geometry,
  nearest legal source boundaries, locks, Undo/Redo and the eight-pixel threshold
  at high zoom. The original code fails four of the six initial regression cases.

The private DSP comparisons pass 78 edited/original cases and four lossless
exports, with exact PCM and waveform comparisons and unchanged limits. A longer
source exposed a tempo-processing tail that the initial fixed-body path would
discard. The repaired whole-render path retains the original tail on the final
surviving original-end piece; twelve actual SDK edit/tail comparisons pass.
Context-free whole exports retain legacy EOF draining. Tail trim keeps the
original processed prefix and removes the original-end tail; it does not create
a new effect tail at the edited endpoint. Native tail requests exceeding the
five-second total budget fail with a code instead of truncating output.

The r4 combined build/background suite and fresh native title/export and device
checks pass, but its two capped cadence traces fail the duration requirement.
The recorder-only r5 passes both cadence gates and is published. Delay and
Reverb still refuse cuts that cannot preserve their tails beyond the authored
body. Normalize and nested processing retain the full float cache. Those
remaining workflows are explicitly scoped and not qualified by the direct
causal-stream checks.

## Next exposed editing gap

The transition action currently authors a 24-frame dissolve at the selected
clip's end. There is no seam selection or exposed type, duration or removal
control. The next slice should reuse the SDK boundary lookup and stable
transition IDs, validate supported video boundaries before capturing history,
and expose the supported types, duration and Remove in Properties. Refused or
unchanged requests must preserve Redo. Native dispatch, persistence and
independent transition pixels still need qualification; existing upper-lane and
incoming-effect renderer limits must remain explicit.
