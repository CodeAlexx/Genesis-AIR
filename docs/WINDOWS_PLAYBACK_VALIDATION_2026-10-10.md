# Native playback and locked editing validation

This work tests the ordinary maximized Win32 editor with fitted 480x270 monitors.
Fullscreen 4K remains deferred. Genesis uses the existing MM-AIR media runtime;
no additional FFmpeg executable or codec DLL bundle is introduced.

## Locked destructive edits

The shared editor now refuses Lift and Ripple Delete on a locked track. Application
Lift, Ripple Delete and track removal prepare a candidate document and capture an
Undo snapshot only after a successful mutation. Refused edits retain the document,
selection, dirty state, revisions and complete Undo/Redo branches. Refusals use
`GA_EDIT_LOCKED`, `GA_EDIT_TARGET` and `GA_EDIT_CONTEXT` diagnostics.

The new safety fixture passes seven cases and 29 checks on Windows, Linux and the
AIR interpreter. Existing trim, history and clipboard contracts also pass on all
three paths. A private Windows build using the downloaded 1080p clip verified
Delete, Shift+Delete, painted Lift/Ripple and lane removal refusals. Unlocked Lift
left the authored gap; Ripple closed it; one Undo restored each operation. Scrubbed
picture/time, timeline bitmaps, processed waveforms, histogram, RGB parade, luma
waveform, embedded-audio mute/unmute, Stop and frame-zero rewind were also observed.
Only disposable project copies were saved or closed.

## Timing experiments retained, including failures

The earlier measured runs and the qualified fixed-eight runs use the
supplied AV1/PQ 59.94-fps source and unchanged AA40 media worker. The reported rate counts changes in presented frame positions
over native EndDraw elapsed time. Steady statistics exclude the first 1.0 seconds
of device samples and the final 0.5 seconds before manual Stop. Complete raw epochs
remain retained. These exclusions do not establish zero-drop playback.

| Application | Raw epoch | Steady distinct pictures/s | Skipped positions | Presentations more than two frames late | Result |
|---|---:|---:|---:|---:|---|
| Published C6D2 baseline | 187.533 s | 59.8528 | 19 | 4 | Fail |
| DF78 late-reservation experiment | 187.615 s | 59.0222 | 170 | 798 | Fail; withheld |
| 13258 policy reversal | 193.437 s | 59.8902 | 9 | 2 | Fail; withheld |
| AF337 picture preroll, fitted timeline | 195.823 s | 59.8857 | 9 | 1 | Fail; withheld |
| 9676 ordered windows, three-picture budget | 179.276 s | 59.8456 | 17 | 5 | Fail; withheld |
| 8892 fixed-eight reserve, qualified retry | 120.095 s | 59.9398 | 0 | 0 | Pass; private, publication pending |
| BDF3 coherent profile build | 133.122 s | 59.9393 | 0 | 0 | Cadence pass; live Gain UI failure, withheld |
| Published 1A49 recovery build | 133.890 s | 59.9377 | 0 | 0 | Full-suite, editing/export, cadence, publication and root-ready pass |

The AF337 run explicitly fitted the complete timeline before Play. Its steady
paint median was 1.786 ms, compared with approximately 1.23 ms in the earlier
runs. These are individual observations, rather than a controlled claim that
preroll alone improved cadence.

The DF78 experiment held an in-flight decode through two heard frames of lateness
and recovered at current time. That kept requesting already-late pictures and
eventually jumped over two positions. All 170 steady omissions were never
requested. This policy was removed; its failed traces remain part of the evidence.

The reversal restores reservation of on-time requests, current-frame recovery
for one-frame lateness and bounded future recovery for larger backlog. Its nine
omissions were requested but never delivered. Neither measured candidate overwrote
completed packets, presented early pictures or drained the steady audio queue.

The reversal's remaining two late pictures arrived already two frames behind.
Request-to-consumption intervals were 45.17 and 39.45 ms; normal 5.38 and 5.69 ms
EndDraw intervals then crossed the third-frame boundary. No owned future picture
was available during either event. The entire steady reversal run had a prepared
future-picture maximum of zero. The trace does not timestamp worker packet arrival,
so it cannot distinguish decode delay from all wake/consumption delays.

## Picture preroll and refill experiments

The AF337 experiment prepares two actual consecutive future pictures before queuing
the first authored PCM block. `waveOutOpen` opens an empty device; the first
`waveOutWrite` starts the authored audio. Readiness validates the picture epoch,
monitor mode, origin and actual owned frame positions; short sequence tails need
only their available frames. Stop, seek, edits, media replacement and errors must
retire both pending pictures and pending PCM. Picture priming receives a bounded
timeout after first PCM readiness.

The fresh private build passes 14 queue cases/136 checks and 12 lifecycle
cases/69 checks. Native startup actually owned pictures 1 and 2 with zero device
samples before the first PCM queue. Separate completed-image identities for
Program and Source prevent an unrelated repaint from relabeling stale origin
pixels. Source identity includes its selected source ID. Stop also removes an
already completed caller-owned PCM file before its channel receipt arrives;
the serial producer checks supersession again after rendering and cleans late
cancelled output.

