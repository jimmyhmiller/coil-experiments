# Markdown agent materializer

This is the first end-to-end implementation of Markdown-specified Coil source.
It is a build-time materializer rather than a runtime interpreter or an LLM call
inside a reader callback.

```sh
coil run src/apps/markdown-agent/main.coil -- \
  src/my-module.md \
  src/my-module.coil \
  my-project.my-module \
  - \
  ./build/markdown-agent-runner \
  /Users/you/.cargo/bin/coil
```

Build the small runner once with:

```sh
(cd tools/markdown-agent-runner && coil build main.coil -o ../../build/markdown-agent-runner)
```

Behavior:

- If the target `.coil` exists, it is used immediately and no agent runs.
- Otherwise, the Codex provider works in the current repository and writes a
  sibling `.candidate` file.
- Agent execution uses the included one-shot Coil runner. It is a copied,
  self-contained slice of `coil-agent-harness`: the provider-neutral agent loop,
  Coil-native direct Codex HTTP provider, subscription credential loader, and
  repository-bounded filesystem, search, and Bash tools. It never launches the
  Codex CLI. There is no factory, coordinator, workflow, service, or TUI layer.
- The only mandatory acceptance gate is Coil type checking. Pass `-` for the
  contract argument to generate complete applications from Markdown alone.
- When a Coil contract is supplied, the materializer additionally promotes the
  candidate provisionally, checks the contract's consumer graph, and executes
  it under a deadline.
- A consumer-graph failure moves the target back to staging and sends those
  diagnostics to the next attempt.
- Compiler diagnostics are included in the next attempt, up to five attempts.
- A passing candidate is atomically renamed to the target `.coil` file.
- A failing candidate never becomes the target.

Contracts are optional and may themselves be generated from Markdown: first
materialize `contract.md` to `contract.coil` with `-` as its own contract, then
pass the resulting `contract.coil` when materializing or verifying the production
module. Generated contracts are ordinary inspectable Coil artifacts and run
offline once persisted.

This version intentionally does not regenerate an existing `.coil` file. Doing
that safely requires the generated-artifact ownership and fingerprint contract
described in the `coil-markdown-reader-plan` pad. The next integration step is a
compiler pre-index hook that invokes this materializer for missing configured
Markdown modules.
