# Coil GPU UI

An experimental, GPUI-inspired macOS UI framework implemented entirely in Coil.
It talks directly to the Objective-C runtime, AppKit, QuartzCore, and Metal. There
is no C, Objective-C, Swift, Rust, Python, wrapper library, or generated binding
layer in the runtime path.

## What works

- Native resizable AppKit window with a triple-buffered `CAMetalLayer`.
- Runtime-compiled Metal vertex and fragment shaders.
- Instanced draw runs for adjacent box primitives, interleaved with ordered
  vector-path draws without changing scene submission order.
- Triple-buffered, power-of-two-growing shared `MTLBuffer` uploads; large scenes
  do not rely on Metal's small inline-byte path and are never truncated.
- GPU-expanded quads, antialiased rounded rectangles, borders, and alpha blending.
- Composable translate/scale/rotate affine transforms applied on the GPU to solid,
  gradient, shadow, text, and image geometry; pointer hit testing uses the exact
  inverse transform and rejects singular transforms.
- Rounded two-stop linear gradients at arbitrary CSS-compatible angles, mixed
  with solid primitives in exact scene order inside the same instanced draw.
- Coil-native closed-polygon paths with simple-polygon validation and ear-clipped
  concave tessellation in either winding. Triangle lists are uploaded through the
  shared frame ring and filled by a clipped, affine Metal pipeline; invalid,
  degenerate, open, and self-intersecting paths fail atomically.
- Adaptive quadratic and cubic Bézier flattening with caller-controlled geometric
  tolerance, plus open/closed stroke tessellation with butt, square, or adaptively
  rounded caps and bounded miter joins. Stroke meshes reuse the ordered
  transformed/clipped Metal path pipeline.
- Explicit miter, bevel, and adaptively rounded joins. Segment quads remain
  independent and join wedges close the outer turn; over-limit miters fall back
  to bevel geometry instead of producing spikes or narrowed corners.
- Arbitrary alternating dash arrays with SVG-style odd-pattern repetition,
  positive or negative phase offsets, exact distance interpolation across
  polyline corners, and per-run configurable caps and joins.
- Exact tessellated path bounds retained in scene records; the renderer applies
  affine transforms and intersects nested clips plus the viewport before encoding,
  skipping fully invisible path draw calls without disturbing paint order.
- Unified transformed-bounds culling for ordinary boxes, gradients, text atlas
  sprites, and images. Invisible records split batches; remaining adjacent records
  still form maximal ordered instanced runs.
- Analytic shadow instances are filtered and compacted in scene order before
  upload, retaining a single instanced shadow draw with no invisible records.
- Allocation-free retained damage tracking unions consecutive transformed scene
  regions, correctly invalidating moved and removed content. Partial presentation
  awaits a persistent backing texture; rotating layer drawables are always fully drawn.
- Adaptive center-parameterized elliptical arcs with positive or negative sweeps,
  full-circle support, and the same caller-controlled geometric tolerance.
- Batched analytic rounded-rectangle shadows with GPU-computed soft falloff,
  configurable offset, blur sigma, spread, radius, color, and scene clipping.
- Native Unicode line shaping through CoreText `CTLine`/`CTRun`, preserving shaped
  positions, advances, and source cluster indices. Individual glyph rasters are
  cached by font, glyph ID, and 4x2 subpixel variant, then colored and composited
  as ordered Metal atlas sprites.
- Bounded shared text-atlas pages with padded shelf allocation, normalized UV
  regions, explicit overflow, borrowed label handles, and retained per-glyph cache
  entries. Whole-label and shaped-glyph sprites share the same Metal batching path.
- Native ImageIO decoding into owned BGRA Metal textures, with linear sampling,
  tint/opacity, scene clipping, and explicit GPU-resource teardown.
- Buffered, instanced texture sprites: adjacent text/image records sharing a
  texture and pipeline collapse into one draw without changing paint order.
- Reusable scene allocation across frames.
- Immediate element reconstruction over retained application/component state.
- Reusable flex row/column solving with basis, grow, weighted shrink, gaps,
  padding, main-axis justification, cross-axis alignment, and hard min/max clamps.
- Responsive grid solving with fixed and weighted fractional rows/columns,
  hard min/max tracks, iterative cap-and-redistribute behavior, gaps, padding,
  and row/column spanning placements.
