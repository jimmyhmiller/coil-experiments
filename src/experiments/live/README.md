# experiments.live: make a Coil program live

Add two things to a program's `Coil.toml`:

```toml
[dependencies]
live = { path = ".../coil-experiments/src/experiments/live" }

[metaprograms]
use = ["experiments.live.enable"]
```

Run `coil run` in that project. Or use `coil build` and run the binary. From then
on every save in the entry's project source graph reaches the running
program, including transitive imports. `src/experiments/live-demo` is a complete example.

## What happens

- The built binary is the live host (`host.coil`). At startup it compiles the
  project source graph with Coil's in-process compiler and runs its `main`.
- On every save, the host diffs the project against what the program runs,
  definition by definition. It ignores layout and comments. It then applies
  a complete generation as one transaction, preserving each module's identity. When the edit does not
  check, nothing changes, and the program keeps running its previous version.
  No state is lost.
- Values held in `letonce` roots survive every edit. That includes edits to
  their structs, when each changed field has a default or a
  `(migrate Type field old EXPR)` form.
- A definition deleted from the file stays in the running program until it
  restarts. The whole edit is reported as `needs-restart`; restoring the
  definition allows live editing to continue.
- An existing `letonce` initializer is checked when edited, but never rerun.
  Its running value changes through a field migration. New structs and roots
  can be added in the same transaction.

What is not live:

- `main` itself: it is entered once on the native main thread. Keep the event
  loop in `main` and put frame/update work in functions it calls. The entry
  signature is `(defn main [] (-> i64) ...)`.
- Native layouts used through raw pointers or FFI: their functions can change,
  but changing an existing native storage layout requires a restart. Put state
  that needs migration in managed `letonce` values. Native static cells keep
  their addresses across function edits; changing their allocation sites,
  types or initializers requires a restart.
- Removing an accepted definition: restore it or restart. Ordinary imported
  function edits, constants, and adding imports do not require a restart.

The status says which of these an edit ran into.

## Seeing what happened

After a save, any of these works:

- `coil lint`, `coil check` or `coil build` in the project. While the program runs, they
  fail with an error at each form the running program did not take.
  - They wait a few seconds for the program to finish applying the save first.
  - They also fail while the program runs an out-of-date version of another
    module. So to rebuild after a change that needs a restart, stop the program
    first.
  - With no program running, `coil check` and `coil build` still typecheck the
    project using the live reader's initial-generation lowering. Project lint
    runs source checkers; use `coil check` for offline type checking.
- `.coil-live/STATUS.md`, the same report in Markdown.
- `.coil-live/verdict.coil`, the same report as data.
- The program's stderr, one line per save.
- `coil-live` (below).

A report's state is one of:

| State | Meaning |
|---|---|
| `live` | The program runs the current project sources. |
| `pending` | The saved version has not been processed yet. Wait for the watcher or use `coil-live apply`. |
| `rejected` | The edit does not check. The compiler's errors are attributed to the definitions concerned, and the program runs its previous version. |
| `needs-migration` | A struct changed while the program holds values of it. The report shows the `migrate` form to add. |
| `needs-restart` | The edit changes the active main, a native layout, or removes a definition. |
| `unreadable` | The file is missing, inaccessible, or has invalid delimiters/string syntax. |
| `would-apply` | Only from a check: the edit would apply. |

## For agents: `coil-live`

`src/experiments/live-cli` builds `coil-live`, which talks to the running
program:

```sh
cd src/experiments/live-cli && coil build     # -> build/release/coil-live
# Or: coil install                         # put coil-live on your PATH

coil-live status [--json] [--dir DIR]   # what the program did with the latest save
coil-live check  [--json] [--dir DIR]   # dry-run the file as it is on disk
coil-live apply  [--json] [--deferred] [--dir DIR]   # apply now, as a save would
```

DIR defaults to the working directory; the CLI finds the nearest enclosing
`Coil.toml`, so it also works from source subdirectories. The CLI verifies the
canonical project identity before a file operation. Exit status is
0 when the program runs the file as it is, 1 when it does not, and 2 when no
program answers. `--deferred` applies what checks and marks the broken callers
for repair, instead of changing nothing.

