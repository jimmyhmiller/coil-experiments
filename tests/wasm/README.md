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
```

`test-integers` compiles each official `i32` and `i64` module through the reader
and executes all homogeneous, single-result integer `assert_return` commands in
one generated Coil entry point per module. It currently covers 350 `i32` and 205
`i64` assertions. This is a semantic test—not merely a module compile check.

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
