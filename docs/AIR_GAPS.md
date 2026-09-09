# AIR gaps found by Genesis AIR

Genesis AIR uses AIR; it does not modify it. When building this application ran into
something AIR could not express, the gap is recorded here with the smallest fix that would
close it, the file it belongs in, and a reproducer — and the application works around it in
a way that stays visible to the person using it, rather than pretending the feature exists.

Nothing in `CodeAlexx/AIR` was changed for any entry below.

SDK pinned by this project: `air-sdk.conf` → `AIR_SDK_COMMIT`.

---

## 1. `std.editor` cannot write a clip's speed or reverse flag

**What is missing.** `editor.Clip` carries `speed: f64` and `reverse: bool`, `editor_io`
round-trips both, and `editor.clip()` reads them — but there is no setter. `set_clip_gain`,
`set_clip_enabled`, `set_fade_in` and `set_fade_out` all exist; speed and reverse have no
equivalent.

**Why it matters here.** The inspector's SPEED section can display a clip's speed and
reverse flag but cannot change them. Modelling speed as a filter parameter instead was
rejected: `Clip.speed` already exists, and a second store for the same fact is exactly the
disagreement this codebase is built to avoid.

**Smallest fix.** Two functions in `stdlib/editor.ai`, beside `set_clip_gain`:

```
pub fn set_clip_speed(doc: ref<Document>, id: u64, value: f64) -> bool
pub fn set_clip_reverse(doc: ref<Document>, id: u64, value: bool) -> bool
```

**Affected file.** `stdlib/editor.ai` (AIR).

**Reproducer.** In a document with one clip, `editor.clip(doc, id).speed` reads `1.0` and no
call in the module can make it read anything else.

**What Genesis AIR does instead.** The SPEED rows are read-only and the panel says so, in
`src/chrome.ai` (`properties_panel`).

---

## 2. `std.editor` cannot reorder tracks

**What is missing.** `add_track` appends with the next `order`, and `remove_track` deletes;
nothing moves a track to a different lane. `editor_view.lanes` sorts by `Track.order`, so
lane position is entirely determined by creation order.

**Why it matters here.** The conventional layout is video above audio. Because the topmost
lane is the highest `order`, Genesis AIR has to CREATE its default tracks bottom-up
(A2, A1, V1, V2) to get V2/V1/A1/A2 top-down. That works for the default project, but a
track added later with the `+A` button lands at the top of the stack instead of below the
video, and nothing can move it down.

**Smallest fix.** One function in `stdlib/editor.ai`, mirroring `reorder_filter`, which
already does exactly this for filter stacks:

```
pub fn reorder_track(doc: ref<Document>, id: u64, position: u32) -> bool
```

**Affected file.** `stdlib/editor.ai` (AIR).

**Reproducer.** `add_track(doc, seq, track_audio(), "A3")` on a document whose tracks are
A2, A1, V1, V2 puts A3 above V2 in `editor_view.lanes`, and no call can move it.

**What Genesis AIR does instead.** Seeds its tracks bottom-up (`src/app.ai`,
`src/commands.ai::new_project`) and leaves later additions where the toolkit puts them.

---

## 3. `std.vector_font` has almost no punctuation

**What is missing.** `vector_font.glyph_points` covers `0-9`, `A-Z`, `a-z`, `+`, `-` and
`.` — 65 codepoints. Everything else, including `:` `/` `(` `)` `%` `<` `>` `|` `^` `_` `,`
`?` `*` `=` and every non-ASCII character, returns no outline. Unsupported characters
advance the pen but draw nothing, so they render as gaps.

**Why it matters here.** A label made only of unsupported characters draws as an empty
button. The first build of the toolbar had transport buttons labelled `|<` `<` `>` `>|` and
they came out blank.

**Smallest fix.** Additional entries in `glyph_points` for the printable ASCII punctuation,
in the same two-value polyline format the existing glyphs use. No API change.

**Affected file.** `stdlib/vector_font.ai` (AIR).

**Reproducer.** `font.text_vector_width("<>", 7.0)` returns a non-zero advance while
`font.glyph_points(60)` returns an empty array.

**What Genesis AIR does instead.** Every control label is spelled with supported characters
(`Start`, `Prev`, `Next`, `End`, `Up`, `Dn`, `Zoom in`, `Zoom out`), and the prompt's caret
is a drawn rectangle rather than an underscore.

---

## Closed since this project started

- **No long-lived subprocess with writable stdin.** Recorded here first, and now fixed
  upstream: `stdlib/process.ai` gained `spawn_piped` / `write_stdin` / `read_stdout` /
  `poll` / `wait`, backed by `runtime/air_proc_pipe.c`, on AIR `main`. Genesis AIR has not
  adopted it yet because `air-sdk.conf` still pins the pre-merge NLE commit; adopting it
  means repointing the pin and rebuilding the compiler for the new opcodes, which is a
  separate change from this one.