The reserve survived through frame 302. A roughly 40 ms request-to-receipt
interval for frame 305 emptied it. Issuing one decode per native display refresh
then prevented the reserve from refilling, even when decoding became faster.
The sole steady late presentation showed frame 4731 at heard frame 4733 before
a normal 5.49 ms EndDraw crossed to heard frame 4734. Six of the nine omissions
were requested but not delivered; three recovery positions were never requested.
All validated completions were received and no completed packet was overwritten.
The steady queue did not drain and no early or backward pictures were observed.

The same AF337 executable was checked on a disposable two-clip project from the
downloaded 1080p source. Fit populated both thumbnail and processed waveform
strips. A ruler seek to `00:00:29:37` updated Program picture/time and histogram,
RGB parade and luma waveform. Embedded audio showed active stereo meters; Mute
silenced them while time advanced, and Unmute restored them. Playback traversed
the clip boundary and stopped at the authored last frame `00:01:59:58` with
silent output. Source playback independently advanced while Program remained
parked at `00:00:29:37`; Source Stop silenced output, and both Start controls
restored nonblank frame zero. Saving the disposable project after restoring its
state produced the original project hash. Only the owned private windows closed.

The 9676 implementation uses two-frame consecutive decode windows and an ordered
two-packet FIFO. Its fresh combined native build passes 17 queue cases/191 checks,
13 clock cases/81 checks, four retained-producer cases/139 checks and eight
socket/FIFO cases/93 checks. The native trace proves three total owned/reserved
credits, including 9,892 rows with one owned picture and two reservations. No
validated completion was overwritten and the steady audio queue never drained;
no early or backward presentation was observed. Median future ownership was one
picture and the 95th percentile was two. This is actual refill, but not sufficient
reserve for the observed stalls.

All 17 skipped positions were never issued: 82-86, 131-134, 3152-3155 and
10420-10423. Issue-to-GUI receipt reached 74.96 ms; this includes both decode work
in the window and consumer scheduling. The next recovery request jumped ahead
of the actual heard frame. Five presentations exceeded two-frame lateness, with
a five-frame maximum. The complete 179.276-second raw epoch is retained. Manual
Stop occurred before the 50,000-row profile limit; the immutable trace has 49,609
rows and includes Stop and nonblank rewind to frame zero.

The exact 9676 executable also passes a separate disposable 1080p control check.
Fit populated both thumbnail and processed waveform strips; a ruler seek to
29:37 changed Program picture/time and all three scopes. Gain 1.00 to 1.05 and
Pan 0.00 to 0.05 rebuilt audio and resumed stereo playback, including across the
clip boundary; both values were restored. Mute silenced output while time
advanced; Unmute restored meters. A ruler seek during Play paused and silenced
output, then restored the matching 29:37 picture. Source playback advanced with
active stereo while Program remained parked; Source Stop silenced output and
both Start controls restored nonblank frame zero. Saving the restored disposable
project produced its original hash. This run does not include authored EOF.

## Qualified private fixed-eight reserve

The 8892 candidate implements a fixed eight-picture native budget while keeping
producer windows and the transport FIFO capped at two. Before first PCM, it
requires eight actual consecutive owned future pictures, or only the available
pictures in a shorter tail. Reservations and predicted times do not qualify.
Legacy two-slot paths remain unchanged. Native preparation fills available credit
consecutively without the old 50 ms horizon; depleted recovery requests the actual
heard frame. Stop, seeks and content changes retire the window. Due release still
follows actual device samples, with the existing two-second readiness deadline
and completed Program/Source origin identities.

Windows native, Linux native and AIR interpreter fixtures pass 20 queue
cases/303 checks and 17 clock cases/3,326 checks. They follow one- and two-frame
request counts, model 40/54/75 ms completion stalls against actual 48 kHz
rational-frame boundaries, and check seven pictures are insufficient, eight owned
pictures are ready, zero- through seven-frame tails, Source mode, repaired origins,
FIFO order and independent retirement paths. A finite reserve cannot guarantee
against longer pauses or decoding persistently slower than the media rate.

The first 8892 attempt, `cadence-reserve-4k-f628eba6cd754cf9ba7ccec51bd94f9f`,
reached the fixed 50,000-row profile cap before recording its terminal Stop
boundary. Native Stop at `3:47:34`, silent output and nonblank Start at frame zero
were observed, but the unchanged analyzer correctly refused timing qualification.
Its `incomplete.json` and immutable trace remain retained; this attempt is neither
a cadence pass nor a measured cadence failure. It proved bounded eight-credit
ownership and zero overwrites only. Diagnostic reserve starvation in its initial
slow-presentation segment does not establish a causal effect from single-frame
refills; later reserve ownership recovered despite those refills.

