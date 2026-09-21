# Coil Snake (native GUI)

Snake, with the whole game living in Coil and a small SDL2 file doing nothing but
windows, keys, and pixels.

**The board wraps on all four edges.** Running off the left edge brings the head
back on the right, off the right edge brings it back on the left, off the top
brings it back at the bottom, and off the bottom brings it back at the top. No
edge ends the game. Running into the snake's own body still does.

Recovered from `coil-agent-harness` (`examples/snake-gui`, removed there in
`b92e60d`) so it can serve as a real GUI program to point probes at.

## Probe the key presses

The game knows nothing about probes. One dependency line in `Coil.toml` makes
`.probe` files readable, and `--use` turns one on:

    coil run --use snake.probes.keys          # play; watch the terminal you ran it from

```
key down                                  <- printed the moment it is pressed
key right
key up
key down
key left
key down
key down
key quit
── probe · 510µs · final ──              <- while playing: refreshed every second
key · count by name
  down   4
  right  1
  left   1
  quit   1
  up     1
call game-steer! · count by dx, dy
  0, 1   4
  1, 0   1
  0, -1  1
  -1, 0  1
input-lag · time                          <- key press to the tick that acted on it
  7 calls  total 95µs  avg 13µs  p50 ~13µs  p99 ~22µs  max 22µs
```

That is real output from the scripted run below, where the clock is simulated —
so the durations are tiny. In the real window a tick is 120ms, so expect input lag
anywhere up to that; a real session measured `call render` at about 4ms a frame.

`probes/keys.probe` is the whole thing: a `point` that names the key by calling an
ordinary Coil function (`probes/keynames.coil`), a `print`, two `count`s, a range
span from `enter apply-input` to the next `call game-step!`, and two `time`s.

As a machine-readable stream instead:

    coil run --use snake.probes.keys-json
    tail -f keys.jsonl                        # one JSON object per key press
    watch cat keys-stats.json                 # the aggregations, rewritten every 500ms

`scripted/` links the same Coil sources against a window shim whose key presses
come from a script and whose clock is simulated, so the probes can be checked with
no display: `scripted/check.sh`.

## Layout

| File | Role |
| --- | --- |
| `src/engine.coil` | **The authoritative engine.** Board size, movement, steering, wraparound, self-collision, eating, scoring, restart. No I/O. |
| `src/main.coil` | The playable loop: reads input codes, ticks the engine, asks the shim to draw what the engine reports. |
| `native/snake_window.c` | Presentation shim: SDL window, keyboard, clock, rectangles. Holds no board, no snake, and no rules. |
| `tests/engine_test.coil` | Behavioral tests against the engine, run headlessly. |
| `probes/` | Key-press probes (`keys.probe`, `keys-json.probe`) and the helper they call. Not part of the game. |
| `scripted/` | Test tooling: a display-free window shim + `check.sh` for the probes. |

The split is the point: because no rule lives in C, every rule is testable
without a display.

## Rules

- The snake advances one cell per 120 ms tick in its current direction.
- **Wraparound.** The new head position is folded onto the board with
  `wrap-index`, so `x = -1` becomes `x = 29`, `x = 30` becomes `x = 0`,
  `y = -1` becomes `y = 21`, and `y = 22` becomes `y = 0`. Crossing an edge is an
  ordinary move: score, length, and direction are unchanged, and the game
  continues.
- **Self-collision is terminal.** If the new head lands on a live body segment
  the game is over — including when it got there by wrapping across an edge. The
  tail cell is exempt while the snake is not growing, because that same step
  vacates it.
- Eating the food grows the snake by one, scores a point, and respawns food on a
  uniformly chosen free cell.
- Arrows or `WASD` steer; a reversal straight back onto the neck is ignored.
  `Space`/`Enter` restarts after a game over, `Esc` quits.
- The board is 30 × 22 cells; the snake starts three long in the middle heading
  right.

## Build, test, run

    coil check     # typecheck the project and compile the native shim
    coil test      # run the engine test suite (no window needed)
    coil build     # writes build/release/snake
    coil run       # build and play

Requires SDL2 (`brew install sdl2`); `Coil.toml` points at the Homebrew include
and library directories.

## Tests

`coil test` runs `tests/engine_test.coil` in-process-per-test with no window:

| Test | What it pins down |
| --- | --- |
| `wrap-left` | Head at `x = 0` moving left reappears at `x = 29`, same row, alive, same length and score. |
| `wrap-right` | Head at `x = 29` moving right reappears at `x = 0`, same row, alive. |
| `wrap-up` | Head at `y = 0` moving up reappears at `y = 21`, same column, alive. |
| `wrap-down` | Head at `y = 21` moving down reappears at `y = 0`, same column, alive. |
| `wrap-index-folds-both-ways` | The fold itself, on both edges of both axes. |
| `wrap-keeps-the-body-following` | The body trails the head correctly across an edge. |
| `wrapping-lap-returns-to-the-start` | A full 30-step lap comes home, still alive. |
| `wrap-eats-food-on-the-far-edge` | Wrapping onto food scores and grows. |
| `self-collision-ends-the-game` | Turning into a body segment is still terminal. |
| `self-collision-across-an-edge-ends-the-game` | Wrapping into your own body is terminal too. |
| `a-finished-game-does-not-move` | A finished game ignores further ticks. |
| `following-the-tail-is-allowed` | Entering the tail cell being vacated is legal. |
| `reset-starts-a-fresh-game` | Fresh length, score, position, and food off the snake. |
| `restart-after-game-over` | Restart clears the game-over state and moves again. |
| `eating-grows-and-scores` | Food grows the snake, scores, and respawns. |
| `steering-cannot-reverse-onto-the-neck` | Reversal is ignored; a legal turn is queued. |

Run one edge on its own with, for example:

    coil test tests/engine_test.coil --filter wrap-left

## Known issue

Project-wide `coil lint` currently fails with
`comptime: code-field-* expects a type symbol or instantiation (Gen …)`. This is
a compiler-side limitation, not a problem with this example: any project whose
struct has a fixed `(array T N)` field reproduces it, and `Game` stores its
segments in an `(array Cell 660)`. Per-file linting (`coil lint src/engine.coil`)
is clean, as are `coil check`, `coil test`, and `coil build`.
