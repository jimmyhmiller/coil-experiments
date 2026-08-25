# WebAssembly conformance tests

The normative target is the official WebAssembly 1.0 core test suite from
`WebAssembly/spec`, tag `v1.0.0` (`d910f03bd6d6477656fc5070b5098e8f909305d3`).
That suite defines the MVP profile claimed by this reader. Proposal suites and
features incorporated in Wasm 2.0/3.0 are tracked separately and are not part of
the initial compliance denominator.

Focused decoder tests are ordinary Coil tests:

```sh
coil test tests/wasm/decoder_test.coil
```

Raw binaries use the standard reader-provider path:

```sh
coil run module.wasm --use experiments.wasm.lang
```

The conformance runner will fetch the pinned upstream suite into an ignored
cache, convert WAST scripts with `wast2json`, and execute every assertion against
the Coil implementation. WABT is test tooling only; production decoding,
validation, compilation, and execution remain Coil-native.

