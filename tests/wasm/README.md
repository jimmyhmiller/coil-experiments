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