The same frozen application and worker then passed the unchanged cadence analyzer
in `cadence-reserve-4k-fa92a46f94c949a08ac599a1d71fa5de`. Its 41,446-row immutable
trace includes a complete 120.095-second raw epoch and observed manual Stop. The
steady body contains 7,093 distinct pictures at **59.939828 pictures/s**, with zero
skipped positions, repeated pictures, early or backward presentations, pictures
more than two frames late, and audio queue drains. Prepared future ownership has
median six and 95th percentile seven. Median picture spacing is 16.680 ms; its
maximum is 21.677 ms. Native EndDraw median is 5.589 ms and maximum 10.624 ms.
These are observations from this private run, not a paired causal comparison.

The complete raw epoch remains available: 7,184 presentations, one repeated
startup picture and one observed empty audio queue, with zero skipped positions,
early or backward pictures, or pictures more than two frames late. The raw maximum
picture gap is 218.067 ms; steady selection excludes the first 1.0 seconds of device
samples and the final 0.5 seconds before manual Stop. Retaining these startup
observations prevents the steady result from being mistaken for a whole-run
zero-repeat or zero-drain claim.

The separate credit gate passed: maximum eight total owned/reserved pictures,
maximum two reservations, zero completed-packet overwrites, and 4,076 rows with
six owned pictures plus two reservations. There were 4,257 single-member and
1,468 two-member windows. Actual eight-picture preroll was also observed before
first PCM in the incomplete earlier attempt. Pair-only refill hysteresis was not
implemented for either run.

Exact qualified-run identities:

- Application: `889247c224a69355d9dcaa6ce7e3209c32801c11971cda6e1e84f3db2c7ba595`.
- Worker: `aa40b96c631c82cfc834d027678e95a00bd8d5f61db54f15e7c7ecefcf74228c`.
- Immutable profile: `93cde6a8af74379067f5d54698695f9d3476a3a4633ea200422e771737c3c5ae`.
- Analyzer: `037d1a8af2c1eaabf37cc7472cafd99e76f9311abb81689b45d4b3c87870c25b`.

The qualified result applies to ordinary maximized Windows playback of this
single AV1/PQ 59.94-fps source, with fitted 480x270 monitors. Manual Stop does not
prove authored EOF or full-duration playback. Presented positions are application
metadata rather than independently decoded pixels for every measured frame.
Compound 4K60, fullscreen 4K and physical speaker/photon synchronization remain
outside this result. This qualified private run does not claim publication or
complete professional editing acceptance. The recovery audit below records why
the subsequent coherent build was withheld and which final gates remain pending.

## Recovery audit and private cancellation proofs

The first coherent fixed-eight application, `9FD4`, completed its native build
with exit zero. That build remains retained, but was not accepted as a fully
tested, natively measured or published checkpoint: a follow-up lifecycle audit
found later-PCM ownership and modal preview-retirement gaps. Its build success
and the earlier `8892` cadence result do not qualify the revised application.

The revised main source (`b918286aafc4d59479217f0cf412488be5b81fbf8a3b7a661285360e1b58875b`)
retires the audio producer's request before releasing the window's session-owned
chunk on Stop, error and modal entry. This also removes a later chunk that has
finished before its GUI receipt, after first-PCM waiting flags have ended. On
shutdown, the producer is stopped and joined before the chunk is released.
Only that owned output path is removed. The first-PCM release helper retains its
separate idempotent behavior so a repeated release cannot delete a replacement
it no longer owns. Failed audio retirement reports `GA_AUDIO_RETIRE`; failed
modal generation or marker retirement reports `GA_MODAL_RETIRE`. A picker Cancel
leaves playback paused rather than resuming retired work.

Focused clock checks in `cadence-reserve-modal-clock` pass **18 cases/3,329 checks**
on Windows native and Linux native. They include later-output cleanup after
first-PCM ownership has ended. This is distinct from the earlier **17 cases/3,326
checks** passed on Windows, Linux and the AIR interpreter; no interpreter result
is claimed for the added modal-clock case.

The actual background audio task passes three new ownership scenarios with
**2,400,000 exact quantized PCM sample comparisons**. A normal later chunk finishes
without polling its GUI receipt; a superseding discard marker and output release
then remove it, and the discard acknowledgement confirms cleanup before reuse.
A fresh request reuses the same path and matches every expected source sample.
An unrelated output sentinel remains intact. Two controlled wrapper scenarios
block a real worker pipe during reply and write, then prove discard acknowledgement,
old-child exit, correct fresh same-path PCM, final cleanup and Stop/join within
2.5 seconds. The independent oracle models the authored PCM16 source's ordinary
float normalization and final 32767-scale rounding exactly, with no sample tolerance.

The expanded existing audio harness exits zero with all 33 continuous editor
cases, the six prior cancellation paths and these two new blocked ownership
forms. Receipts and initial oracle-development failures are retained under
`agent-editing-pcm-owner`; the first draft's incorrect assumption that source
PCM16 bytes survive output quantization was corrected explicitly. These checks
use no window or output device and do not establish physical sound or cadence.

