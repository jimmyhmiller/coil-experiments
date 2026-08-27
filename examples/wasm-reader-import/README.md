# WASM reader import proof of concept

This project maps `.wat` files to `experiments.wasm.reader` in `Coil.toml`.
`main.coil` imports `checksum.wat` through the normal Coil module system and
calls its typed `checksum` export. The WebAssembly function computes a rolling
hash of the ASCII bytes for `COIL`, using four typed parameters and a mutable
WASM local.

Run it from this directory:

```sh
coil run
```

It prints:

```text
WASM checksum for COIL: 2074255
```

An exit status of zero also verifies the result.
The same setup works for binary modules by changing the reader key to `.wasm`
and pointing the module entry at a `.wasm` file.
