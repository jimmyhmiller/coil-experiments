# WASM reader import proof of concept

This project compiles a real `no_std` Rust library to core WebAssembly, maps its
`.wasm` extension to `experiments.wasm.reader`, and imports the binary through
Coil's normal module system. The exported Rust function loops over four packed
ASCII bytes, classifies uppercase letters, vowels, and digits, and returns the
three counters in one `u32`.

Build the Rust binary and run Coil from this directory:

```sh
cd rust
RUSTFLAGS="-C target-cpu=mvp" cargo build --release --target wasm32-unknown-unknown
cd ..
coil run
```

It prints:

```text
Rust/WASM analysis of COIL: 262656 (4 uppercase, 2 vowels, 0 digits)
```

An exit status of zero also verifies the encoded result (`0x040200`). No WASI
runtime, JavaScript glue, Python implementation, or native Rust library is used
at runtime: Coil reads and compiles the generated `.wasm` file.