Preview modal retirement now publishes a cancellation-only request ID, clears the
retired transport window and forces a fresh snapshot on the next real request.
This includes independent Source playback; the old snapshot must not remain
eligible merely because content and the parked Program position are unchanged.
A failed marker write preserves owned transport state. A narrowly scoped producer
guard ignores a blocked-send error only after that specific window's marker has
been superseded; current-window errors still propagate.

The final private retained-producer fixture passes **six cases/186 checks**. A
negative version that omits the Source fresh-snapshot reset correctly fails that
case: **five of six cases pass, 179 checks**. A separate diagnostic deliberately
holds the request marker unavailable for 100 ms. Without the retired-send guard,
the blocked old window `8/9` emits producer error `9` while the current window is
retired (`0`), then `GA_PREVIEW_REQUEST` closes the original producer. With the
guard, the same diagnostic recovers exact requests `10/11` in the existing owner.
This proves the forced diagnostic's cancellation behavior, not the cause of an
earlier intermittent panic/channel close in the first final fixture executable.
That earlier failure remains unclassified; three repeats of that exact binary
passed and are retained separately.

The following coherent build and suite attempt uses the `cadence-reserve-modal`
prefix. The focused private proofs above do not substitute for complete Windows,
native controls/recovery, cadence or publication gates, and do not extend the
qualified `8892` scope.

## Coherent modal build and profile-fixture correction

The `cadence-reserve-modal` build completed with exit zero and application hash
`d44c4cfcc5d42b7a1c33c0bbcdc75f9c18ffab9feb53298d2a32af5502a01afa`.
Its full Windows suite attempt then exited **one** at `genesis-window-cache.exe`.
The fixture still expected 39 profile columns, while the production writer
intentionally appends seven decode-window/owned-credit/reserved-credit descriptors
for 46 columns. Its old expectation that column 38 ended the row was also stale;
the final newline now belongs at column 45. The failed cache fixture reported
seven passing cases, one failed case and 2,517 checks. The failure log, frozen
source manifest and build receipt remain immutable.

Before that failure, the suite completed audio and nested-audio checks, including
the 130-case report with zero sample failures. Export cancellation passed at open,
frame, audio, close and exit, with worker exit/partial cleanup and independently
verified audible six-frame same-path retries. These are retained component
results. The suite stopped before the remaining headless and control gates, so
neither the build nor these earlier passes establish final Windows acceptance.

The correction changes only `tests/window_cache.ai`, whose frozen hash is
`45664f19009227d51df430f9d0e1751168d2011316d0ce6e1fe08b7e60fdcd07`.
It preserves the original profile field-order checks, requires exactly 46 columns,
and independently assigns seven nonzero or signed sentinels to check columns
39 through 45 individually. Three additional checks cover default poll-only
window IDs, unavailable frame sentinels and zero credits. The corrected fixture
passed eight cases/2,527 checks on Linux native using the bootstrap executable
produced by the new coherent build; the Windows result subsequently passed in
the complete suite recorded below. These model results alone do not qualify
native playback.

The subsequent coherent build uses the `cadence-reserve-profile` prefix, with a
new frozen manifest reflecting only that fixture change and no production change.
Its results follow. The failed modal-suite evidence and the qualified private
`8892` timing result retain their separate identities and scopes.

## BDF3 full suite and qualified cadence; live Gain failure withheld

The `cadence-reserve-profile` coherent build completed with exit zero. The exact
application is `bdf3b73e6b4f28d7dd964a8b0293e6e8850ab9a8ce58c12f899f7ea717fe248a`,
with unchanged worker `aa40b96c631c82cfc834d027678e95a00bd8d5f61db54f15e7c7ecefcf74228c`.
The complete Windows suite also exited zero, including the corrected cache fixture's
eight cases/2,527 checks, 757 control-click outcomes across four tabs and the
unchanged 153 saved application facts plus three native-drop checks. This
full-suite result remains valid evidence for that exact build, separately from
the subsequent native editing failure.

The same executable passed the unchanged native cadence analyzer in
`cadence-reserve-profile-4k-24af528ed73e458ab439336e6710dd59`. Its 38,204-row
immutable profile records a complete **133.122106-second** raw epoch with manual
Stop. The steady body contains **7,877 distinct pictures at 59.93931453384678
pictures/s**, with zero repeated pictures, skipped positions, jumps greater than
one frame, early or backward presentations, presentations more than two frames
late, audio queue drains or completed-packet overwrites. Picture-spacing
median/95th percentile/maximum are **16.68235/17.4098/23.6442 ms**. Prepared future
ownership has median six, 95th percentile seven and steady maximum seven.

The credit gate separately passes with maximum eight total owned/reserved
pictures and two reservations. It records 6,048 windows: 4,119 single-member and
1,929 two-member windows. Steady cadence excludes the first 1.0 seconds of device
samples and the final 0.5 seconds before manual Stop, using the same analyzer and
selection policy as the earlier runs. The full raw epoch retains 7,969
presentations, 7,967 distinct pictures, two repeated startup presentations, two
observed drained-queue presentations and a **168.0563 ms** maximum picture gap.
Its raw skipped-position, early, backward and more-than-two-frame-late counts
are zero. The steady pass must not be described as whole-run zero repetition or
zero queue drain.

