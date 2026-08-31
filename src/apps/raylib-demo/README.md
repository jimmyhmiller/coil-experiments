# Raylib imported from C source

The demo imports `experiments.raylib-demo.raylib` like an ordinary Coil module.
That namespace maps to Raylib's real public header, `vendor/raylib/src/raylib.h`.
The C reader uses its declarations as the module's public interface and lowers
Raylib's seven implementation translation units from `[c.raylib]` in memory.
There is no generated `raylib.coil` to update or check in.

Everything needed to understand and configure the demo is in this directory:

- `main.coil` imports and uses Raylib.
- `Coil.toml` maps the import to `raylib.h`, lists the implementation `.c`
  files, configures the C frontend, and declares the native libraries.
- Raylib's pinned upstream source remains in the repository's shared
  `vendor/raylib` directory.

Run it as an ordinary standalone Coil project:

```sh
cd src/apps/raylib-demo
coil run
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