- Nested clipping propagated to both GPU paint records and hitboxes.
- A separate reverse-painted hitbox list with stable component IDs; decorative
  paint no longer accidentally participates in input.
- Retained focus routing across transient scenes, disabled-control skipping,
  Tab/Shift-Tab traversal, and logical activate/decrement/increment actions.
- Hierarchical event paths with capture, target, and bubble phases; listener
  registration order is stable and an owned dispatch cursor supports immediate
  stop-propagation and default-action prevention as independent controls.
- Configurable keymaps with platform-independent modifiers, multi-stroke chords,
  global and stacked component contexts, deepest-context and latest-binding
  precedence, explicit disabled bindings, versioning, and failed-prefix retry.
- Typed retained entity stores with type/slot/generation identities, stale-handle
  rejection, slot reuse, deterministic destruction of owned values, ordered
  observation queues, and generation-safe subscription cancellation. The demo's
  application state lives in a retained entity rather than a frame-local value.
- Uniform and variable-height virtual lists with retained pixel offsets, bounded
  overscan, exact visible ranges, viewport clipping, wheel input, and stable GPU
  scrollbars. Variable lists use a Fenwick prefix-sum index for logarithmic
  measurement updates and pixel-offset lookup, with scroll-anchor preservation.
- The demo's scroll view has 100,000 heterogeneously sized logical rows but
  measures and constructs only visible rows plus three-row overscan each frame.
- Interactive buttons, checkbox, slider, progress, divider, panel, and single-line
  text-field components. The text field owns a NUL-terminated UTF-8 buffer, supports
  insertion, selection replacement, code-point-safe deletion/navigation, shaped
  pointer hit-testing, and GPU-rendered selection and caret geometry.
- GPU text labels integrated with the reusable scene and demo components.
- Mouse hover, press, release, checkbox toggling, slider dragging, plus keyboard
  activation and arrow-key slider adjustment.
- Headless geometry, flex, clipping, focus/actions, scene ordering, component
  batching, ABI, and allocation-reuse tests.

## Architecture

```text
retained application state
        |
        v
flex/grid layout -> component functions rebuild a transient Scene each frame
        |
        v
ordered box/path commands + clipped hitbox/focus list + texture-sprite list
        |
        v
triple-buffered shared MTLBuffer upload + instanced shape/texture runs + path triangles
        |
        v
affine vertex shaders expand/transform quads; fragments perform SDF paint

CoreText-backed shaping/rasterization -> bounded high-DPI atlas regions
ImageIO decode -> cached BGRA textures
        |
        v
Metal text/image pipelines apply per-scene tint, clipping, and alpha composition
```

This follows GPUI's hybrid model: long-lived state owns focus, component values,
layout buffers, GPU resources, and text caches, while the root
view produces a short-lived element tree every frame. GPUI's elements pass through
request-layout, prepaint, and paint. The Coil library mirrors those responsibilities
with `layout.coil`/`grid.coil`, clipped hitbox registration in `ui.coil`, retained routing in
`input.coil`, and batched GPU painting in `metal.coil`. Paint primitives and hitboxes
are intentionally independent.

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

Run the Coil-native release scene benchmark:

```sh
cd src/experiments/coil_gpui
/Users/jimmyhmiller/Documents/Code/projects/coil/build/bin/coil build bench.coil \
  -o build/release/coil-gpui-bench --release
./build/release/coil-gpui-bench
```

Benchmark the million-row variable-height index:

```sh
cd src/experiments/coil_gpui
/Users/jimmyhmiller/Documents/Code/projects/coil/build/bin/coil build \
  variable_scroll_bench.coil -o build/release/coil-gpui-variable-scroll-bench --release
./build/release/coil-gpui-variable-scroll-bench
```

## Performance contract

The scene retains shape, path, command, shadow, and texture-list allocations after `scene-clear!`,
avoiding steady-state list allocation. A paint primitive is 104 bytes, including its
six-float affine transform. Ordinary shapes and
analytic shadows use instanced commands. Ordinary shapes form maximal adjacent
instanced runs around ordered path commands. All geometry shares a three-slot buffer ring; each slot starts
at 64 KiB and doubles until the complete scene fits. The demo intentionally rebuilds
1,024 background instances per frame so the large-scene path remains exercised. The
layer uses three drawables and display synchronization. Per-frame autoreleased Cocoa
objects are drained every frame.

