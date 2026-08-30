# Coil GPU UI

An experimental, GPUI-inspired macOS UI framework implemented entirely in Coil.
It talks directly to the Objective-C runtime, AppKit, QuartzCore, and Metal. There
is no C, Objective-C, Swift, Rust, Python, wrapper library, or generated binding
layer in the runtime path.

## What works

- Reusable multi-window hosts own independent AppKit windows, views, retained
  scenes, triple-buffered `CAMetalLayer` renderers, display clocks, scale/resize
  state, visibility, and deterministic teardown. Specialized views can be
  injected for IME and accessibility. The demo presents an independently
  animated second GPU window, and lifecycle tests prove scene/render-target
  isolation and safe destruction in either order.
- CoreVideo display-link pacing with coalesced refresh ticks, bounded recovery
  from display reconfiguration, and occlusion-aware suspension of scene rebuilds
  and Metal submission.
- Coil-native animations sampled from monotonic `CACurrentMediaTime`: delayed and
  finite/infinite timelines, repeat/autoreverse cycles, arbitrary CSS cubic
  Bézier easing, and redirectable mass/stiffness/damping springs with bounded
  120 Hz integration substeps. The demo continuously rotates its retained SVG
  by changing only the composed GPU affine transform.
- Reusable deferred scenes rebase and append primitive, vector, texture, and
  hitbox storage after the ordinary tree, preserving top-layer paint and input
  order without per-frame allocation. Anchored popovers flip across viewport
  edges, clamp oversized content, support modal outside-click dismissal, wrap
  keyboard selection, and accept pointer-selected menu rows. The demo attaches
  a deferred GPU menu to its transformed SVG icon.
- Runtime-compiled Metal vertex and fragment shaders.
- Instanced draw runs for adjacent box primitives, interleaved with ordered
  vector-path draws without changing scene submission order.
- Triple-buffered, power-of-two-growing shared `MTLBuffer` uploads; large scenes
  do not rely on Metal's small inline-byte path and are never truncated.
- GPU-expanded quads, antialiased rounded rectangles, borders, and alpha blending.
- Nested GPUI-style opacity groups multiply and restore scene state. One scalar is
  recorded per primitive, path, glyph, or image and applied in its Metal fragment
  shader, preserving source colors and avoiding per-channel CPU rewrites.
- Composable translate/scale/rotate affine transforms applied on the GPU to solid,
  gradient, shadow, text, and image geometry; pointer hit testing uses the exact
  inverse transform and rejects singular transforms.
- Rounded two-stop linear gradients at arbitrary CSS-compatible angles, mixed
  with solid primitives in exact scene order inside the same instanced draw.
- GPUI-compatible diagonal slash background patterns with configurable color,
  line width, transparent gap, and rounded outer bounds. Stripe coverage is
  analytic in the existing Metal paint fragment, so patterns require neither
  texture allocation nor extra draw pipelines.
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
- Allocation-free retained damage snapshots hash ordered primitive, shadow,
  glyph/image, path, and path-vertex records. Identical transient rebuilds submit
  nothing; paint-only changes, movement, insertion, and removal invalidate the
  exact old/new union. A private, resize-aware Metal backing texture preserves
  unchanged pixels, while a device-pixel scissor clears and replays only records
  intersecting damage. A framebuffer-only drawable is presented with one
  fullscreen GPU sample, retaining the layer's optimal allocation mode.
- Adaptive center-parameterized elliptical arcs with positive or negative sweeps,
  full-circle support, and the same caller-controlled geometric tolerance.
- SVG endpoint-parameterized elliptical arcs with x-axis rotation, radii
  correction, large-arc and sweep flags, exact endpoints, and tolerance-derived
  subdivision. Degenerate SVG radii correctly fall back to a straight segment.
- Coil-native SVG path-data parsing for every absolute and relative command
  family (`M/L/H/V/C/S/Q/T/A/Z`), implicit repetitions, compact signs, decimals,
  exponents, smooth-control reflection, and multiple subpaths. `SvgVector`
  validates and tessellates filled contours once, retains the meshes, and paints
  aspect-preserving instances through the ordered Metal path pipeline. The demo
  uses this component for its cyan lightning icon.
- Batched analytic rounded-rectangle shadows with GPU-computed soft falloff,
  configurable offset, blur sigma, spread, radius, color, and scene clipping.
