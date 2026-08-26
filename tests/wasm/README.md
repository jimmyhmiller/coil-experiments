# WebAssembly conformance tests

The normative target is the official WebAssembly 1.0 core test suite from
`WebAssembly/spec`, maintained tag `wg-1.0`, pinned to
`977f97014c962f7bd1291fcc6d28b41a924882bf`. Its 73 WAST files define the MVP
profile claimed by this reader. The similarly named `v1.0.0` tag is deliberately
not used: it points at a later multi-version documentation commit whose
`test/core` includes post-MVP feature tests. Proposal suites and features
incorporated in Wasm 2.0/3.0 are not part of this initial denominator.

Focused decoder tests are ordinary Coil tests:

```sh
coil test tests/wasm/decoder_test.coil
```

Raw binaries use the standard reader-provider path:

```sh
coil run module.wasm --use experiments.wasm.lang
```

Imported WASM modules use the ordinary project reader mapping and expose
function exports as typed Coil functions:

```toml
[readers]
".wasm" = "experiments.wasm.lang"
```

```coil
(import "my.wasm.module" :as wasm)
(wasm/add 20 22)
```

Fetch, verify, inventory, and prepare the suite with:

```sh
scripts/wasm-spec.sh inventory
scripts/wasm-spec.sh prepare
scripts/wasm-spec.sh test-integers
scripts/wasm-spec.sh test-floats
scripts/wasm-spec.sh test-conversions
scripts/wasm-spec.sh test-memory
scripts/wasm-spec.sh test-tables
scripts/wasm-spec.sh test-control
scripts/wasm-spec.sh test-loops
scripts/wasm-spec.sh test-structured-control
scripts/wasm-spec.sh test-start
scripts/wasm-spec.sh test-basic-instructions
scripts/wasm-spec.sh test-evaluation-order
scripts/wasm-spec.sh test-functions
scripts/wasm-spec.sh test-globals
scripts/wasm-spec.sh test-memory-instructions
scripts/wasm-spec.sh test-types
scripts/wasm-spec.sh test-data-segments
scripts/wasm-spec.sh test-elements
scripts/wasm-spec.sh test-imports
scripts/wasm-spec.sh test-linking
scripts/wasm-spec.sh test-encoding
scripts/wasm-spec.sh test-exports
scripts/wasm-spec.sh test-wat
```

`test-integers` compiles each official `i32` and `i64` module through the reader
and executes all homogeneous, single-result integer `assert_return` commands in
one generated Coil entry point per module. It currently covers 350 `i32` and 205
`i64` assertions. This is a semantic test—not merely a module compile check.

`test-floats` executes all 3,178 ordinary `f32`/`f64` return assertions plus
1,822 canonical- and arithmetic-NaN assertions. Floating inputs and results are
transported as their exact IEEE-754 bit patterns so signed zero, subnormal, NaN
payload, and infinity behavior is checked without a host text conversion.

`test-conversions` executes 334 mixed-scalar conversion results and verifies 67
overflow/invalid-conversion traps as actual process traps. Compiler diagnostics
do not count as passing trap assertions.

`test-memory` checks state persistence, all representative load/store widths,
growth, zero-filled new pages, active data initialization, 68 official byte-order
assertions, and all 36 official `memory_size` assertions across four modules.

`test-tables` checks focused table initialization and indirect dispatch, then
executes every runnable assertion in the official MVP `call_indirect` file: 103
returns and 13 process traps.

`test-control` exercises function returns before unreachable instructions and
returns propagated through nested blocks, loops, and conditionals. It also
checks nonterminal and outer-depth `br`, both paths of nonterminal and
outer-depth `br_if`, and multi-target/default `br_table` selection across nested
typed Coil labeled blocks. A stateful counting loop verifies `br 0` as a loop
continuation and an outer `br_if` carrying the function result. An i64 factorial
loop verifies that assignments before an immediate outer branch are preserved.
It also passes
the complete official MVP `return`
file: 63 returns and 20 validation
failures.

`test-loops` passes the complete official MVP `loop` file: 66 return assertions
and 12 validation failures. This includes loops in operand positions, deep
nesting, branches to inner and outer labels, stateful continuation, and
polymorphic unreachable instruction sequences. Together, the harnesses above
currently execute 6,337 official assertions.

`test-structured-control` passes the complete official MVP `block`, `br`,
`br_if`, `br_table`, and `if` files: 425 returns, 249 validation failures, 12
malformed-text rejections, and one runtime trap. Large branch tables are lowered
to balanced unsigned decision trees, avoiding parser-depth growth while keeping
each target as a lexical Coil transfer. The cumulative official total is 7,024
assertions.

`test-start` passes the complete official MVP `start` file: six returns, three
validation failures, and one instantiation trap. Start functions run exactly
once before direct CLI access or an exported function/global, including starts
that call imported `spectest` functions. The three successful import-only/start
modules and the suite's ordered actions are also instantiated. The cumulative
official assertion total is 7,034.

