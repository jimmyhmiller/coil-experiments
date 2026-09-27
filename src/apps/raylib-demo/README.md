# Raylib imported from C source

The demo imports `experiments.raylib` like an ordinary Coil module. That
module is the `raylib/` package, a `prebuilt = true` dependency whose entry,
`raylib/raylib_all.h`, includes Raylib's real public headers. The C reader uses
their declarations as the module's public interface and lowers Raylib's seven
implementation translation units from `[c.raylib_all]` in memory; Coil builds
the result once into `.coil/units/` and links it. There is no generated
`raylib.coil` to update or check in.

Everything needed to understand and configure the demo is in this directory:

- `main.coil` imports and uses Raylib.
- `raylib/Coil.toml` names the module (`module-name`), lists the implementation
  `.c` files, configures the C frontend, and declares the native libraries.
- `vendor/raylib` contains the complete pinned upstream Raylib source used by
  the demo.

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
(import "experiments.raylib" :as raylib)

(raylib/initialize-c-library)
(let [sky (load (raylib/Color :r 17 :g 34 :b 51 :a 255))]
  (raylib/ClearBackground sky))
```
