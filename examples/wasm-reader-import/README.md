# WASM reader import proof of concept

This project maps `.wat` files to `experiments.wasm.reader` in `Coil.toml`.
`main.coil` imports `math.wat` through the normal Coil module system and calls
its typed `add` export as `math/add`.

Run it from this directory:

```sh
coil run
echo $?
```

An exit status of zero means the imported WebAssembly function returned `42`.
The same setup works for binary modules by changing the reader key to `.wasm`
and pointing the module entry at a `.wasm` file.
