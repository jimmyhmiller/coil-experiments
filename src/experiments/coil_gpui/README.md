# Coil GPU UI

An experimental, GPUI-inspired macOS UI framework implemented entirely in Coil.
It talks directly to the Objective-C runtime, AppKit, QuartzCore, and Metal. There
is no C, Objective-C, Swift, Rust, Python, wrapper library, or generated binding
layer in the runtime path.

## What works

- Native resizable AppKit window with a triple-buffered `CAMetalLayer`.
- Runtime-compiled Metal vertex and fragment shaders.
- One instanced draw call per frame for every box primitive in the scene.
- GPU-expanded quads, antialiased rounded rectangles, borders, and alpha blending.
- Reusable scene allocation across frames.
- Immediate element reconstruction over retained application/component state.
- Reverse-order hit testing with stable component IDs.
- Interactive buttons, checkbox, slider, progress, divider, and panel components.
- Mouse hover, press, release, checkbox toggling, and slider dragging.
- Headless geometry, scene ordering, component batching, ABI, and allocation-reuse tests.

## Architecture

```text
retained application state
        |
        v
component functions rebuild a transient Scene each frame
        |
        v
flat, paint-ordered ArrayList<Primitive> (80-byte stable GPU ABI)
        |
        v
one setVertexBytes upload + one instanced Metal draw
        |
        v
vertex shader expands quads; fragment shader performs SDF shape rasterization
```

This follows GPUI's hybrid model: long-lived entities own state, while the root
view produces a short-lived element tree every frame. GPUI's elements pass through
request-layout, prepaint, and paint; this experiment currently collapses those into
component construction, explicit layout helpers, scene order, and a batched paint
pass. The split between `ui.coil` and `metal.coil` keeps layout, components, and hit
testing independently testable.

## Build and run

Use the current Coil checkout, not a stale installed compiler:

```sh
cd src/experiments/coil_gpui
mkdir -p build/release
/Users/jimmyhmiller/Documents/Code/projects/coil/build/bin/coil build --release
./build/release/coil-gpui-demo
```

For Metal API validation:

```sh
MTL_DEBUG_LAYER=1 ./build/release/coil-gpui-demo
```

Run the focused tests from the repository root:

```sh
/Users/jimmyhmiller/Documents/Code/projects/coil/build/bin/coil test --suite coil-gpui --jobs 4
```

## Performance contract

The scene retains its allocation after `scene-clear!`, avoiding steady-state heap
traffic. A primitive is 80 bytes and every primitive is rendered through a single
instanced command. Component count does not increase draw-call count. The layer uses
three drawables and display synchronization. Per-frame autoreleased Cocoa objects
are drained every frame.

The current backend uses `setVertexBytes`, which is excellent for small and medium
UI scenes but has an API size ceiling. The next renderer tier should maintain a ring
of shared `MTLBuffer`s, then split only scenes larger than a ring segment. That work
must preserve paint order and never silently truncate a scene.

## Capability roadmap

The current milestone proves the complete Coil-to-Metal path and a real component
application. GPUI parity still requires substantial systems, notably:

- glyph shaping and an atlas-backed GPU text renderer;
- flex/grid layout with intrinsic measurement;
- scroll views, clipping stacks, transforms, shadows, images, SVG, and paths;
- focus, keyboard dispatch, actions, keymaps, IME, drag/drop, and accessibility;
- retained entities, subscriptions, observation, async executor integration, assets,
  inspector support, deterministic UI tests, and multiple windows;
- damage tracking, frame pacing, occlusion handling, buffer rings, texture atlases,
  and GPU/CPU profiling.

These are explicit missing capabilities, not features claimed by the prototype.

## Research basis

- [GPUI README](https://github.com/zed-industries/zed/blob/main/crates/gpui/README.md)
- [GPUI element lifecycle](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/element.rs)
- [Apple CAMetalLayer documentation](https://developer.apple.com/documentation/QuartzCore/CAMetalLayer)
- [Apple MTLRenderCommandEncoder documentation](https://developer.apple.com/documentation/metal/mtlrendercommandencoder)
