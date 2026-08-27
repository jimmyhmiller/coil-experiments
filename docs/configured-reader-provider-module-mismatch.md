## Bug: `[readers]` rejects modules that contain a valid `reader-provider`

Status: reproducible with current installed `coil 0.1.0` on 2026-08-26.

### Summary

The manifest documentation says `[readers]` maps a suffix to the ordinary Coil
module that **contains** one `reader-provider` declaration. Coil finds that
declaration, but registers the declaration's implementation-module string as the
active reader identity. It then compares that identity to the manifest's
containing-module name and reports that the containing module has no provider.

This prevents a `.ohm` import from using the already-working Ohm reader through
the new extension mapping.

### Minimal shape

`Coil.toml`:

```toml
[package]
name = "ohm-demo"
entry = "main.coil"

[readers]
".ohm" = "experiments.ohm.cst"
```

`experiments.ohm.cst`:

```coil
(module experiments.ohm.cst)

(reader-provider "experiments.ohm.reader" read-ohm-cst)
```

Command:

```sh
coil run
```

Actual result:

```text
error: [readers] provider module 'experiments.ohm.cst' does not declare a reader-provider
```

The same declaration works through the established CLI path:

```sh
coil run some-file.ohm --use experiments.ohm.cst
```

### Local-wrapper reproduction

Putting the declaration directly in an app-local module produces the same
failure:

```coil
(module experiments.ohm-demo.reader)

(reader-provider "experiments.ohm.reader" read-ohm-cst)
```

```toml
[readers]
".ohm" = "experiments.ohm-demo.reader"
```

Actual result:

```text
error: [readers] provider module 'experiments.ohm-demo.reader' does not declare a reader-provider
```

Trying to make the declaration's first string equal the containing module and
importing the implementation function instead:

```coil
(module experiments.ohm-demo.reader)
(import "experiments.ohm.reader" :use [read-ohm-cst])
(reader-provider "experiments.ohm-demo.reader" read-ohm-cst)
```

gets past the first check, but fails later with:

```text
error: read phase: provider 'experiments.ohm-demo.reader.read-ohm-cst' is absent from the settled program
```

### Compiler-side evidence

In the installed compiler's `driver.coil`:

- `provider-in-forms` parses `(reader-provider "MOD" FN)` into a
  `ReaderProvider` whose `.module` is `MOD`.
- `discover-reader-providers` scans the configured containing module but stores
  only that parsed `ReaderProvider`.
- `activate-configured-readers` stores `.module pp` as the active source-reader
  identity.
- `configured-reader-missing` compares each module named by `[readers]` against
  those active identities.

Therefore the configured name `experiments.ohm.cst` is compared against
`experiments.ohm.reader`, even though `experiments.ohm.cst` is exactly the module
that contains the declaration.

### Expected behavior

The manifest value should identify the module containing the declaration, as the
guide specifies. Discovery should retain both identities:

1. the containing/provider-declaration module used for `[readers]` dispatch; and
2. the implementation module and function used to compile/invoke the reader.

The configured-reader presence check and suffix dispatch should use identity 1.
The generated read setup should import and invoke identity 2.

### Impact

Configured source-extension readers cannot use the normal wrapper pattern already
used by Coil dialects (`cst.coil`, `lang.coil`, `brainfuck.coil`, and others).
The Ohm metaprogram passes its direct `--use` parser tests, but a normal app cannot
yet import an `.ohm` module through `[readers]`.
