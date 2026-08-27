# Reader-provider `Code` boundary regressions

These are two minimal, Coil-only reproductions extracted from the Ohm reader.
Both involve a `Code` value crossing an ordinary helper-function boundary while
a reader provider is evaluated by `--use`.

## Resolution

Both regressions are fixed at Coil repository revision `b999fc9`. The failing
commands and both controls now exit 0. The remainder of this document preserves
the original reports and diagnostics as regression-test context.

Environment used to reproduce:

```text
coil 0.1.0
binary: /Users/jimmyhmiller/.cargo/bin/coil
Coil repository revision: 8767276
```

## 1. A helper-returned `Code` form is parsed in expression position

Files:

- `src/dialects/reader_nested_defn_repro/reader.coil`
- `src/dialects/reader_nested_defn_repro/lang.coil`
- `tests/ohm/reader-nested-defn.input`

The essential shape is:

```coil
(defn make-rules [] (-> Code)
  `(defn rules [] (-> i64) 0))

(defn build-program [(context Code) (source (slice u8))] (-> Code)
  (let [rules (make-rules)
        main-name (primitive/datum->syntax context "main")]
    (if (= (len rules) 0)
        (primitive/error "missing rule")
        `(do
           (module reader-nested-defn-repro.generated)
           (defn ~main-name [] (-> i64)
             (if (= ~source "ok\n") 0 1))))))
```

Reproduce:

```sh
coil run tests/ohm/reader-nested-defn.input \
  --use experiments.reader_nested_defn_repro.lang
```

Actual result:

```text
error: 'defn rules' is a top-level definition, but it appears inside an expression — an enclosing form is missing a ')'
```

Expected result: exit 0. `rules` is a runtime metaprogram value of type `Code`.
Calling the `Len` trait on it should inspect its children; the quoted definition
should not be inserted into the source expression containing `(len rules)`.

Control case:

```sh
coil run tests/ohm/reader-nested-defn.input \
  --use experiments.reader_nested_defn_repro.direct
```

The control exits 0. It performs the same `len` call when the quoted `Code` value
is created directly in the registered reader instead of being returned by
`make-rules`.

This suggests reader-provider specialization is substituting helper-returned
`Code` as syntax into an expression rather than preserving it as a first-class
metaprogram value.

## 2. A reader context passed to a helper loses its collection shape

Files:

- `src/dialects/reader_code_get_repro/reader.coil`
- `src/dialects/reader_code_get_repro/lang.coil`
- `tests/ohm/reader-code-get.input`

The essential shape is:

```coil
(defn read-impl [(context Code)] (-> Code)
  (let [source (primitive/code-str (get context 2))
        main-name (primitive/datum->syntax context "main")]
    `(do
       (module reader-code-get-repro.generated)
       (defn ~main-name [] (-> i64)
         (if (= ~source "ok\n") 0 1)))))

(defn read-source [(context Code)] (-> Code)
  (read-impl context))
```

Reproduce:

```sh
coil run tests/ohm/reader-code-get.input \
  --use experiments.reader_code_get_repro.lang
```

Actual result:

```text
error: comptime: code-nth expects a list/vector
```

Expected result: exit 0. The reader-provider contract supplies a list-shaped
`Code` context, and `get` is the ordinary `Get` trait operation for `Code`.

Control case:

```sh
coil run tests/ohm/reader-code-get.input \
  --use experiments.reader_code_get_repro.direct
```

The control exits 0. It performs the same `(get context 2)` directly in the
registered reader. The failure appears only after passing `context` through the
typed helper parameter.

The primitive named in the diagnostic is an implementation detail of the `Get
Code` trait. The reproducer intentionally uses `get`, not
`primitive/code-nth`.

## Impact on the Ohm reader

The Ohm metaprogram parses the canonical Ohm grammar and emits a standalone Coil
parser when invoked directly. The emitted module passes `coil check`. Registering
the same implementation as a reader provider requires both patterns above:

- helper functions exchange grammar nodes represented as `Code`;
- the reader context is passed into helpers for source access and hygienic names.

Inlining everything into the registered function avoids the second regression
but encounters the first. Moving the implementation behind a helper avoids the
first diagnostic but encounters the second. Using `primitive/code-nth` would
only bypass the intended collection API and does not address the staging error.
