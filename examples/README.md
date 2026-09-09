# Example projects

`demo.air` is the project `genesis-air demo` builds: three media sources, four tracks, two
video clips with a crossfade between them, an audio bed, a two-filter stack, opacity
keyframes, a marker and a subtitle.

It is an ordinary `air.editor.project` document — the schema the AIR NLE toolkit defines, not
a Genesis-only format — so anything that reads that schema can open it.

```sh
../build/genesis-air render /tmp/demo.png demo.air   # paint it headlessly
../build/genesis-air open demo.air                   # open a window on it
```

The media paths it names are placeholders; with the fake provider they resolve to
deterministic synthetic frames, which is what the tests use.
