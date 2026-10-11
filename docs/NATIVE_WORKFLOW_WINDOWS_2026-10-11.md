# Native Windows editing workflow, 2026-10-11

This continuation qualifies specific workflows on exact binaries. The broader
professional-editing goal remains active. Tests use private project copies;
the supplied 1080p60 and 4K media and original projects remain unchanged.

## Installed linked-lane build

Native desktop observations bind application `06af1ab848cf1225c3bbb7f9896dd6dbdfa3148df95b8ed9f5241c9b20ca687b`
and actual loaded audio DLL `bc5c962ba9a002bde1dab105e900f4449c2e0d0a41e2dd2bbd408b01dd18659a`.
The private 1080p60 project opens with V1 frame thumbnails and A1 processed
waveform. Program playback, Gain/Pan edits, mute/unmute, Source audition,
Stop, timeline seek and rewind to populated frame zero respond through native UI.
After a native Open dialog remains open for more than two seconds, Cancel leaves
the transport paused; a new Source Play recovers.

With V1 selected, Clip Gain 0.60 and low EQ +2.50 are saved only on the linked A1
clip. V1 retains video-only stream membership, unity gain and zero pan. Track
Gain 0.45 and Pan -0.95 persist on A1. A native Split at frame 209 produces two
V/A pairs with matching source positions. One Undo restores the original pair;
Redo and Save reproduce the split project bytes exactly. These observations do
not measure frame cadence or physical speaker/display alignment.

That BC5C audio DLL separately passes the unchanged hardware-clock gate:
20 seconds, 24 completed buffers and 2,390 polls, -0.286 ms clock drift and
0.463 ms phase error. Drain, restart, pause/resume and Stop checks pass. The
coherent device client also passes ordinary stereo, hard-left and silent PCM
fixtures. Device-component receipts cannot establish whole-application cadence
or physical speaker latency.

## Title drafts and runtime timing recorder

Title drafts now retain their opening project, sequence, clip, filter kind and
original content. Background pointer, menu, wheel and shortcut input is blocked.
An invalidated opening target returns `GA_PROMPT_TARGET` without document/history
changes. Shift+Enter inserts a line; Enter accepts; Escape cancels. Unicode
multiline content survives Save/Open. Editing supports append, Ctrl+A replacement
and grapheme Backspace; arbitrary caret navigation is not added.

Focused Windows and Linux inspector gates each pass 24 cases / 228 checks,
including exact two-line alpha coverage. The initial independent raster oracle
incorrectly used maximum alpha for two overlapping shadow pixels. The corrected
source-over union is `round(A + B - A*B/255)`; all 129,600 alpha pixels match
exactly. Failed reports and original rasters are retained; no renderer tolerance
changes were made. A further native key/text sequence test reproduced duplicate
newlines from Ctrl+Shift+Enter before the fix. Only Shift+Enter without Control
inserts a line; Ctrl+Shift+Enter commits once and its following native LF is ignored.

Help → Record playback timing creates an exclusive session-local trace without
replacing older traces. Stop/EOF flushes while recording remains armed; Help-off
and close finish it. The existing 46-column schema, 128-row buffer and 50,000-row
limit remain. Create/write failures report `GA_WINDOW_PROFILE_CREATE` or
`GA_WINDOW_PROFILE_WRITE` and retire the recorder. Initial Windows recorder/cache
checks pass nine cases / 2,543 checks; the final Stop/close buffering gate passes
ten / 2,551. The latter simulates audio-retirement sequencing at the component
boundary and does not claim native waveOut behavior. Startup environment profiling
remains compatible.

## Historical 056E native title, export and recorder proof

The private Stop-order candidate binds application
`056eafa3a01f0f1dd594d2a8e201b4d72d044bdb2a3297c5b5806009080f238c`
and actually loaded audio DLL
`5a004885dfff4604a6826e9500f2cfcb640240db57f195d23cbfe84bef8ced85`.
Native UI verifies a two-line Unicode title, Shift+Enter and Ctrl+Shift+Enter,
Cancel, one Undo/Redo, outside-modal input blocking, Save As and native reopen.
V1 retains frame thumbnails and A1 its processed waveform. Program playback,
Solo/Mute/unmute, Stop/Start, seek to frame 178 and changing histogram/parade/luma
respond with the rendered title. These observations belong to 056E, not a later
binary merely sharing its application source.

Native Escape cancels export without leaving the target; retry writes the authored
range `[0,178)`. Independent verification counts 178 H.264/AAC frames at 1080p60
and checks original-source pictures plus both title interiors at frames 0, 89 and 177.
Title interior coverage is at least 0.999291 against the 0.93 minimum. Audio has
142,400 decoded/reference sample frames, zero-shift AAC correlation 0.9999744232
and at most one PCM16 code of worker-reference difference. This is a short lossy
export with three picture probes, not an all-pixel/whole-source comparison.
The original five-pixel font-interior mask failed its independent minimum-area
precondition. A font-only declaration selects a three-pixel mask with 1,608 and
2,822 interior pixels before inspecting exported pixels; both verifier versions
and the failed report remain retained.

The native Help recorder creates a 46-column trace. Play/Stop and titlebar Close
flush 6,007 complete rows with stopped device and zero final queue/credits.
The short trace ran during compilation and qualifies lifecycle only, not cadence.
The owned UI process exited. The exact 5A0048 waveOut component proof remains
separately scoped; neither proof establishes physical speaker/photon timing.

## Fresh F718 device proof and source provenance

