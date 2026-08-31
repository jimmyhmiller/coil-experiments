# Raylib imported from C source

The demo imports `experiments.raylib-demo.raylib` like an ordinary Coil module.
Its `.cmod` source anchor selects `[c.raylib]` in the workspace `Coil.toml`; the
C reader preprocesses and lowers Raylib's seven translation units in memory.
There is no generated `raylib.coil` to update or check in.

Run it directly from the repository root:

```sh
coil run src/apps/raylib-demo/main.coil
```

The pinned Raylib implementation is in `vendor/raylib`, so this command needs
no setup script, network access, generated source, or separate build step.

The generated library exports Raylib's original C names and explicit-layout
record types. C static initialization must run once before its API is used:

```coil
(import "experiments.raylib-demo.raylib" :as raylib)

(raylib/initialize-c-library)
(let [sky (load (raylib/Color :r 17 :g 34 :b 51 :a 255))]
  (raylib/ClearBackground sky))
```
