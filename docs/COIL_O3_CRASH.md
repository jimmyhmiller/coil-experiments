# `coil build -O3` dies with SIGBUS on a large module

`-O0`, `-O1` and `-O2` are all fine. `-O3` bus-errors, in LLVM, on a Coil-spawned
codegen thread. Measured on `coil` at `/Users/jimmyhmiller/.cargo/bin/coil`,
macOS arm64.

## Reproduce

```sh
coil build doom-native.coil -O3 -o /tmp/doom --link-flag -lm
# Bus error: 10        (exit 138)

coil build doom-native.coil -O2 -o /tmp/doom --link-flag -lm
# wrote /tmp/doom      (exit 0)
```

`doom-native.coil` is in this directory: 2,261,446 bytes, one module, 2,466
functions. It is Doom Generic's 81 translation units lowered by the C frontend in
`src/dialects/c/`, which is why it is one big module — the frontend compiles a
whole program at once.

It is deterministic, and it is not new: the same file from before a week of
changes to the generator fails the same way.

## What it is

Stack exhaustion inside LLVM's ScalarEvolution. `backtrace.txt` has all 88 frames
the report captured; they are one cycle repeated until the stack runs out:

```
llvm::ScalarEvolution::getRangeRef
llvm::ScalarEvolution::StrengthenNoWrapFlags
llvm::ScalarEvolution::getMulExpr
llvm::ScalarEvolution::createSCEV
llvm::ScalarEvolution::createSCEVIter
llvm::ScalarEvolution::LoopGuards::collectFromBlock
llvm::ScalarEvolution::LoopGuards::collectFromPHI
llvm::ScalarEvolution::LoopGuards::collectFromPHI
llvm::ScalarEvolution::LoopGuards::collectFromBlock
llvm::ScalarEvolution::howFarToZero
llvm::ScalarEvolution::computeExitLimitFromICmp
llvm::ScalarEvolution::computeExitLimitFromCondImpl
llvm::ScalarEvolution::computeExitLimit
llvm::ScalarEvolution::computeBackedgeTakenCount
llvm::ScalarEvolution::getRangeRef            <-- and round again
```

`LoopGuards::collectFrom*` has no depth limit, so a loop whose exit condition
depends on a chain of guarded PHIs recurses as deep as the chain is long.

The exception says so directly:

```
EXC_BAD_ACCESS (SIGBUS)
KERN_PROTECTION_FAILURE at 0x000000017d5b3fd0
"Could not determine thread index for stack guard region"
```

That address is a stack guard page.

## Where the thread comes from

The bottom of the stack is yours:

```
libLLVM.dylib   LLVMTargetMachineEmitToFile
coil            main.llvm-partition-worker
libsystem_pthread.dylib  _pthread_start
```

So the optimiser runs on a thread Coil spawns, and that thread's stack size was
fixed when it was created. Raising the shell's limit does nothing, which is
consistent -- `ulimit -s 65520` (8x the default) still bus-errors:

```sh
sh -c 'ulimit -s 65520; coil build doom-native.coil -O3 -o /tmp/doom --link-flag -lm'
# Bus error: 10
```

## The likely fix

Give the partition workers a bigger stack. Rust's default for a spawned thread is
2 MiB, which is small for LLVM; LLVM's own tools run the optimiser on an 8 MiB
thread for exactly this reason (`llvm::CrashRecoveryContext::RunSafelyOnThread`
takes a `RequestedStackSize` and the drivers pass 8 MB).

```rust
std::thread::Builder::new()
    .name("llvm-partition-worker".into())
    .stack_size(16 * 1024 * 1024)
    .spawn(...)
```

That may only move the cliff rather than remove it, since the recursion is
unbounded, but it is the difference between "works on real programs" and
"doesn't".

## What triggers it

Whole-program inlining. Each of Doom's translation units lowered on its own and
built at `-O3` is fine -- I tried `p_map.c`, `p_enemy.c`, `r_bsp.c`,
`f_finale.c`, `r_draw.c`, `r_segs.c`, `p_setup.c` and `am_map.c`, and all of them
reach the linker. It takes the whole program in one module, where the inliner
builds functions with deeply nested loops, for SCEV to recurse far enough.

Worth knowing for the shape of the input: 8 of the 2,466 functions are lowered
through a control-flow graph and a dispatch loop, because C's `goto` cannot
always be written with structured control flow. Those are one big loop with
dozens of exits and a binary search over a state variable, so they carry far more
guarded PHIs than ordinary code, and they are the most likely thing on this side
to be pushing the recursion deep. They are `F_CastTicker`, `A_Look`, `A_Chase`,
`PTR_SlideTraverse`, `P_SlideMove`, `PTR_ShootTraverse`, `R_ClipSolidWallSegment`
and `R_AddLine`.
