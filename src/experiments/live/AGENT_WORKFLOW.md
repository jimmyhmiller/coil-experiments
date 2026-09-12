# Editing a running Coil program

The entry in `Coil.toml` roots the live project source graph. Its project modules,
including transitive imports, are live. Find the active project with `coil-live status --json --dir PROJECT`.
The report identifies the entry, accepted epoch, project version, participating files, and problems.

1. Read the affected modules and current report. Persistent application values live in
   `letonce` roots. Preserve their names when editing behavior.
2. Make one complete source edit, including affected callers and migrations.
   An atomic file replacement avoids exposing intermediate writes to the watcher.
3. Run `coil-live apply --json --dir PROJECT`. This submits that saved version
   and returns its verdict. Ordinary saves also apply automatically.
4. Check the verdict and exit code. Exit 0 means live, 1 means pending/rejected
   or needing repair, and 2 means the connection/request failed. A reply timeout
   does not cancel the transaction: inspect status before retrying it.
5. Verify the application's actual behavior. An accepted compilation alone does
   not establish that the intended visual or behavioral change is correct.

For `needs-migration`, read the field diagnostic and add its `migrate` form next
to the struct. Supply the actual conversion, not a guessed placeholder:

```coil
(defsum Visibility (Hidden) (Visible))
(defstruct Particle [(visible Visibility (Visible))])
(migrate Particle visible old (if old (Visible) (Hidden)))
```

Update consumers of `visible` in the same save. `coil lint` and `coil check` in
the project report the pending migration while the old program remains running.
After acceptance, the migration may stay in the source: the ledger does not
submit it again. Editing a `letonce` initializer changes what a future fresh
start uses; it does not reset the existing value.

For `rejected`, repair the named definitions. For `pending`, wait for the watcher
or use `apply`. For `needs-restart`, explain the exact reason; do not disguise a
restart as preserved state. For `unreadable`, restore valid source and submit
again. Never delete discovery/status files to hide a rejected generation.

Keep the one-shot `main` event loop stable. Put state updates and rendering in
returning functions called from it. Use normal file edits and the file protocol;
file-owned sessions reject REPL `eval`/`load-file` so the source ledger remains
authoritative. Use strict publication by default. Deferred publication is an
explicit recovery mode that can suspend broken callers.

The MCP server exposes the same workflow as `live_status`, `live_check`, and
`live_apply`; each accepts a project `dir`. `live_check` does not itself publish,
but saving the file still allows the independent watcher to apply it.