- Native Unicode line shaping through CoreText `CTLine`/`CTRun`, preserving shaped
  positions, advances, and source cluster indices. Individual glyph rasters are
  cached by font, glyph ID, and 4x2 subpixel variant, then colored and composited
  as ordered Metal atlas sprites.
- Width-dependent single-line end, start, and middle truncation copies complete
  shaped glyphs and inserts a cached Unicode ellipsis while preserving the
  requested portions of the line. Each result owns its glyph list and leaves the
  source shape immutable, so transient zero-width layout probes cannot make later
  wider renders permanently collapse to an ellipsis. Multi-line clamps ellipsize
  the final visible line and retain logical mapping through hidden paragraph text.
- Bounded shared text-atlas pages with padded shelf allocation, normalized UV
  regions, explicit overflow, borrowed label handles, and retained per-glyph cache
  entries. Whole-label and shaped-glyph sprites share the same Metal batching path.
- Native ImageIO decoding into owned BGRA Metal textures, with linear sampling,
  tint/opacity, scene clipping, and explicit GPU-resource teardown.
- GPUI-style image object fitting: `fill` stretches to the destination, `contain`
  centers aspect-preserving geometry, and `cover` retains the destination quad
  while cropping normalized source UVs. An optional dedicated Metal fragment
  pipeline converts sampled color to luminance on the GPU; grayscale images remain
  batchable by texture and mode with no CPU pixel rewrite.
- Fitted images support a clamped corner radius carried in the shared sprite ABI.
  Color and grayscale fragment pipelines compute antialiased rounded coverage from
  local quad coordinates; text sprites keep radius zero and share the same upload
  and batching machinery without an additional mask texture.
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
  observation queues, generation-safe subscription cancellation, and optional
  direct callbacks. Notification dispatch snapshots callbacks in registration-slot
  order, so callbacks may safely subscribe, unsubscribe, or grow the hub without
  invalidating the active scan. The demo's
  application state lives in a retained entity rather than a frame-local value.
- GPUI-style thread-confined `Entity<T>` and `WeakEntity<T>` handles backed by an
  allocator-aware reference-counted arena. Strong handles clone automatically,
  values are destroyed exactly when their final strong handle drops, weak handles
  do not extend value lifetime, upgrades validate the slot generation, and entity
  handles can safely outlive the map that created them.
- Render-time reactive dependency scopes with stable generation-checked consumer
  IDs. Entity reads deduplicate within a capture, dependencies no longer read by a
  later capture are pruned, explicit state notifications enqueue each affected
  consumer once, and unregistered consumer slots cannot inherit stale edges. The
  demo scene records its retained application-state dependency on every rebuild.
- Uniform and variable-height virtual lists with retained pixel offsets, bounded
  overscan, exact visible ranges, viewport clipping, wheel input, and stable GPU
  scrollbars. Variable lists use a Fenwick prefix-sum index for logarithmic
  measurement updates and pixel-offset lookup, with scroll-anchor preservation.
- The demo's scroll view has 100,000 heterogeneously sized logical rows but
  measures and constructs only visible rows plus three-row overscan each frame.
- Interactive buttons, checkbox, slider, progress, divider, panel, single-line text
  field, and retained multiline text-area components. The editors own NUL-terminated
  UTF-8 buffers and support insertion, selection replacement, code-point-safe
  deletion/navigation, shaped pointer hit-testing, and GPU-rendered selection and
  caret geometry. The text area adds width-constrained wrapping, explicit newlines,
  preferred-column vertical movement, selection across line breaks, and reshaping
  only when text or available width changes.
- Native `NSTextInputClient` composition routes insertion, marked ranges, newline,
  horizontal and vertical selection movement into the Coil editors. Candidate
  rectangles are converted to Cocoa screen coordinates, and screen-point character
  queries map back through retained multiline layout with UTF-8/UTF-16 conversion.
- Retained accessibility nodes backed by Coil-defined `NSAccessibilityElement`
  subclasses. Components expose native roles, labels, stable identifiers, values,
  ranges, enabled/focused state, screen-space bounds, change notifications, and
  press/increment/decrement actions that return through the Coil action router.
- GPU text labels integrated with the reusable scene and demo components.
- Mouse hover, press, release, checkbox toggling, slider dragging, plus keyboard
  activation and arrow-key slider adjustment.
