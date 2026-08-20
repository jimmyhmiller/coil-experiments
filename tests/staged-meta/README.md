# Staged metacompilation, through the Scheme phase runtime

`staged_scheme_bridge.coil` is a staged entry that imports the full Scheme
*phase* runtime — GC heap, symbols, numerics, syntax objects — and round-trips a
form through `code -> syntax object -> Scheme datum -> Scheme compute ->
datum->syntax -> code`, entirely at expansion time inside the metaprogram
engine. The test exits 42 when the round trip holds.

    coil run tests/staged-meta/staged_scheme_bridge_test.coil ; echo $?   # 42

It ran in Coil's `gate-staged-meta.sh` across the native, `COIL_META_INTERP=1`,
and `COIL_META_ARENA=poison` engines, and moved here with the dialect it
depends on. The procedural `define-syntax` / `syntax-case` / ellipsis
end-to-end cases that ran beside it are `tests/scheme/dialect/proc_syntax_*`.
