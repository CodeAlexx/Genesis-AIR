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

## F718 cadence failures before the pixel-credit candidate

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
native socket-buffer probe led to the bounded component candidate below. These
results do not replace the failed cadence measurements.

## Published pixel-credit checkpoint: bounded cadence and native workflow

The pixel lane uses 16×64 KiB messages, retaining the channel's 1 MiB payload
bound. The reusable Windows adapter changes only OS-verified loopback TCP peers:
each connected/accepted endpoint requests and verifies a 1 MiB send allowance.
Remote TCP and UDP retain their defaults. Local command/metadata lanes also use
this policy, so two bidirectional TCP lanes provide 4 MiB send allowance per Link.
This is an allowance, not measured committed kernel memory or total application
storage. Receive buffers, channel framing, CPU pixel packets and prepared frames
remain separate resources.

The maintained FIFO fixture restores the original Japanese string and passes
10 cases / 134 checks on both Windows and Linux. Earlier private mojibake and
failed credit-only receipts remain historical. The native address classifier
passes 20 checks and buffer policy passes 19. Separate IPv4/IPv6 resource runs
each open 32 TCP pairs, verify 33,603,584 real bytes and close all owned handles
with unchanged before/after handle counts. Their 64 connected endpoints expose
64 MiB configured send allowance; no aggregate-memory measurement is inferred.

The shared Direct2D presenter keeps `D2D1_PRESENT_OPTIONS_NONE` as the SDK default.
Genesis's isolated runtime build opts into `D2D1_PRESENT_OPTIONS_IMMEDIATELY`;
initial and recreated targets use the same option. Driver reporting distinguishes
Direct2D from GDI, whose presentation options are not applicable. Each private
default/immediate component variant passes 97 checks and 2,150,400 exact RGB
comparisons covering resize, retained/next images, injected target recreation,
GDI and construction-failure fallback. Recreation was injected after a real
successful EndDraw, not produced by actual device loss. The component windows
closed normally; they do not qualify the combined editor's cadence.

The display snapshot reports approximately 59.951 Hz monitor timing and
59.953 Hz DWM composition. Immediate presentation removes the render target's
refresh wait; it does not prove that every 60 fps software submission reaches
physical scanout. Exact software clock/queue checks, physical display cadence and
speaker/photon alignment remain separate scopes. No physical synchronization,
fullscreen or compound-4K60 acceptance is claimed.

The `pro-native-pixel-credit-2026-10-11` transport candidate builds coherently with
application `3b5eee99965db27e0604fb6408109245edd9b0b8b1e50b62c75361edb0cc7093`
and audio DLL `005f5f01f943a7183919f706fa3869356f8fea99574d09b781ff0340fb91ab59`.
Build receipt `f20f5fe40b4e7fdae74374528dab4652594027c943f0abdcce4fde4a0e5049e7`
binds this candidate. The first full background attempt fails the unchanged
`tests/playback_timing.py` lossless picture-gap limit: 355.1998 ms exceeds 250 ms.
The trace already owns a ready picture before one 327.8562 ms consumer-loop stall;
steady provider timing remains within 3 ms without errors. This localizes the
observed gap, not its initiating system cause. The failed exit/log and complete
raw timing evidence remain retained.

An unchanged focused repeat passes with 1,006 observations, 240 pictures,
42.6766 ms maximum gap and 33.525 ms lag. It does not replace the failed full gate.
A second full background invocation of the same 3B5E build passes with exit zero
and 64 fresh report snapshots, retained in its exclusive `repeat1` log/start/receipt.
The accepted log digest is
`90888daac646df50c62548b4ec0204119e35ebea9fb19bb3b86afc0cdc9126f5`.
Its maintained playback fixture records 1,008 observations, 240 pictures,
42.4514 ms maximum gap, 33.3541667 ms lag and no observed underrun. This result
leaves the first failed full attempt and earlier focused pass intact; it does not
classify or repair the first consumer stall's cause.

The exact 3B5E/005F audio-device gate passes with receipt
`ccbed5511975d81940e738fc823aba5f7d7a8a9578e9b97a1fb24a72a055b79c`.
Its requested twenty-second clock test measures 18.99 seconds and 2,378 polls,
with −0.362 ms interval drift, 0.416 ms phase range and zero drained/resumed
shortfall. Stereo, hard-left, silent, meter and Stop fixtures bind the actual
loaded 005F module. This isolated device proof does not establish physical hearing
or speaker/display alignment.

