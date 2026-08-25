#!/usr/bin/env python3
"""Compare optimized Coil builds with and without the safety metaprogram."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/tmp/coil-safety-bench")
SAFETY = "experiments.safety.safety"

WORKLOADS = {
    "arithmetic": {
        "source": "src/experiments/safety/bench/arithmetic.coil",
        "uses": [],
        "stdin": b"",
    },
    "bounds-random": {
        "source": "src/experiments/safety/bench/bounds_random.coil",
        "uses": [],
        "stdin": b"",
    },
    "dynamic-dispatch": {
        "source": "src/experiments/safety/bench/dynamic_dispatch.coil",
        "uses": [],
        "stdin": b"",
    },
    "brainfuck": {
        "source": "tests/brainfuck/benchmark.bf",
        "uses": ["experiments.brainfuck.lang"],
        "stdin": b"A" * 5_000_000 + b"\0",
    },
}


def command(workload: dict, safe: bool, output: Path) -> list[str]:
    cmd = [
        "coil",
        "build",
        workload["source"],
        "-o",
        str(output),
        "--release",
        "-O3",
        "--meta-opt=1",
    ]
    for namespace in workload["uses"]:
        cmd.extend(["--use", namespace])
    if safe:
        cmd.extend(["--use", SAFETY])
    return cmd


def elapsed_run(cmd: list[str], stdin: bytes = b"") -> tuple[float, bytes]:
    start = time.perf_counter()
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return time.perf_counter() - start, completed.stdout


def sample_compile(name: str, workload: dict, safe: bool, samples: int) -> list[float]:
    label = "safe" if safe else "base"
    output = OUT / f"{name}-{label}"
    values = []
    for _ in range(samples):
        elapsed, _ = elapsed_run(command(workload, safe, output))
        values.append(elapsed)
    return values


def sample_runtime(executable: Path, stdin: bytes, warmups: int, samples: int) -> tuple[list[float], bytes]:
    output: bytes | None = None
    for _ in range(warmups):
        _, output = elapsed_run([str(executable)], stdin)
    values = []
    for _ in range(samples):
        elapsed, current = elapsed_run([str(executable)], stdin)
        if output is None:
            output = current
        elif current != output:
            raise RuntimeError(f"nondeterministic output from {executable}")
        values.append(elapsed)
    return values, output if output is not None else b""


def summary(values: list[float]) -> dict[str, float]:
    return {
        "median_seconds": statistics.median(values),
        "min_seconds": min(values),
        "max_seconds": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-samples", type=int, default=5)
    parser.add_argument("--runtime-samples", type=int, default=9)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--workload", action="append", choices=sorted(WORKLOADS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    results = {
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "coil": subprocess.check_output(["coil", "--version"], text=True).strip(),
            "optimization": "--release -O3 --meta-opt=1",
        },
        "workloads": {},
    }

    selected = args.workload if args.workload else list(WORKLOADS)
    for name in selected:
        workload = WORKLOADS[name]
        base_compile = sample_compile(name, workload, False, args.compile_samples)
        safe_compile = sample_compile(name, workload, True, args.compile_samples)
        base_exe = OUT / f"{name}-base"
        safe_exe = OUT / f"{name}-safe"
        base_runtime, base_output = sample_runtime(base_exe, workload["stdin"], args.warmups, args.runtime_samples)
        safe_runtime, safe_output = sample_runtime(safe_exe, workload["stdin"], args.warmups, args.runtime_samples)
        if base_output != safe_output:
            raise RuntimeError(f"baseline and safety output differ for {name}")
        bc = summary(base_compile)
        sc = summary(safe_compile)
        br = summary(base_runtime)
        sr = summary(safe_runtime)
        results["workloads"][name] = {
            "compile": {"baseline": bc, "safety": sc, "ratio": sc["median_seconds"] / bc["median_seconds"]},
            "runtime": {"baseline": br, "safety": sr, "ratio": sr["median_seconds"] / br["median_seconds"]},
        }

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("workload             compile base  safety   ratio   runtime base  safety   ratio")
        for name, result in results["workloads"].items():
            c = result["compile"]
            r = result["runtime"]
            print(
                f"{name:20} {c['baseline']['median_seconds']:8.3f}s "
                f"{c['safety']['median_seconds']:7.3f}s {c['ratio']:6.2f}x "
                f"{r['baseline']['median_seconds']:10.3f}s "
                f"{r['safety']['median_seconds']:7.3f}s {r['ratio']:6.2f}x"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