- Owned UTF-8 clipboard items through `NSPasteboard`, with native Copy/Cut/Paste/
  Select-All responder commands. External text and file-URL drags enter through
  Coil-defined AppKit callbacks and update a reusable GPU-painted drop target.
- A byte-budgeted GPU image asset cache with owned source paths, deduplicated
  ImageIO loads, generation-checked stable IDs, explicit invalidation, frame pins,
  and least-recently-used eviction. A texture referenced by the current frame
  cannot be evicted; stale IDs are rejected when an evicted slot is reused.
- A GPU-painted scene inspector toggled with Command-I. It uses the same inverse
  affine and clip semantics as event dispatch, picks the topmost hitbox under the
  pointer, cycles through occluded candidates with the scroll wheel, reports
  hierarchy depth and scene counts, and overlays selected and parent bounds without
  introducing native inspection views.
- A Coil-native UI scheduler with generation-checked cancellable handles,
  owner-thread foreground and monotonic timer queues, and pthread-backed background
  work on a bounded reusable pool (four workers by default, configurable at
  construction). A mutex/condition FIFO feeds heap-stable control blocks to the
  pool; cross-thread result state is atomic, workers receive cooperative
  cancellation, and pool threads are joined before synchronization or job storage
  is released. Completion publication signals the frame
  semaphore, waking both active display pacing and the occluded fallback without
  exposing UI state across threads. The demo computes a checksum off-thread and
  paints its owner-thread completion as a GPU status badge.
- Structured task scopes group foreground, timed, and background work under one
  lifecycle. They prune completed generation handles, reject additions after
  closure, and cooperatively cancel all remaining jobs before releasing their own
  storage. The demo owns its background checksum through such a scope.
- Headless geometry, flex, clipping, focus/actions, scene ordering, component
  batching, scheduler lifecycle, ABI, and allocation-reuse tests (81 total).

## Architecture