The unchanged native menu-timing parser passes both predeclared first Program
epochs on this exact candidate:

| Source / ordinary monitor | Native steady seconds | Device steady seconds | Changed pictures / frame range | Pictures/s | Maximum gap |
| --- | ---: | ---: | --- | ---: | ---: |
| 1080p60 / fitted 480×270 | 137.6867878 | 137.6844792 | 8,262 / 60–8,321 | 59.9984946413 | 20.244 ms |
| 4K/59.94 / fitted 480×270 | 166.0013750 | 165.9985625 | 9,951 / 60–10,010 | 59.9392625513 | 24.358 ms |

Each steady interval has zero omitted or repeated positions, backward/early
presentations, presentations more than two frames late, device-queue drains and
packet overwrites. Maximum after-presentation lag is zero frames. The fixed
selection remains the first second and final half-second excluded, at least 120
steady native/device seconds required, and no input rows discarded.

Both recorders reach their automatic 50,000-row limit with complete 46-column
rows; the closed original and immutable copied traces are byte-identical. The
qualified intervals exceed the unchanged duration gate without extending the
recorder cap or selecting a later epoch. Every raw row remains preserved: the
1080p raw selected epoch contains one repeat, two startup queue drains and a
139.6834 ms maximum gap; 4K contains two repeats, two startup drains and a
239.9414 ms maximum gap. These raw values are not relabeled as steady zero-drop
results. Raw digests are
`b855fc5c3a05ed8a18bda3c091a2b6b1155485e4f2e90a2647159e4c314b1b77`
and `c1f6ad96737fd7b024cadb5a9b69554431f34977a7ac092623e3769192eec432`.
The new build-bound archive adapter preserves the original parser reports and
derives app/worker/audio identity from the predeclared coherent build receipt;
the historical F718 adapter remains unchanged.

Fresh native workflow receipt
`b4b398b1212bd107f508cc5aa79712f4edef94286ae5c60de07cf166cf11804d`
binds the actual loaded 005F module, exact 3B5E build and saved graph. Its 4K
observations include nonblank rewind to zero,
seek to `00:00:06:57` showing the snake picture with changed histogram/RGB/luma,
and drag to `00:00:02:58` showing the beach with matching marker, picture and
scopes. V1 filmstrip, A1 waveform and A1 gain 0.60 / pan −0.50 respond. Program
Play changes pictures with active postmix stereo meters; Mute leaves silent
meters while video advances, and Unmute restores active output. Program Stop
pauses both transports and leaves empty meters. Independent Source Play changes
Source picture/time with active output while Program remains parked; Source Stop
leaves silent output. Private native Save as/Open restores both positions, mixer
values, separate lanes and decoded pictures after asynchronous completion. The
saved graph is independently checked, and the owned test process closes normally.
This final native scope covers those observations; title/export interaction was
not repeated on 3B5E and retains its historical 056E proof.

Root publication passes using the explicitly selected `repeat1` background
receipt/log/exit. Published app 3B5E, audio 005F and worker AA40 match the coherent
build; the original failed full attempt remains separately recorded. Protected
projects/media remain unchanged and the shared MM-AIR runtime policy is preserved.
Fresh root-ready passes with receipt
`d7b3a988ecfe5c3fc6930519e2f1f5b42de33dae39191e3b64f5e660fc2df370`.
The maximized published editor opens the private 1080p project through its native
chooser, showing populated Source/Program pictures paused at `00:00:00:00`,
V1 filmstrip without waveform and A1's separate waveform. Its actual loaded root
005F module capture is bound by
`6555e2966aa418d7cb35a7b3e5290ff4239780bee3815e64dc54067e960782f5`.
This root-ready check confirms the installed state; its cadence remains separately
qualified by the exact build-bound traces above.

The old verified-stage archive plan remains unexecuted. The final
[evidence bundle](../archive/pro-native-pixel-credit-2026-10-11.tar.gz) and
[archive receipt](../archive/pro-native-pixel-credit-2026-10-11.json) retain the
qualified source and validation results. The receipt records the bundle's SHA.
The bundle retains the F718 failures and earlier 056E evidence,
source identities and sanitized driver artifacts with their original scope.
Focused passes above do not replace those gates. Fullscreen 4K remains deferred.
Genesis reuses MM-AIR's runtime; no separate FFmpeg executable/DLL bundle is added.
