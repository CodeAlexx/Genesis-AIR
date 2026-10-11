# Linked video and audio lanes on Windows

Source-aware Add clip, Append, Insert and Overwrite place pictures on a V lane
and sound on an A lane. Video with sound creates two linked clips sharing one
source-time mapping; the V-only half cannot contribute duplicate sound.
Audio-only sources use A lanes and video-only sources use V lanes. New imports
respect the chosen A lane's mixer. V lanes display frame thumbnails and A lanes
display processed stereo waveforms, including compound audio; legacy combined
V clips remain audible but do not display a waveform over their pictures.

Selecting a linked V clip exposes its A mate in both Audio and the audio portion
of Properties. Gain, EQ and dynamics controls read and edit that mate while V
remains selected; video geometry, grade and rate controls retain the V target.
Pure-video clips have no audio subsection. Recognized disabled/offline audio
still exposes controls so it can be restored.

Paired moves/nudges, head/tail and ripple trims, Split/Razor, Slip, Lift/Delete,
Roll/Slide and Copy/Cut/Paste preserve linked source time with one undo snapshot.
Static Rate and Reverse change both halves. Group includes existing mates and
retains unique pair discovery; explicit Ungroup intentionally unlinks. Locked,
ambiguous, incompatible-neighbour or cross-lane range edits refuse atomically
rather than shifting only one stream. Independent linked Speed filter/key edits
report `GA_LINKED_SPEED`; unsupported multi-lane range edits report
`GA_LINKED_RANGE`. Clipboard content includes ordered filters, scoped keys and
both streams. Resource retirement and Open/New clear unsafe clipboard identity;
cross-FPS paste remains an explicit refusal.

Native Open separates safely convertible legacy embedded audio in memory,
leaving the original file untouched. Converted documents are dirty until Save
persists the layout. Migration preserves old mixer intent and occupied A clips,
using a compatible free lane or creating a matching lane. When authored groups,
locks or unknown context prevent safe conversion, Open keeps the original graph
and reports why. Headless readers retain the authored graph without migration.

The shared SDK persists `Clip.streams`: 1 video, 2 audio, 3 legacy both. Missing
values decode as 3 and the encoder omits that default. The pinned SDK uses
`patches/air-editor.patch` and `patches/air-editor-io.patch`; one shared AIR source
runs through the native Windows adapters.

## Loaded audio and background validation

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

The focused linked-command/control fixture passes 28 cases / 784 checks. It
exercises actual shared Properties control generation and pointer dispatch,
paired geometry, Group, complete Undo/Redo, atomic refusal ledgers, routed audio
FX, Copy/Cut/Paste and migration Save/Open. This is native CPU evidence without
a desktop window. Pixel/cache and independent processed PCM/picture gates are
separate from this model fixture.

The shared preview channel also has a focused backpressure repair: separate
credit-poll/frame-write deadlines preserve reliable framing within a bounded
two-second window-message budget. Four real-TCP cases / 18 checks and four exact
wire oracles pass, including a 200 ms write stall, resumable no-credit expiry and
fatal partial-frame refusal. The earlier BDF3 initiating cause remains unknown;
these component checks do not qualify the changed application. See the
[retained failure and protocol proof](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md#linked-lane-background-follow-up).

The transport candidate passed media/audio fixtures but failed the existing
Nudge success-message contract. The fresh contract candidate restores `nudged`;
paired edit/refusal behavior is unchanged. A separate 757-control/four-tab tail
passes; the coherent final result is recorded below.

The final `linked-lanes-contract-final` build and full BackgroundOnly Windows
gate pass; the verified application `06af1ab848cf1225c3bbb7f9896dd6dbdfa3148df95b8ed9f5241c9b20ca687b` is published with unchanged AA40
worker/runtime. Acceptance includes linked controls 28/784, channel 4/18 plus
four exact TCP wire oracles, retained preview 8/229, track scrolling 8/83,
153 headless facts plus three native-drop checks, 757 four-tab control outcomes,
the 61-case PCM/master preflight and exact 181-second / 37-chunk continuity.

A separate three-case / 22-check real-1080p shared-source helper renders V-only
tiles/A peaks and changing Program/scopes at frames 0, 90 and 179. Inspected
background surfaces are not desktop or speaker tests. The initial SDK driver
path error was repaired before launch without changing the candidate, and all
failed gate/fixture/transport evidence remains retained. See the
[complete validation scope](WINDOWS_PLAYBACK_VALIDATION_2026-10-10.md#linked-lane-background-follow-up).

Publication preserves protected originals and terminates no user application.
Desktop clipboard, live audio/device clocks and sustained cadence remain
deferred; older 1A49 timing cannot qualify this binary. Complete professional
editing acceptance remains open. The
[1,287-member immutable bundle](../archive/linked-media-windows-2026-10-10.tar.gz)
has SHA256 `b822ed35284be3961abead18381aed7f23bb55aaafae2701d28c33d73ecd87bb`; the
[receipt](validation/linked-media-windows-2026-10-10.json) binds its exact scope.
