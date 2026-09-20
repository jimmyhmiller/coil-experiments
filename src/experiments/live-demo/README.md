# Bouncing balls, live

The heap-inspector's bouncing-ball demo as an ordinary program made live by
two manifest lines:

```toml
[dependencies]
live = { path = "../live" }

[metaprograms]
use = ["experiments.live.enable"]
```

```sh
coil build && ./build/release/live-demo
```

`balls.coil` is the program. While it runs, every save of the file is diffed
against what the program runs, and exactly the changed definitions are
applied on the next frame as one transaction. The balls keep their places and
speeds, including across changes to the structs that hold them. An edit that
does not check, or that changes a struct without saying how to carry the
running values over, is rejected, and the program keeps running on its
previous version.

After a save, run `coil check` (or read `.coil-live/STATUS.md`). It exits 0
when the running program is running the file, and otherwise reports, at the
forms concerned, what it did instead.

`window.coil` (the renderer) is not live: an edit to it takes a restart, and
`coil check` says so.

## A tour

Each step is a plain edit to `balls.coil`.

1. **Change a function.** `(defn radius [(p Particle)] (-> i64) 20)`. The balls grow.

2. **Add fields with defaults, and use them.** Change `Particle` and `tint`:

   ```coil
   (defstruct Particle
     [(x i64) (y i64) (vx i64) (vy i64)
      (hue i64 20) (visible bool true)])

   (defn tint [(p Particle)] (-> i64)
     (if (.visible p) (+ (.hue p) (/ (.x p) 3)) 0))
   ```

   Every ball in the running world gains the new fields at their defaults,
   and each color now follows its position.

3. **Change a field's type.** Make `visible` a sum:

   ```coil
   (defsum Visibility (Hidden) (Visible))
   (defstruct Particle
     [(x i64) (y i64) (vx i64) (vy i64)
      (hue i64 20) (visible Visibility)])
   ```

   The program keeps running unchanged. `coil check` fails at
   `defstruct Particle`: the running balls hold a `bool` there, and nothing
   says what it becomes.

4. **Say how.** Give the field a default for new balls, add a migration next
   to the struct for the running ones, and bring `tint` and `advance` up to
   date. One save applies it all:

   ```coil
   (defstruct Particle
     [(x i64) (y i64) (vx i64) (vy i64)
      (hue i64 20) (visible Visibility (Visible))])

   (migrate Particle visible old
     (if old (Visible) (Hidden)))

   (defn tint [(p Particle)] (-> i64)
     (match (.visible p)
       (Hidden [] 0)
       (Visible [] (+ (.hue p) (/ (.x p) 3)))))
   ```

   In `advance`, build the result with `:hue (.hue p) :visible (.visible p)`.
   The migration can stay in the file; once applied it is never sent again.

5. **Draw by kind.** Balls right of center become rings:

   ```coil
   (defsum Kind (Dot) (Ring))
   (defn kind-of [(p Particle)] (-> Kind)
     (if (> (.x p) 320) (Ring) (Dot)))
   (defn kind-code [(p Particle)] (-> i64)
     (match (kind-of p) (Dot [] 0) (Ring [] 1)))
   ```

6. **Break it.** Add `(Bar)` to `Kind`, and have `kind-of` return it past
   x = 430, without touching `kind-code`. The match is no longer exhaustive,
   so the edit is rejected, and `coil check` points at `defn kind-code`.

7. **Repair.** Give `kind-code` its `(Bar [] 2)` arm. The pending change goes
   through, and bars appear.