Active stereo meters were observed at `00:00:58:08` and `00:02:07:13`. Manual
Stop at `00:02:12:46` silenced output, and Start restored a nonblank frame zero.
The owned 4K test window closed. This remains ordinary maximized playback with
fitted 480x270 monitors; it does not prove authored EOF, full-duration playback,
compound 4K60, fullscreen 4K, independent pixels for each measured presentation
or physical speaker/photon synchronization.

The required disposable 1080p editing check then failed in
`cadence-reserve-profile-editing-3faba8c1399a4eccb599af7affd68e08`. Before the
failure, Fit populated two mapped filmstrips and waveforms; a ruler seek to
`00:00:29:37` updated Program picture/time, histogram, RGB parade and luma waveform;
and Play showed active stereo at `00:00:36:39`. Clicking track Gain plus at
`00:00:43:40` changed **1.00 to 1.05**, but playback then paused at
`00:00:43:41` with **`[GA_PREVIEW_REQUEST] Cannot publish the preview window`**.
The original project remained unchanged and the disposable project was not saved.

`cadence-reserve-profile-ui-failure.json` and its immutable `window-failure.tsv`
retain this failed native acceptance result. The producer issue's cause is
unknown; no fix or causal diagnosis is claimed. The successful Fit, scopes and
initial Play observations do not qualify modal recovery, live-edit recovery,
Pan, Mute, Save or the remaining intended UI checks. BDF3 is withheld from
publication despite its full-suite and separate cadence passes. A later corrected
candidate still requires a coherent full suite, final native editing/recovery,
cadence and publication gates.

## Gain failure sequence and pending recovery candidate

The retained BDF3 profile and diagnostic events now establish a narrower failure
sequence in `cadence-reserve-profile-diagnosis.json`. The new Gain request
**848-849** was accepted with snapshot **848**, document revision **2** and audio
origin **2621**. Completed-packet count remained fixed at **846**. The first
paused row followed **0.4233891 seconds** later. Diagnostic events record
`[GA_PREVIEW_CHANNEL] Preview task ended unexpectedly` before the subsequent
generic `[GA_PREVIEW_REQUEST] Cannot publish the preview window` retry message.
Thus the Gain request was accepted before the producer closed, and the retry
message obscured the earlier closure. The initiating exit reason is still
unknown. A proposed 50 ms write-timeout/channel-poison explanation remains an
unproved hypothesis; this evidence does not attribute the failure to it.

The new shared recovery code preserves a terminal producer error durably with
its request and snapshot identity outside the event channel. Only a closed
producer can promote that correctly scoped terminal cause across a retired
document epoch; ordinary cancellation does not become a permanent failure.
A closed lane without error text has an explicit coded fallback. The main loop
latches failure independently of status-message deduplication, restores the
error if input replaces the status, and pauses both transports before audio
start/queue processing when a closed or connection-wide error is present.
Request-specific errors continue to require current queue eligibility rather
than reviving a retired failure on a generic publication retry.

Mix restart also stops the old device epoch and publishes a superseding audio
request before releasing its session-owned chunk and waking the producer. That
cleanup covers later PCM after first-PCM flags have cleared, and occurs before
reusing the output path. It retains the existing serial-producer cancellation
checks; no transport deadline or SDK behavior was changed for this diagnostic.

The focused native CPU persistent-producer fixture in
`agent-gain-producer-diagnostic/receipt.json` and
`agent-gain-producer-diagnostic/check-1/preview-batch-tests.json` passes **eight
cases/228 checks**. This includes an actual shared track-Gain command during an
incomplete playing packet, followed by retirement/recovery, plus scoped terminal
diagnostic ownership checks. The original live GUI failure has **not** been
reproduced by this regression. The focused pass proves the tested recovery
contract, not the unknown initiating cause or final native Gain usability.

At that diagnostic stage the next coherent candidate used the `cadence-reserve-gain`
prefix and its complete Windows suite, exact-current 4K cadence and publication
were pending. The completed checkpoint follows. BDF3's full-suite/cadence successes
and failed native Gain check remain retained unchanged.

## Fresh 1A49 native editing and modal recovery proof

`cadence-reserve-gain-ui.json` records a passing owned native 1080p editing run
with application `1a49b8af32b9a9169dfcdebb78d4f523bf742c4c34a006f90551c2b8251eb4b6`
and unchanged AA40 worker. Its run is
`cadence-reserve-gain-editing-4e9b03d5a01a48ff9a1e761f955c9f8f`; the immutable
32,227-row profile hash is
`bde523325b1b0f5aaaec7110d00494a7c95fffa5928872a7c5e5ec5e003f5eaa`.
This is evidence for the fresh binary's observed editing behavior, not a causal
explanation of BDF3's earlier producer exit.