```text
retained application state
        |
        v
foreground/timer queue <- joined background Coil tasks
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
avoiding steady-state list allocation. A paint primitive is 112 bytes, including its
six-float affine transform and GPU opacity scalar. Ordinary shapes and
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

The release scene benchmark rebuilds 1,049 paint primitives, emits 99 retained
paragraph glyph sprites, and advances a 100,000-row virtual list. On the development
Apple Silicon machine it measured **6,964 ns/frame** across 5,000 frames (median of
three consecutive runs). A same-session checkout immediately before nested opacity
measured 6,611 ns/frame, making the cost of the additional GPU record state explicit.
This measures
Coil scene construction, retained-text recording, and visible-range calculation—not
GPU presentation or display latency. The benchmark is checked in as `bench.coil` so
results remain reproducible and comparable.

The variable-height benchmark interleaves measurement replacement and inverse-prefix
lookup across one million rows. It measured **164 ns per update-plus-lookup** across
100,000 operations. Initial tree construction is excluded; the timed path covers the
steady-state work performed as rows are measured during scrolling.

Text rasterization is cached rather than repeated each frame. CoreText produces glyph
runs with positions, advances, and source cluster indices; each font/glyph/subpixel
variant is rasterized once into an application-owned, explicitly bounded atlas page.
Repeated shaping reuses those entries, and compatible glyph and label sprites remain
one instanced Metal run. Whole-label caching remains available for static labels.

Image fitting is resolved before recording the sprite. `contain` changes quad bounds;
`cover` keeps the component bounds and records the centered visible UV fraction. This
avoids oversized quads and redundant clip pushes. Color and grayscale use separate
Metal pipelines, while the existing run builder keeps adjacent records batched only
when texture and mode are compatible. Each sprite is 112 bytes after adding the
clamped image radius and explicit ABI padding.

Retained paragraphs use CoreText's Unicode line breaker with explicit wrap width,
line height, and optional line clamp. Each visual line owns byte-accurate UTF-8 source
ranges and a shaped GPU line, enabling point-to-index and index-to-position mapping
across wrapping, emoji, and explicit newlines. Rebuilding an equivalent paragraph
reuses semantic font/glyph/subpixel atlas keys rather than duplicating font objects.

Editable text is integrated with AppKit without a native wrapper. Coil dynamically
registers an `NSView` subclass implementing `NSTextInputClient`, translates UTF-16
AppKit ranges to the field's UTF-8 byte offsets, and handles marked-text updates,
commits, selection ranges, commands, and candidate-window positioning. Selection,
marked-text decoration, and the caret are painted through the same GPU scene.

Image assets enter through a Coil-owned cache rather than component-local texture
ownership. `image-asset-cache-begin-frame!` releases the previous frame's pins;
painting pins each referenced texture for the new frame. Loads with the same path
reuse one Metal texture, while budget pressure evicts only unpinned least-recently-
used entries. Asset generations make cached handles safe across slot recycling.

Background work does not create one operating-system thread per task. Scheduler
construction starts a fixed worker set; tasks enter a condition-variable FIFO and
reuse those threads. Result and cancellation publication use sequentially consistent
atomics, while queue ownership stays under one mutex. Polling reclaims a completed
block only after the worker's final `done` store. Teardown first marks every live
block cancelled, then drains queued work, joins all workers, and finally destroys
the queue and its synchronization objects.

## Capability roadmap

The current milestone proves the complete Coil-to-Metal path and a real component
application. GPUI parity still requires substantial systems, notably:

- grapheme-aware navigation and richer shaped-layout
  caching, and atlas-page eviction (editable selection/caret measurement,
  UTF-8/CoreText cluster conversion, glyph-run extraction, subpixel glyph caching,
  bounded atlas allocation, and GPU mask composition work now);
- intrinsic text/image measurement (flex and constrained grid layout work);
- closed-path dash seam merging, full SVG XML/style/transform document loading,
  and non-simple/multi-contour hole fill rules (path-data parsing, retained vector
  components, adaptive quadratic/cubic
  curves and elliptical arcs, polygon
  fills, butt-cap/miter strokes, affine transforms, analytic shadows, linear
  gradients, general raster images, virtual scrolling, and nested rectangular
  GPU clipping work);
- keymap predicate expressions and source metadata, internal drag sources,
  multi-item external drops, richer text-area accessibility
  ranges, and accessibility text actions
  (hierarchical capture/target/bubble listeners with stop-propagation, focus
  traversal, and logical actions work);
- typed future values, worker-pool priority lanes and work stealing,
  non-image/remote asset sources,
  editable style inspection, and deterministic pixel/event UI tests;
- multi-page texture-atlas eviction and deeper GPU/CPU profiling.

These are explicit missing capabilities, not features claimed by the prototype.

## Research basis

- [GPUI README](https://github.com/zed-industries/zed/blob/main/crates/gpui/README.md)
- [GPUI element lifecycle](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/element.rs)
- [GPUI key dispatch](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/key_dispatch.rs)
- [GPUI keymap precedence and matching](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/keymap.rs)
- [GPUI retained entity map](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/app/entity_map.rs)
- [GPUI subscriptions](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/subscription.rs)
- [GPUI image element](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/elements/img.rs)
- [GPUI pattern example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/pattern.rs)
- [GPUI opacity example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/opacity.rs)
- [GPUI foreground/background executor](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/executor.rs)
- [GPUI text system](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/text_system.rs)
- [GPUI text-overflow styling](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/styled.rs)
- [Apple CoreText line API](https://developer.apple.com/documentation/coretext/ctline)
- [GPUI window, focus, and hitbox model](https://github.com/zed-industries/zed/blob/main/crates/gpui/src/window.rs)
- [GPUI list example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/list_example.rs)
- [GPUI responsive grid example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/grid_layout.rs)
- [GPUI painting example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/painting.rs)
- [GPUI SVG example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/svg/svg.rs)
- [GPUI animation example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/animation.rs)
- [GPUI popover and deferred-layer example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/popover.rs)
- [GPUI multiple-window example](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/window.rs)
- [GPUI entity transfer between windows](https://github.com/zed-industries/zed/blob/main/crates/gpui/examples/move_entity_between_windows.rs)
- [GPUI macOS Metal renderer](https://github.com/zed-industries/zed/blob/main/crates/gpui_macos/src/metal_renderer.rs)
- [Apple CAMetalLayer documentation](https://developer.apple.com/documentation/QuartzCore/CAMetalLayer)
- [Apple MTLRenderCommandEncoder documentation](https://developer.apple.com/documentation/metal/mtlrendercommandencoder)
- [Apple CTRun documentation](https://developer.apple.com/documentation/coretext/ctrun)
- [Apple ImageIO documentation](https://developer.apple.com/documentation/imageio)
