# AIR gaps found by Genesis AIR

Genesis AIR uses AIR; it does not modify it casually. When building this application ran into
something AIR could not express, the gap was recorded here first — with the smallest fix, the
file it belonged in, and a reproducer — and the application worked around it in a way that
stayed visible to the person using it, rather than pretending the feature existed.

The AIR gaps below are closed in the compatible AIR main SDK recorded by
`air-sdk.conf`. This file records the original issues and their language-level fixes;
renderer integration status lives in the main README.

---

## 1. `std.editor` could not write a clip's speed or reverse flag — CLOSED

**What was missing.** `editor.Clip` carried `speed: f64` and `reverse: bool`, `editor_io`
round-tripped both, and `editor.clip()` read them — but there was no setter. `set_clip_gain`,
`set_clip_enabled`, `set_fade_in` and `set_fade_out` all existed; speed and reverse had no
equivalent.

**Why it mattered.** The inspector's SPEED section could display a clip's rate and reverse
flag and could not change them. Modelling speed as a filter parameter instead was rejected:
`Clip.speed` already existed, and a second store for the same fact is exactly the
disagreement this codebase is built to avoid.

**Fixed by** `set_clip_speed` and `set_clip_reverse` in `stdlib/editor.ai`, beside
`set_clip_gain`. A negative rate is **refused** rather than clamped. Zero is accepted as a
held frame, matching `freeze_frame`; `reverse` remains the separate direction flag.

**Covered by** `stdlib_editor`, which checks rejected negative rates and accepted zero as
well as the writes — including that a refused write leaves the previous rate alone — against its independent Python oracle,
native and reference agreeing.

**In this application** the SPEED section is a rate slider and a reverse switch, like any
other parameter.

---

## 2. `std.editor` could not reorder tracks — CLOSED

**What was missing.** `add_track` appended with the next `order` and `remove_track` deleted;
nothing moved a track to a different lane. `editor_view.lanes` sorts by `Track.order`, so
lane position was entirely determined by creation order.

**Why it mattered.** The conventional layout is video above audio. Because the topmost lane
is the highest `order`, Genesis AIR had to CREATE its default tracks bottom-up to get
V2/V1/A1/A2 top-down — and a track added later with the `+A` button landed at the top of the
stack, above the video, with nothing able to move it down.

**Fixed by** `reorder_track` in `stdlib/editor.ai`, mirroring `reorder_filter`, which already
did exactly this for filter stacks. It renumbers the rest to keep a sequence's orders a dense
`0..n-1` run and clamps a position past the end to the last lane.

**Covered by** `stdlib_editor`: moving the last of four lanes to the front leaves 0..3 with
no hole and no duplicate, a position past the end clamps, and an unknown track is refused.

**In this application** `+A` places the new track below the video, and `+V` above it.

---

## 3. `std.vector_font` was not legible — CLOSED

**What was wrong.** Three things at once, and the first is the one that mattered most:

- **The glyphs were a third of their own advance.** The forms were drawn between x=1 and x=3
  on a 5×7 grid whose pen advanced 7 units. Text set in it read as thin marks separated by
  wide gaps, and at small sizes `a`, `e` and `o` were indistinguishable from `s`.
- **The pen advanced by `advance() + 2`.** The side bearings are part of the outlines, so
  those two units were counted twice, setting the text nearly half again as loose as it
  should have been.
- **The table covered only letters, digits, `+`, `-` and `.`.** Anything else drew as an
  empty box: a timecode lost its colons, a percentage its sign, a path its separators. A
  label made only of unsupported characters — the transport buttons were first labelled
  `|<` `<` `>` `>|` — came out blank.

Dots were a two-point segment 0.2 units long: a fifth of a pixel at ten-pixel type, which the
stroker rounds away, so `0.85` printed as `0 85`.

**Fixed by** redrawing the whole table in `stdlib/vector_font.ai`. All 95 printable ASCII
glyphs are present, drawn between x=0.6 and x=4.4 — nearly the full cell — with letterforms
chosen so the bowls stay open when the stroker fills them; the pen advances by `advance()`;
and a dot is a small closed square that carries area at every size the font is legible at.
`height()` and `advance()` are unchanged, so nothing that measures through
`text_vector_width` moved except in the direction of having more room than it asked for.

**Covered by** `stdlib_graphics_xml_extra`, whose pinned glyph counts and coordinates now
read from `std.vector_font`'s own table and stated metrics rather than from a frozen donor
table.

**What it still costs.** It is a 5×7 stroke font: legible from about nine pixels up, at a
stroke weight of about one. A heavier pen still closes the bowls — heavier is worse, not
bolder — and there is no size at which it has the texture of a real typeface. Genesis AIR
names its type scale in `genesis.view` so no call site can pick a size outside that window,
and every strip that holds a row of labels measures them first and steps the size down until
they fit.

---

## Closed earlier

- **No long-lived subprocess with writable stdin.** Recorded here first, then fixed upstream:
  `stdlib/process.ai` gained `spawn_piped` / `write_stdin` / `read_stdout` / `poll` / `wait`,
  backed by `runtime/air_proc_pipe.c`. This project now pins a commit that carries it; the
  export now uses it for a persistent worker. Interactive probe and preview requests still
  use short worker invocations, as recorded in the README.
