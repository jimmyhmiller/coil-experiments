# Forth, compiled by a Coil metaprogram

`experiments.forth.lang` reads ordinary `.fth` source at compile time and emits
ordinary Coil. The generated program has direct integer operations and native
control flow; it does not contain a token dispatcher or Forth data stack.

```sh
coil run tests/forth/hello.fth --use experiments.forth.lang
coil run experiments.forth.lang tests/forth/hello.fth   # print generated Coil
```

## Language

- Integers: decimal literals on an `i64`.
- Arithmetic: `+ - * / mod negate`.
- Comparisons and booleans: `= <> < > <= >= and or invert`.
- Stack: `dup drop swap over depth nip tuck rot -rot pick`.
- Memory: `variable`, `@`, `!`; arrays are deliberately omitted in this slice.
- Control flow: structured `if ... else ... then` and `begin ... again/until/while ... repeat`.
- Definitions: `: name body ;`, with static resolution, recursion support, and
  exact compile-time stack-effect checks.
- Output: `. prints the top integer; emit prints one byte.
- Comments: `\` to end of line and `( comment )`.

The implementation intentionally keeps the language compact rather than adding
untyped execution machinery. Its value is the metaprogramming boundary: Forth
source becomes checked Coil definitions before optimization, so generated code
is as direct as hand-written Coil for this subset.

## Status

The scanner, token model, and generated-module boundary are implemented. The word compiler and native lowering are still being built; running a nonempty program does not yet execute it.
