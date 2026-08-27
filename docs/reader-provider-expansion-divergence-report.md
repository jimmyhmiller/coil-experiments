# Coil bug report: registered `--use` reader diverges from direct reader expansion

## Summary

A registered reader provider used through `coil run FILE --use PROVIDER` does
not exhibit changes that are visibly present when the same reader is invoked
directly to emit Coil source. Touching the consumer and the provider module does
not resolve the divergence.

This blocks debugging metaprograms because there is currently no way to tell
whether `--use` compiled the newly emitted forms or reused an older specialized
reader result.

This is reproducible in the `feature/ohm-metaprogram` worktree at commit
`223b0932ba3a5a8a5e554a25a9a33294089bc9f2`, plus the current uncommitted
failure-scope experiment.

Repository:

`/Users/jimmyhmiller/Documents/Code/projects/coil-experiments-ohm`

## Provider

`src/dialects/ohm/builder_lang.coil`:

```coil
(module experiments.ohm.builder-lang)

(reader-provider "experiments.ohm.builder" read-ohm-builder)
```

The provider delegates to `read-ohm-builder` in
`src/dialects/ohm/builder.coil`, which delegates to the implementation in
`src/dialects/ohm/reader.coil`.

## Consumer

`tests/ohm/match-node-public-dump-runtime.coil`

The relevant grammar is equivalent to:

```ohm
G {
  Start = item+ ending?
  item = letter | digit
  ending = "!"
}
```

For input `!`, the final output record currently contains the expanded failure
descriptions:

```text
a lowercase letter, an uppercase letter, a Unicode character in Lt, Lm, or Lo, a letter, or a digit
```

The expected result from Ohm is:

```text
a digit or a letter
```

## Reproduction

From the worktree root:

```sh
coil run experiments.ohm.builder-lang \
  tests/ohm/match-node-public-dump-runtime.coil \
  > /tmp/ohm-expanded.coil

rg -o 'begin-failure-scope' /tmp/ohm-expanded.coil | wc -l
```

Observed:

```text
142
```

The directly emitted program visibly contains the newly generated calls to:

```coil
experiments.ohm.runtime.begin-failure-scope!
experiments.ohm.runtime.finish-failure-scope!
experiments.ohm.runtime.memo-find-named
```

Now execute the same consumer through its registered provider:

```sh
coil run tests/ohm/match-node-public-dump-runtime.coil \
  --use experiments.ohm.builder-lang \
  --backend arm64 | tail -1
```

Observed: the failure still contains all five expanded descriptions, exactly as
it did before those generated forms were added.

The same result persists after each of the following source changes:

1. Editing a comment in the consumer.
2. Structurally changing the Builder grammar from `(app letter)` to the
   equivalent `(seq (app letter))`.
3. Editing a comment directly in `builder_lang.coil` beside the
   `reader-provider` declaration.
4. Re-running with a fresh `/tmp` output path.

The runtime dependency itself *does* rebuild. Temporary instrumentation added
to `record-expectation!` produced new stderr output during the `--use` run.
Thus runtime imports are current while the status of the specialized reader
expansion is unclear.

## Additional direct-emission symptom

Compiling the directly emitted source is not currently a usable workaround:

```sh
coil run /tmp/ohm-expanded.coil --backend arm64
```

This terminates with a signal (`SIGSEGV` or `SIGILL`, depending on the reduced
fixture). The same consumer succeeds when compiled through `--use`.

That gives a second observable divergence between the registered-reader path
and the reader's emitted Coil source.

## Expected behavior

1. Every `--use` compilation should specialize the reader from the current
   transitive source graph, including changes in the provider's imported
   implementation modules.
2. If reader expansions are cached, the cache key must include the provider,
   its transitive dependencies, the consumer syntax/input, compiler flags, and
   compiler version.
3. Coil should provide a way to dump the exact post-reader forms used by a
   `--use` compilation so the generated program can be compared with direct
   reader invocation.
4. Compiling those dumped forms directly should be behaviorally equivalent to
   compiling the consumer through `--use`.

## Actual behavior

- Direct invocation visibly emits the new forms.
- The registered `--use` execution retains the pre-change observable result.
- Runtime-only instrumentation is picked up, so this is not a wholly stale
  executable.
- Direct compilation of the emitted forms terminates by signal while `--use`
  compilation succeeds.

## Important qualification

This evidence proves a divergence between the two compilation paths, but it
does **not** yet prove that cache invalidation is the root cause. Other possible
compiler causes are:

- the registered provider specializes a different syntax object or phase than
  direct invocation;
- some emitted forms are discarded or reordered at the reader-provider
  boundary;
- hygiene causes the directly emitted textual forms and the syntax objects
  compiled by `--use` to resolve differently;
- the `--use` path uses a cached reader specialization whose dependency key is
  incomplete.

The most useful compiler-side diagnostic would be a dump of the exact expanded
syntax objects consumed by the `--use` compilation, including resolved/hygienic
identities, plus cache hit/miss and cache-key dependency information.

## Impact

This prevents reliable development and verification of nontrivial Coil reader
metaprograms. Source-level inspection says one program was generated, while the
only supported `--use` execution path cannot be shown to compile that program,
and compiling the textual expansion directly is not equivalent.
