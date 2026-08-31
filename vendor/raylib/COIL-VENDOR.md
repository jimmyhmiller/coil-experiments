# Vendored Raylib source

This directory contains Raylib's complete `src/` tree at commit
`c1ab645ca298a2801097931d1079b10ff7eb9df8` from
<https://github.com/raysan5/raylib>. The upstream `LICENSE` is included beside
this file.

It is vendored so a normal Coil import is reproducible and requires no network
or source-generation step. `[c.raylib]` in the repository `Coil.toml` selects
the translation units used by the demo.