`test-basic-instructions` passes the complete official MVP `nop`, `break-drop`,
`switch`, `local_get`, `local_set`, `local_tee`, `call`, `select`, and
`unreachable` files: 357 returns, 129 validation failures, and 64 runtime traps.
The cumulative official assertion total is 7,584.

`test-evaluation-order` passes the complete official MVP `labels` and
`left-to-right` files: 120 returns and three validation failures. Typed
`br_if`, `br_table`, `select`, and `call_indirect` operands are materialized in
WASM order and evaluated exactly once, including fallthrough and discarded
stack values. The cumulative official assertion total is 7,707.

`test-functions` passes the complete official MVP `func`, `forward`, `fac`,
`unwind`, `func_ptrs`, and `stack` files across every generated module: 145
returns, 38 validation failures, 16 malformed-text rejections, and 14 runtime
traps. This covers recursion, forward calls, function/table index validation,
deep stack use, and trap unwinding. The cumulative official assertion total is
7,920.

`test-globals` passes the complete official MVP `globals` file: 45 returns, 23
validation failures, four malformed-binary rejections, and one runtime trap.
Mutable cells, immutable values, initialization, exports, and global index/type
validation are covered. The cumulative official assertion total is 7,993.

`test-memory-instructions` passes every assertion in the official MVP
`memory_grow`, `memory_redundancy`, `load`, `store`, `address`, `align`, and
`memory_trap` files, plus the complete `memory` file: 430 returns, 157
validation failures, 67 malformed-module rejections, and 206 runtime traps.
The state-reset actions in
`memory_redundancy` execute in source order in the same module instance. The
cumulative official assertion total is 8,853.

`test-types` passes the complete official MVP `type` file: two validation
failures and two malformed-text rejections. It also compiles the file's valid
type-declaration module. The cumulative official assertion total is 8,857.

`test-data-segments` passes the complete official MVP `data` file: 14
instantiation failures and six validation failures, plus all 25 valid module
instantiations. Constant offsets and imported immutable-i32-global offsets both
initialize local and imported memories before start execution. The cumulative
official assertion total is 8,877.

`test-elements` passes the complete official MVP `elem` file: 12 returns, 12
instantiation failures, six validation failures, and one runtime trap. Runtime
table slots store typed native function references, so element segments from
separately compiled and registered WASM modules can overwrite a shared table and
be called by the exporting module. The cumulative official assertion total is
8,908.

`test-imports` currently covers registered-module functions and the host global,
table, and memory action portions of the official MVP `imports` file. A
separately compiled module imports eight functions from another WASM module plus
the official `spectest` host functions. The harness passes 21 returns, eight
runtime traps, all seven binary validation failures, and all 57 unlinkable
assertions. Unused function imports are resolved eagerly, and their complete
structural signatures are checked during instantiation. All 30 additional valid
module commands instantiate, and all 16
malformed text assertions are rejected. This completes all 109 assertions and
every module command in the pinned official MVP `imports` file. The cumulative
official assertion total is 9,017.

`test-linking` currently covers the registered function, global, table, and
memory chains in the official MVP `linking` file. Independently compiled modules
import, call, mutate, and re-export shared resources, including an export name
containing a space. The harness preserves action order within each chain and
passes all 62 returns, all 19 traps, the trapped-start instantiation, and all 12
unlinkable assertions. A Coil-native recoverable trap boundary retains imported
memory and table mutations when a start function traps. This completes all 94
assertions and every module command in the pinned official MVP `linking` file.
The cumulative official assertion total is 9,111.

`test-encoding` covers the complete pinned MVP `binary-leb128`, `binary`,
`custom`, `token`, four UTF-8, `comments`, and `inline-module` files. It passes
all 835 malformed assertions and instantiates all 49 valid module commands.
Custom sections validate their name envelope even though their payload is
semantically ignored, and all binary names use strict Unicode scalar-value
UTF-8 validation. The cumulative official assertion total is 9,946.

`test-exports` passes the complete pinned MVP `exports` file: six returns, 22
validation failures, and all 54 valid module commands. Export names are compared
as validated UTF-8 byte strings, so duplicate names are rejected across every
external kind. The cumulative official assertion total is 9,974.

`test-wat` exercises the Coil-native text reader directly, including named
parameters, named `local.get`, signed integer constants, floating constants, and
all four MVP scalar result types. Flat, folded, and mixed folded/flat numeric
instruction forms are covered, along with named/numbered mutable parameters and
locals through `local.get`, `local.set`, and `local.tee`. It does not invoke WABT
or another converter.

An individual exported integer function can be checked through the same reader
entry path:

```sh
coil run module.wasm --use experiments.wasm.lang -- \
  --assert-i32 add 42 20 22
```

The harness also builds WABT 1.0.12 at pinned commit
`cf261f2bd561297e0da7008ddde8c09ba5ea35a2`. This is the last converter release
that accepts the MVP suite's historical canonical/arithmetic NaN assertions;
modern WABT rejects that syntax. WABT is test tooling only. Production decoding,
validation, compilation, and execution remain Coil-native.