Fit populated both clips with **24 mapped thumbnail rows** and processed waveform
strips containing **1,199 and 1,200 points**. A paused seek to `00:00:29:37` updated
Program picture/time, histogram, RGB parade and luma waveform. Program Play
showed active stereo output meters at `00:00:42:57`. Live Gain changed 1.00 to
1.05 and back to 1.00, with stereo playback resuming after each edit. Pan changed
0.00 to 0.05 and back to 0.00 with active output. Mute silenced output while
picture/time advanced; Unmute restored it. Natural EOF paused at `00:01:59:58`,
retaining a nonblank last image and zero meters.

Source playback independently advanced with stereo output while Program stayed
parked at `00:00:29:37`. Source Stop silenced output, and Source Start restored a
nonblank frame zero. Native Open was invoked while playing at `00:00:44:48` and
held longer than two seconds. Escape returned to paused `00:00:44:49`; subsequent
Play reached `00:00:58:11` with active stereo in the same healthy producer owner.
A ruler seek during Play returned to paused `00:00:29:37` with a fresh completed
picture.

Locked Lift and Ripple both returned `GA_EDIT_LOCKED`, preserving two clips and
7,199 frames. Split produced three clips; Undo, Redo and another Undo restored
the expected 2/3/2 clip counts without changing duration. The disposable project
was saved and reopened through the native picker, preserving authored content.
After reopening, Play showed active green stereo at `00:00:06:20`; Stop at
`00:00:12:21` silenced output and retained a nonblank picture. Both Start controls
restored nonblank frame zero, with Fit strips and Scopes available. The original
project remained unchanged.

The receipt records zero unexpected errors and zero durable producer failures;
its one distinct expected editor diagnostic is the locked-edit refusal. It does
not claim physical speaker or display timing. The original Gain failure's
initiating cause remains unproved; this run verifies the new candidate's tested
recovery behavior. The completed `cadence-reserve-gain` Windows suite and separate
exact-binary cadence/export/publication proofs follow. The earlier BDF3 cadence
pass does not qualify this changed binary.

## Final 1A49 suite, cadence and native export acceptance

The coherent `cadence-reserve-gain` build and complete Windows gate exit zero.
Application SHA-256 is
`1A49B8AF32B9A9169DFCDEBB78D4F523BF742C4C34A006F90551C2B8251EB4B6`;
the unchanged worker is
`AA40B96C631C82CFC834D027678E95A00BD8D5F61DB54F15E7C7ECEFCF74228C`.
`cadence-reserve-gain-windows.log` records the existing media/audio/export gates,
757 control outcomes, 153 saved facts plus three native-drop checks, persistent
producer eight cases/228 checks, FIFO eight/93, clock 18/3,329, editing safety
seven/29 and the corrected profile cache eight/2,527. The previously failed
39-versus-46-column fixture receipt remains historical evidence; it was not
reclassified as a production pass.

The exact-binary native run is
`cadence-reserve-gain-4k-26e2f631424046ddb7d5defae801c431`. Its analysis and credit
checks pass. The 36,826-row immutable profile SHA-256 is
`6b6b3b0fe6d9274dfe92dabd2719fb10e22176e0fea86570dd3d553ae7aa1783`, with zero
incomplete rows. Launch metadata SHA-256 is
`60986d2107437b74926803fed779f521d4872d75b6488655d93862d4caacea70`.
The whole first playback epoch lasts **133.8901633 seconds**, with **8,015
presentations/8,013 distinct positions**, two frame-zero repeats, two startup
queue-drain observations and a **171.3431 ms** maximum raw gap. These raw
observations remain in the evidence.

The unchanged fixed first **1.0 device seconds** and final **0.5 seconds before
observed manual Stop** exclusions retain **132.1706172 seconds**, **7,923 changed
pictures** at **59.93767879598/s**. There are zero steady repeats, skipped positions,
jumps above one frame, backward/early pictures, presentations beyond two heard
frames, queue drains or completed-packet overwrites. Gap median/p95/maximum are
**16.67895/17.4692/24.1018 ms**. The maximum observed after-presentation lateness is
one heard frame. Prepared futures have median six/p95 seven. The credit receipt
records 6,146 issued windows (4,272 count-one/1,874 count-two), maximum owned eight,
reserved two and combined eight; 3,767 rows have six owned plus two reserved.
Readiness requires actual consecutive owned pictures before first PCM, not merely
eight requests. Producer windows and completed-packet FIFO remain bounded at two.
No analyzer threshold, exclusion or clock gate was weakened.

Native Stop at `00:02:13:32` silenced output while retaining a nonblank picture;
Start restored nonblank frame zero, and the owned test window closed. This remains
ordinary maximized editor playback with fitted 480x270 monitors and live stereo
from the supplied AV1/PQ 59.94-fps source. It proves neither authored EOF/full
five-minute playback, compound 4K60, fullscreen 4K, independent pixels for each
measured presentation nor physical speaker/photon synchronization. A fixed
eight-picture reserve does not guarantee arbitrary stalls or sustained decoding
slower than playback.

