# Debug allocator transform

Build a Coil program with allocator tracing:

```sh
python3 scripts/coil-memory-guard.py --limit-mib 2048 -- \
  coil build path/to/app.coil -o /tmp/app-debug \
  --use experiments.debug-allocator.transform
```

Run the binary normally. On exit it prints one line beginning
`COIL_DEBUG_ALLOCATOR_JSON=` with the complete JSON report. No application
source change is needed. For a report while the process is still running, call
`experiments.heap-inspector.runtime/inspector-snapshot` explicitly.

The transform rewrites checked `coil.alloc` protocol operations (`raw-alloc`,
`raw-resize`, `raw-remap`, `raw-free`) and records the application call site for
`create` and `alloc`. The ordinary allocator remains underneath every marker.
The report contains live allocations and a `sites` array. Each site reports file, line,
column, cumulative allocation count and bytes, current count and bytes, and
peak live bytes. `sourceFile`, `sourceLine`, and `sourceColumn` also appear on
each live allocation. The source site is the checked `coil.alloc` boundary for
allocations that do not pass a marked `create` or `alloc` call.

The recorder uses a 33,554,432-entry live-allocation registry with a pointer hash
index, slot reuse, and a 16,384-entry source-site registry. It prints a source-site
census every 100,000 allocations, including process ID, so an external RSS guard
still leaves a recent report when it terminates a runaway process. It aborts with a
diagnostic when a registry fills, so no allocation record is silently discarded.
This is diagnostic instrumentation; it is not intended for production
performance measurements.

This transform instruments allocations made by the *compiled program* through
`coil.alloc`. It cannot intercept the host Coil compiler, direct libc or foreign
library allocation, primitive static allocation, or stack storage. Use
`scripts/coil-memory-guard.py` around `coil` commands to bound the compiler's
process-tree RSS. The guard samples RSS, so a rapidly allocating process may
temporarily exceed the threshold before termination.
