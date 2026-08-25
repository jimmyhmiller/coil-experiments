# Safety metaprogram performance

Measured on 2026-08-24 on arm64 macOS 26.5.2 with Coil 0.1.0. Both variants
used `--release -O3 --meta-opt=1`; the safety variant additionally loaded
`experiments.safety.safety`. Times are wall-clock medians. Every baseline and
safety executable produced identical output.

| Workload | Compile baseline | Compile safety | Compile ratio | Runtime baseline | Runtime safety | Runtime ratio |
|---|---:|---:|---:|---:|---:|---:|
| Arithmetic, 200M iterations | 1.422 s | 3.284 s | 2.31× | 4.404 s | 7.336 s | 1.67× |
| Data-dependent array bounds, 100M iterations | 1.550 s | 3.210 s | 2.07× | 1.844 s | 2.555 s | 1.39× |
| Dynamic dispatch, 1M calls | 0.602 s | 0.903 s | 1.50× | 0.00334 s | 0.00458 s | 1.37× |
| Brainfuck tape, 5M input bytes with inner tape loop | 1.541 s | 2.061 s | 1.34× | 0.119 s | 0.129 s | 1.08× |

The arithmetic and data-dependent bounds rows used three compile samples, one
warmup, and five runtime samples. Dynamic dispatch used seven compile samples,
two warmups, and nine runtime samples. The corrected Brainfuck workload used
three compile samples, two warmups, and seven runtime samples.

## Workloads

- `bench/arithmetic.coil` isolates checked addition and multiplication in a
  200-million-iteration recurrence.
- `bench/bounds_random.coil` performs 100 million data-dependent accesses into a
  fixed 4,096-element array. The index cannot be proven from a simple induction
  variable.
- `bench/dynamic_dispatch.coil` calls through a `(dyn Value)` parameter one
  million times.
- `tests/brainfuck/benchmark.bf` is compiled through the actual Brainfuck reader.
  It processes five million nonzero bytes, repeatedly moving between tape cells.

The Brainfuck generator was adjusted to retain its `(array u8 30000)` pointer
type instead of erasing the bound to `ptr u8`. Its intentional byte wrapping is
also explicit. This is the representation a bounds-checked Zig implementation
would likewise preserve.

## Interpretation

The ordinary runtime cost is measurable: approximately 39% for deliberately
unpredictable array access and 67% for an arithmetic stress test. The Brainfuck
case costs approximately 8%, indicating that optimization can eliminate or
amortize much of the checking in structured generated code.

The initial dynamic-dispatch implementation called `dladdr` while validating the
vtable against loaded images at every dynamic boundary. It measured nearly 192
times slower than baseline. Safe Coil dynamic vtables are compiler-created
constants; forging one already requires `unsafe`, so the loaded-image lookup did
not strengthen safe-code guarantees. Replacing it with null/alignment validation
reduced one million calls from 0.793 seconds to 0.00458 seconds. Baseline is
0.00334 seconds, leaving approximately 1.24 nanoseconds or 37% overhead per call
in this dispatch-only microbenchmark.

Compilation currently costs roughly 1.3× for the smaller generated/dynamic
programs and 2.1–2.3× for the arithmetic and bounds-heavy Coil sources. This is
the cost of compiling and executing the semantic transform plus compiling the
larger rewritten program.

## Reproduction

From the workspace root:

```sh
python3 scripts/safety-bench.py --compile-samples 5 --runtime-samples 9 --warmups 2
```

Use `--workload NAME` to select one or more workloads and `--json` for complete
sample summaries.