`cadence-reserve-gain-export.json` passes the separate native export workflow on
a disposable **1,032-clip/8,192-key** authored graph. A **240-frame** export is
cancelled at observed **29%** progress: encoder PID 42856 exits while preview PID
8356 remains alive, and no final, owned partial or signal remains. The native
**12-frame** retry completes. Independent decoded video checks title, grade and
background; decoded AAC has exactly **9,600 frames**, no padding, and
zero-sample-shift correlation **0.9999758635037325** against the independently
processed audio reference. Native Save/Reopen preserves the authored JSON graph,
including the edited title, with both monitors nonblank. The source project is
unchanged. This is bounded cancellation/retry and output correctness, not a full
large-project export-throughput qualification.

The final `cadence-reserve-gain-gate.json` passes. Earlier failed timing runs,
8892's capped incomplete attempt and private retry, D44C's stale fixture failure,
BDF3's separate cadence success/native Gain failure, and its unknown initiating
producer-exit cause remain retained. Focused and fresh native recovery passes do
not establish the cause of that earlier exit.

## Installed root and ready state

`cadence-reserve-gain-publication.json` records successful root publication of
the exact 1A49 application and AA40 worker. The shared MM-AIR manifest, SDK/worker
pins and original assets remain unchanged; Genesis adds no separate FFmpeg
executable or codec DLL bundle. Previously loaded application/native-audio images
were preserved in the workspace backup. No user process was terminated.

`cadence-reserve-gain-root-ready.json` binds the fresh installed-root run
`cadence-reserve-gain-root-4ab076f8cfcc4511b4bc07e6b5bcdc11`, PID 40700/native window
6556960. It opens the original **76,701-frame** Regular project unchanged, with
both monitors nonblank and paused at frame zero. Whole-project Fit has **23 mapped
bitmaps** and **25,567 processed peak cells**, with populated histogram, RGB parade
and luma scopes. Three immutable readiness snapshots and the launch hash are
bound by the receipt. The native window is left open for the user; there is no
shell window.

Sanitized evidence is preserved in
`archive/native-playback-reserve-2026-10-10.tar.gz`; its digest is recorded in the
archive receipt and publication commit. This checkpoint qualifies the
specific editing, recovery, export and bounded native cadence contracts above;
it does not mark the complete professional editing goal achieved.

## Linked-lane background follow-up

The preceding installed 1A49/native-window sections are historical acceptance
for their exact binary. The following slice is background-only; it does not
repeat desktop clipboard, live audio, hardware-clock or sustained cadence tests.

Shared source-aware imports produce V-only/A-only linked clips, V bitmaps and A
processed peaks, with one audio contribution. Properties reads and edits A while
V is selected; Group includes and preserves existing mates. Paired edit success
has one Undo/Redo transaction, and unsupported or locked edits preserve the
complete graph/history. Native migration leaves the original file unchanged
until Save; unsafe conversion opens the original graph with a warning.

The focused Windows CPU linked fixture passes 28 cases / 784 checks, including
actual generated controls and pointer dispatch. It is separate from independent
picture/PCM decoding and from a real native window. The earlier locked-Slip failure remains retained; Properties/Group checks cover
the two reported integration defects without changing expected outcomes.

Contributing clip Pan/Speed curves and curves on enabled audio-filter instances
report `GA_AUDIO_AUTOMATION_UNSUPPORTED`; this is explicit refusal, not animated
DSP support. Audible offline leaves, including compound descendants and original
Source audition, report `GA_AUDIO_SOURCE_OFFLINE`. Supported clip Gain/Fade curves
retain their existing processing. Disabled clips, muted or sequence-local
solo-excluded lanes, inactive/unreferenced sequences, no-audio or video-only
branches, and half-open nonoverlap remain noncontributing. Static held clips are
silent, but an enabled stored Speed curve still refuses: it could make a held
clip progress. Disabled filter curves stay dormant. Hidden/locked tracks remain
audible; scalar zero gain is not a bypass for positive Gain keys. Compound
preflight includes the selected child history needed by cached DSP. Direct peak
failures retain `GA_AUDIO_CLIP_ENV` and the underlying cause.

The focused 61-case background oracle compares 1,536,000 PCM16 values (maximum
0.735521 code at the unchanged one-code limit) and 384,000 independently decoded
lossless-master values (maximum normalized error 1.207935e-7 at the unchanged
2e-6 limit). Masked picture branches, source audition, refusal recovery, owned
cache/partial cleanup and preservation of external sidecars are included. The
prechange silent-loss failure and later fixture-authoring corrections remain
retained. These are focused receipts, not native-device or desktop acceptance.

Audio-plan failure stops the device before the next paint; export rejects the
plan before acquiring output/cleanup ownership. No codec, DSP, color or worker
change is introduced, and Genesis continues to use MM-AIR's runtime without its
own FFmpeg executable/DLL bundle.

