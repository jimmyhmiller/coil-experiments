# Heap inspector

A whole-program transform inspired by `lang-with-inspector`. It recognizes the
*checked declaration* `coil.alloc/create [T]` (not its spelling) when `T` is a
concrete struct. `box` expands through `create`, so it is included naturally.
Successful `Option` results are registered without changing payload layout;
failure remains `None`. Arguments are evaluated once. The matching checked
`coil.alloc/destroy` unregisters immediately before destruction.

```sh
cd /path/to/coil-experiments
coil build src/experiments/heap-inspector/demo.coil \
  -o /tmp/heap-inspector-demo --use experiments.heap-inspector.transform
/tmp/heap-inspector-demo
# or: src/experiments/heap-inspector/scripts/demo.sh
```

The JIT demo submits inspector queries at runtime. The host exports the inspector
functions so submitted forms can resolve them. On Linux x86-64 it must also link
LLVM because `coil.jit` uses Coil's LLVM MCJIT backend:

```sh
coil build src/experiments/heap-inspector/jit_demo.coil \
  -o /tmp/heap-inspector-jit \
  --use experiments.heap-inspector.transform \
  --link-flag "-L$(llvm-config --libdir)" \
  --link-flag -lLLVM --link-flag -lm \
  --link-flag -Wl,--export-dynamic
/tmp/heap-inspector-jit
```

On macOS arm64, omit the LLVM flags and use
`--link-flag -Wl,-export_dynamic`. The ordinary demo deliberately does not
import `coil.jit`: source-linking the compiler into a binary is expensive when
runtime query submission is not being demonstrated.

The side registry assigns monotonically increasing instance IDs and records the
pointer, type ID, and live bit. Generated metadata contains compile-time type
text, `sizeof`, `alignof`, field count/names/types, plus a type-specific callback.
Field metadata is queryable at runtime and includes each field's index, name,
type text, and byte offset. Coil's current field reflection preserves concrete
type arguments for fields of a generic instantiation, but reports only the base
name for an ordinary field such as `(slice u8)` or `(ptr Point)`. The callback
safely prints i64, bool, f64, and pointer fields; slices and other unsupported
field kinds are explicitly shown as unsupported rather than reinterpreted.
Nested structs by value are not recursively formatted; pointers to nested
structs are shown as addresses. The fixed registry supports 256 type
records and 4096 instances and is single-threaded.

Stable non-generic output APIs are `inspector-list-types`,
`inspector-list-instances`, and `inspector-inspect`. The JIT demo keeps one
`JitSession`, submits complete forms calling these APIs when `jit-supported?`,
and clearly reports the unsupported path. The query forms declare `extern` C
symbols and call back into the host registry; importing the runtime into the JIT
would incorrectly create a second set of static cells. The host must therefore
export those symbols dynamically. Executing Coil's JIT currently supports
macOS arm64 and Linux x86-64.

## Exact surface and limitations

Only typed `create [concrete-struct]` is tracked: not `alloc-slice`, arrays,
primitives, stack/static, `raw-alloc`, direct malloc/casts, or primitive heap
allocation. Concrete generic struct instantiations are eligible when exposed by
the checked type model. Calls bypassing `destroy` (`raw-free`, direct `free`) are
not observable, nor is arena bulk reset; arena `destroy` itself is a no-op but
still removes the logical registry entry. Escaped pointers can therefore outlive
or underlive registry information. There is no concurrency synchronization.
This is precise instrumentation of the supported API surface, not universal
liveness tracking.