The verified build binds application
`f7185c70a51025c04b9ee33c490bbbf9c65418ccb619a067faba3ca98cc65292`
and audio DLL
`342dc9ae62327f98a90b6387697e69dce37cce5414be821afe9a560472b816e6`.
Its coherent build receipt is
`e471644626cfda1511ef7131d3841eaed72f8c80ba0db281b50c0ee5ff6db960`.
The fresh device client actually loads 342D and passes stereo, hard-left, silence,
meters and Stop. The unchanged requested 20-second clock gate measures 18.994 seconds,
2,372 polls and 24 completed buffers: drift −0.318 ms, phase range 0.621 ms,
zero drain/resume shortfall, restart at zero and resume within one millisecond.
Receipt `575cb87f40a288f5f7fb71c7732ca650afb206de1dc2e5dbf2f92fe5c2580ac3`
binds this exact build/module and its driver. It is a device-component proof,
not physical hearing or whole-application A/V cadence.

Production equality receipt
`ca1c62d91ba6fd6bf34d0ed9ec165da05da64c8f5540ea55c681a578542e2da5`
records identical application/adapter/overlay source and generated main C between
056E and F718. Only `tests/headless.ai` and its expected facts changed.
Source equality is provenance; the cause of different executable/DLL bytes is
not classified as metadata-only without PE section evidence. Historical 056E UI,
export and 5A0048 device results retain their original scope.

Fresh F718 native workflow receipt
`021790a08877c0f73d5bcb83797e4d675f3948bd03f61508bc9f66a60f9e38c5`
binds the actually loaded 342D module. Program Play advances with changed pictures
and balanced live meters at A1 track Gain 0.60 and Pan −0.05. Stop at 6:02 leaves
silent meters; Start restores nonblank frame zero. Seek to frame 178 updates the
picture and time after asynchronous decode. V1 filmstrip and A1 processed waveform
remain populated. Independent Source Play advances to 1:25:19 while Program holds
frame 178; Source Stop at 1:31:23 leaves both transports paused and silent.
Native Save As preserves the private project. The owned process closes normally.
This short fresh workflow does not relabel the broader 056E title/export proof or
establish sustained cadence or physical speaker/display alignment.

## Coherent continuation acceptance

The first frozen `pro-native-title-timing-2026-10-11` candidate compiled coherently
as `71a593fee81b0d43d1786d723ff05b755531623c8fe99951469148d502ae7ab8`.
It was not launched or published. Review found that recorder append/flush could
precede native device retirement after Stop or close. The corrected candidate
defers those writes until audio service has retired the device, including the
last closing row when its authored transport remains playing. First-candidate
source/build evidence remains retained.

The 056E full background run then failed only the old `menu_access_opens_file`
fixture expectation: it tried opening a background menu while a Save prompt was
active. Production modal blocking remains unchanged. The corrected fixture asserts
blocked input first, cancels the prompt, then tests File-menu opening. Focused
Windows/Linux headless gates each pass 154 saved facts plus 3 native-drop checks;
the original failed full log, source and output remain retained. This focused
correction does not constitute a complete Windows pass.

The new `pro-native-title-timing-verified-2026-10-11` build passes the complete
`tests/windows.ps1 -BackgroundOnly` gate with exit zero. Its receipt binds 63 fresh
report snapshots to F718, AA40, the frozen source and build above. The immutable
background log digest is
`da0b03fb50dcb45566e58a1f99d71a0e43965d9bfc0b8ed282afb8b1b7861f96`.
Background scope includes native CPU/OpenCL pixels and file-based media/audio
checks; native UI, physical sound and sustained presentation are separate proofs.

Publication verifies the root F718 application, 342D audio DLL and unchanged AA40
worker, with protected assets unchanged and the shared MM-AIR runtime preserved.
The installed root opens a private 1080p project with separate V1/A1 lanes.
The later cadence measurements below fail; publication of the binaries does not
qualify cadence or complete this acceptance checkpoint. The owned F718 native
window closes normally after the measurements.

## F718 cadence failures and pending pixel-credit candidate

The Help recorder was armed before Play. The unchanged parser selects the first
predeclared uninterrupted Program epoch, excluding the fixed first second and
final half-second while retaining every raw epoch and trace row. The 1080p run
records 148.8840964 steady seconds at 59.9526760469 changed pictures/s but omits
five frame positions. It has no early/backward presentation, more-than-two-frame
late presentation, steady device-queue drain or packet overwrite. It still fails
the required consecutive-picture gate.

The 4K 59.94 fps source is shown in the ordinary fitted 480×270 monitor. Its
169.6265217 steady seconds average 59.8845033 changed pictures/s, with nine omitted
positions and five presentations more than two frames late. Picture credit is
empty at those late events. These are not fullscreen or compound-4K measurements.
Both failures retain their raw `window-final.tsv`, identity, launch, capture and
analysis under `cadence-1080` and `cadence-4k`; neither report is relabeled as passed.

Increasing channel credits while retaining the one-megabyte transport bound
passed the focused Linux fixture but failed the Windows held-frame and
cancellation/recovery checks. That candidate was rejected; the original
transport source and maintained fixture were restored exactly. A private
native socket-buffer probe and prototype are under investigation. Their results
do not qualify a production change or replace the failed cadence measurements.

The `pro-native-pixel-credit-2026-10-11` transport candidate is a separate pending
continuation. New source/build/background, exact device/native, sustained cadence,
root-ready and publication evidence must agree before its public archive can be
created. The old verified-stage archive plan remains unexecuted. The new planned
bundle is `archive/pro-native-pixel-credit-2026-10-11.tar.gz`, with a separate
archive receipt. Its builder retains the F718 failures and earlier 056E evidence,
source identities and sanitized driver artifacts with their original scope.
Focused passes above do not replace those gates. Fullscreen 4K remains deferred.
Genesis reuses MM-AIR's runtime; no separate FFmpeg executable/DLL bundle is added.