Requests have a 30-second reply deadline. Use `--timeout-ms N` (1–3600000) to
change it. A timeout does not cancel an in-flight apply; inspect status before
retrying. `status` never reports an older version as the latest saved version:
it reports `pending` until the watcher has processed the save. A dry-run check
does not itself publish; the independent watcher still watches saved files.

`coil-live mcp [--dir DIR]` serves the same three as MCP tools
(`live_status`, `live_check`, `live_apply`) over stdio. Its instructions tell
the model how to work with a live file. For Claude Code:

```sh
claude mcp add coil-live -- /abs/path/to/coil-live mcp --dir /abs/path/to/project
```

A snippet for a live project's `AGENTS.md` or `CLAUDE.md`:

The complete procedure is in [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).

> This program runs the source graph rooted at `ENTRY.coil` live. Edit any
> participating project module with ordinary file edits. After
> each save, run `coil-live apply --json` to submit and observe that version,
> or `coil-live status` to observe the watcher. `pending` means try again after
> processing. `coil lint` and `coil check` also show migration requirements.
> If an edit was rejected,
> fix the definitions it names; the program is still running the previous
> version. If it needs a migration, add the `migrate` form it shows next to the
> struct in its owning module. If it needs a restart, report the exact reason.

Editors can use the same operations over the program's nREPL server
(`.nrepl-port`): `coil/file-status`, `coil/file-check` and `coil/file-apply`,
with optional `policy` (`strict`, `deferred`) and `format` (`markdown`,
`json`) keys.

File-owned sessions reject `eval` and `load-file`: those would change the
runtime without updating its source ledger. Edit project files and submit them
with `coil/file-apply`. Standalone REPL sessions retain their eval operations.

## Runtime boundary and verification

The package owns the live reader, retained compiler session, state migrations,
watcher, and editor protocol. No live features are built into Coil's compiler.
An OS advisory lock admits one active host per project and releases on exit or
crash. Discovery is published atomically before the application's main starts.
The server binds loopback, limits concurrent clients and request sizes, times
out incomplete requests, and reclaims each response after sending it.

One active project per process owns the source graph reachable from its entry.
Files under the consumer project root participate, including transitive imports
and new modules discovered by namespace identity. External dependencies remain
dependencies; editing a separate dependency checkout is outside that project's
publication boundary. Each verdict lists every participating file and version.
Missing imported files reject the candidate; restoring them resumes live edits.
Local stack variables are not persistent roots. Live-managed values belong in
`letonce` roots, and rendering/update work belongs in returning functions so
the runtime can acquire a quiescent point. A long-running call can delay a
transaction. The publisher never invokes application redraw functions on its
worker: UI scheduling remains with the native event loop. Unsafe FFI, raw pointers into layouts, arbitrary migration side
effects, and application crashes cannot be made safe by the file adapter.
Trait declaration and closure-signature changes are not currently supported.

The development harness creates a separate consumer outside this workspace:

```sh
python3 scripts/live-integration.py
python3 scripts/live-integration.py --gui  # macOS AppKit/CALayer window
```

It verifies real file edits, running state continuity, rejected candidates,
imported-only edits, new transitive imports, imported native renderer changes,
located migration feedback from both project lint and check, migration
submission exactly once, offline type errors, nested project discovery,
duplicate launches, MCP calls, packet fragmentation, malformed replies,
deadlines, missing files, and recovery. GUI frames assert `pthread_main_np()`
throughout. Python is test orchestration only; the application, CLI, server,
reader, and migration runtime are all Coil. Logs go to `build/test-logs/live/`.

## Files

- `enable.coil`: the module a manifest names. It brings in the host and the
  transform.
- `enable_transform.coil`: rewrites the entry module to start the host, and
  reports the running program's verdict at the forms concerned in
  `coil check` and `coil build`.
- `host.coil`: the live host. It covers the file watcher, the verdicts and
  status files, the nREPL server and `coil/file-*` ops, and startup.
- `project.coil`: immutable source graph snapshots using the public Coil SDK.
- `ledger.coil`: module-scoped definition diffs for project generations.
- `digest.coil`: the file fingerprint the host and the checker share.
- `ledger_test.coil` and `host_test.coil`: `coil test --suite live`.
