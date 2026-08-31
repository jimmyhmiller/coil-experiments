# Raylib imported from C source

The demo imports `experiments.raylib-demo.raylib` like an ordinary Coil module.
Its `.cmod` source anchor selects `[c.raylib]` in the workspace `Coil.toml`; the
C reader preprocesses and lowers Raylib's seven translation units in memory.
There is no generated `raylib.coil` to update or check in.

Run it from the repository root:

```sh
scripts/raylib-demo.sh
```

The generated library exports Raylib's original C names and explicit-layout
record types. C static initialization must run once before its API is used:

```coil
(import "experiments.raylib-demo.raylib" :as raylib)

(raylib/initialize-c-library)
(let [sky (load (raylib/Color :r 17 :g 34 :b 51 :a 255))]
  (raylib/ClearBackground sky))
```
