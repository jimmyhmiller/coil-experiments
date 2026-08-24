# Compiler bugs found while building the native C frontend

Self-contained reductions. Each is run directly:

```sh
coil run -O0 tests/coil-bugs/<case>.coil    # correct
coil run -O1 tests/coil-bugs/<case>.coil    # wrong
```

## `bool-field-in-arraylist.coil`

A `bool` struct field pushed into an `ArrayList` reads back as `false` at `-O1`
and above. `-O0` is correct, and the same struct with `i64` in place of `bool`
is correct at every level.

```
-O0:  bool field: got 1, want 1
      i64  field: got 1, want 1
-O1:  bool field: got 0, want 1     <-- silently wrong
      i64  field: got 1, want 1
```

There is no error and no warning; the value is simply false. Anything that
keeps flags in a record — a token stream, a parser state, a work queue — is
affected, and the symptom appears far from the cause.

Found while writing `src/dialects/c/lex.coil` and `src/dialects/c/pp.coil`,
where it silently cleared the `at-line-start` and `preceded-by-space` flags on
every token and every entry of the preprocessor's conditional stack. Both
modules now spell their flags `i64` and convert at the accessor boundary; the
struct definitions carry a comment pointing here.