Texture sprites use the same growable triple-buffered frame storage as shapes;
there is no per-label `setVertexBytes` path or fixed inline upload ceiling. The
renderer scans the ordered sprite list into maximal adjacent runs by pipeline and
texture, issuing one instanced draw per run. This makes a future shared glyph atlas
translate directly into one draw for all adjacent labels on an atlas page.

The release scene benchmark rebuilds 1,049 paint primitives while advancing a
100,000-row virtual list. On the development Apple Silicon machine it measured
**5,790 ns/frame with affine payloads and ordered paint-command recording**, versus
1,840 ns/frame before transforms and ordering. This measures Coil scene construction and
visible-range calculation, not GPU presentation or display latency; the benchmark
is checked in as `bench.coil` so results remain reproducible and comparable.

The variable-height benchmark interleaves measurement replacement and inverse-prefix
lookup across one million rows. It measured **164 ns per update-plus-lookup** across
100,000 operations. Initial tree construction is excluded; the timed path covers the
steady-state work performed as rows are measured during scrolling.

Text rasterization is cached rather than repeated each frame. CoreText produces glyph
runs with positions, advances, and source cluster indices; each font/glyph/subpixel
variant is rasterized once into an application-owned, explicitly bounded atlas page.
Repeated shaping reuses those entries, and compatible glyph and label sprites remain
one instanced Metal run. Whole-label caching remains available for static labels.

Editable text is integrated with AppKit without a native wrapper. Coil dynamically
registers an `NSView` subclass implementing `NSTextInputClient`, translates UTF-16
AppKit ranges to the field's UTF-8 byte offsets, and handles marked-text updates,
commits, selection ranges, commands, and candidate-window positioning. Selection,
marked-text decoration, and the caret are painted through the same GPU scene.

## Capability roadmap

The current milestone proves the complete Coil-to-Metal path and a real component
application. GPUI parity still requires substantial systems, notably:

- grapheme-aware navigation, multiline wrapping, shaped-line caching, fallback-font
  cache key hardening, and atlas-page eviction (editable selection/caret measurement,
  UTF-8/CoreText cluster conversion, glyph-run extraction, subpixel glyph caching,
  bounded atlas allocation, and GPU mask composition work now);
- intrinsic text/image measurement (flex and constrained grid layout work);
- endpoint-parameterized SVG arcs, closed-path dash seam merging,
  SVG parsing, and non-simple/multi-contour fill rules (adaptive quadratic/cubic
  curves and elliptical arcs, polygon
  fills, butt-cap/miter strokes, affine transforms, analytic shadows, linear
  gradients, general raster images, virtual scrolling, and nested rectangular
  GPU clipping work);
- keymap predicate expressions and source metadata, richer multiline IME geometry,
  drag/drop, and accessibility
  (hierarchical capture/target/bubble listeners with stop-propagation, focus
  traversal, and logical actions work);
- weak/strong retained handles, dependency-tracked observation, async executor
  integration, assets, inspector support, deterministic UI tests, and multiple windows;
- damage tracking, frame pacing, occlusion handling, multi-page texture-atlas eviction,
  and GPU/CPU profiling.

These are explicit missing capabilities, not features claimed by the prototype.

## Research basis

- [GPUI README](https://github.com/zed-industries/zed/blob/main/crates/gpui/README.md)
- [GPUI element lifecycle](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/element.rs)
- [GPUI key dispatch](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/key_dispatch.rs)
- [GPUI keymap precedence and matching](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/keymap.rs)
- [GPUI retained entity map](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/app/entity_map.rs)
- [GPUI subscriptions](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/subscription.rs)
- [GPUI text system](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/text_system.rs)
- [Apple CoreText line API](https://developer.apple.com/documentation/coretext/ctline)
- [GPUI window, focus, and hitbox model](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/window.rs)
- [GPUI list example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/list_example.rs)
- [GPUI responsive grid example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/grid_layout.rs)
- [GPUI painting example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/painting.rs)
- [Apple CAMetalLayer documentation](https://developer.apple.com/documentation/QuartzCore/CAMetalLayer)
- [Apple MTLRenderCommandEncoder documentation](https://developer.apple.com/documentation/metal/mtlrendercommandencoder)
- [Apple CTRun documentation](https://developer.apple.com/documentation/coretext/ctrun)
- [Apple ImageIO documentation](https://developer.apple.com/documentation/imageio)