The first coherent `linked-lanes-controls-final` build succeeded, but its
BackgroundOnly gate failed the timeline-track-scroll fixture (eight cases / 81
checks). That fixture used an unsupported opacity edit which historically added
an unchanged Undo snapshot. The new atomic refusal correctly preserves history,
so the fixture's assumed Undo step was invalid. The correction uses supported
Gain 0.5, verifies the actual edit and Undo restoration before testing wheel
scrolling; the corrected final count is eight cases / 83 checks. Production was unchanged,
and the original failed build/gate evidence remains retained. The fresh
`linked-lanes-controls-retry` build proceeded; this fixture
correction is not a relaxed media, control or atomicity threshold.

The `linked-lanes-controls-retry` gate then exposed a real preview transport
failure: the retained-producer fixture reported six passed, one failed and one
skipped case / 214 checks. The same binary passed isolated execution and repeat
one (eight cases / 228 checks), then failed repeat two. Its first terminal record
is request 2 / snapshot 1, `[GA_PREVIEW_CHANNEL] channel deadline expired`, on the
old packet before the Gain replacement. Link closure is therefore reproduced,
not inferred from a generic UI message. These failures and passing retries are
retained; a retry pass does not erase the failure.

The shared channel used one 50 ms credit-poll/write budget, so backpressure could
leave a frame write with an expired deadline and permanently poison Sender.
The frozen `patches/air-channel-deadlines.patch` adds reusable
`std.channel.send_deadlines` with separate credit-poll and frame-write deadlines.
Preview still polls credit in short steps and bounds each current window message
to two seconds. Cancellation occurs between complete messages: a partially
written frame is fatal and must never be reset into a different frame.

Focused real-TCP proof passes four cases / 18 checks plus four independent exact
wire oracles. A controlled 200 ms started-write stall succeeds with the separate
long write deadline and delivers exact payload/completion; the old or short
write deadline fails after 4,079 payload bytes and cannot emit another frame.
No-credit expiry remains resumable, preserving credits and sequence until the
same logical frame is retried. Legacy send semantics are unchanged. These are
protocol component proofs; the coherent application gate is recorded below.

The `linked-lanes-transport-final` build was retained for the next gate. This
evidence does not establish the initiating cause of the earlier BDF3 native-Gain failure, which remains
unknown.

The `linked-lanes-transport-final` BackgroundOnly run passed the media, audio and
native fixtures, including the 61-case audio-plan gate, then failed the last
headless facts contract: successful Nudge returned `moved` where the existing
expected result was `nudged`. The sole follow-up production correction restores
Nudge's success message/value; refusals and the atomic paired Move remain
unchanged. The failed source snapshot, gate log and reports remain retained.
No other enforced headless-fact mismatch was found.

A separate controls-tail run passes 757 reported clicks and all four dock-tab
overlap checks, plus real Windows Unicode preview and coded errors. That partial
validation did not replace a complete coherent gate. The final contract build
and its independent `agent-linked-streams-contract-final` helper subsequently
passed the accepted background gate below.

The coherent `linked-lanes-contract-final` build and complete
`tests/windows.ps1 -BackgroundOnly` gate pass, and the verified payload is
published in the Genesis root. Application SHA256 is `06af1ab848cf1225c3bbb7f9896dd6dbdfa3148df95b8ed9f5241c9b20ca687b`;
the unchanged worker is `aa40b96c631c82cfc834d027678e95a00bd8d5f61db54f15e7c7ecefcf74228c`. Protected original projects/media are
unchanged; no user application was terminated and no desktop/device test was
performed. MM-AIR runtime reuse and the absence of a separate Genesis FFmpeg
bundle are retained.

The final background gate includes linked controls 28 cases / 784 checks,
channel deadlines four cases / 18 checks plus four exact wire oracles, retained
preview eight / 229, track scrolling eight / 83, 153 headless facts plus three
native-drop checks, and 757 control outcomes across all four dock tabs. The
61-case audio-plan oracle retains the numerical limits above. A 181-second
continuity check passes 37 chunks / 36 boundaries with exact samples.

The separate real-1080p helper passes three cases / 22 checks against the frozen
shared source. Its background raster snapshots at frames 0, 90 and 179 show
V-only filmstrip tiles, A processed waveform extent, Program/scopes updates and
`00:00:00:00`, `00:00:01:30`, `00:00:02:59`. Source is intentionally inactive in
that fixture. The driver's initial SDK relative-path error was repaired before
client launch; the candidate did not change and the failed setup is retained.
These are inspected helper surfaces, not a live desktop or device test.

Desktop clipboard, live audio, hardware-clock behavior and sustained cadence
remain deferred for this build. Earlier 1A49 cadence evidence cannot qualify
06AF; complete professional editing acceptance remains false. All earlier
failed gates, retries and fixture corrections remain retained.

The [immutable 1,287-member evidence bundle](../archive/linked-media-windows-2026-10-10.tar.gz)
has SHA256 `b822ed35284be3961abead18381aed7f23bb55aaafae2701d28c33d73ecd87bb`. The
[acceptance receipt](validation/linked-media-windows-2026-10-10.json) binds exact
source, build, reports, published payload and archive digests.
