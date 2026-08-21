#!/usr/bin/env python3
"""Native C-reader correctness corpus and performance gate."""
import pathlib
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIALECT = "experiments.c.lang"
SMALL_CASES = sorted((ROOT / "tests/c").glob("*.c"))
PROJECTS = ROOT / "tests/c/projects"


def invoke(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def result(command):
    process = invoke(command, capture_output=True)
    return process.returncode, process.stdout, process.stderr


def build_pair(source, directory, stem):
    clang = directory / f"{stem}-clang"
    coil = directory / f"{stem}-coil"
    invoke(["clang", "-std=c11", "-O3", str(source), "-o", clang])
    invoke([shutil.which("coil"), "build", str(source), "--use", DIALECT,
            "-O3", "-o", coil], capture_output=True)
    return clang, coil


def median_runtime(command, samples=7):
    for _ in range(2):
        invoke(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elapsed = []
    for _ in range(samples):
        started = time.perf_counter()
        invoke(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed.append(time.perf_counter() - started)
    return statistics.median(elapsed)


if not shutil.which("coil"):
    raise SystemExit("coil is required")

with tempfile.TemporaryDirectory() as temporary:
    temporary = pathlib.Path(temporary)

    for source in SMALL_CASES:
        generated = invoke(
            ["python3", str(ROOT / "src/dialects/c/c_ast_to_coil.py"), str(source)],
            capture_output=True, text=True).stdout
        assert "(module c_program)" in generated and "ast-dump" not in generated
        clang, coil = build_pair(source, temporary, source.stem)
        assert result([clang]) == result([coil]), f"{source.name}: output differs"
        print(f"{source.name}: native output matches clang")

    cjson_clang, cjson_coil = build_pair(
        PROJECTS / "cjson/program.c", temporary, "cjson")
    assert result([cjson_clang]) == result([cjson_coil])
    print("cJSON (3,206 lines): native output matches clang")

    lz4_clang, lz4_coil = build_pair(
        PROJECTS / "lz4/program.c", temporary, "lz4")
    assert result([lz4_clang]) == result([lz4_coil])
    lz4_c_time = median_runtime([lz4_clang])
    lz4_coil_time = median_runtime([lz4_coil])
    lz4_ratio = lz4_coil_time / lz4_c_time
    print(f"LZ4 (2,848 lines): output matches; Coil/clang time {lz4_ratio:.2f}x")

    clox_clang, clox_coil = build_pair(
        PROJECTS / "clox/program.c", temporary, "clox")
    invoke(["python3", str(ROOT / "src/apps/clox/run-tests.py"), str(clox_coil)])
    benchmark = PROJECTS / "clox/benchmark.lox"
    assert result([clox_clang, benchmark])[1].splitlines()[0] == b"true"
    assert result([clox_coil, benchmark])[1].splitlines()[0] == b"true"
    clox_c_time = median_runtime([clox_clang, benchmark], samples=5)
    clox_coil_time = median_runtime([clox_coil, benchmark], samples=5)
    clox_ratio = clox_coil_time / clox_c_time
    print(f"clox (4,979 lines): 246 tests pass; Coil/clang time {clox_ratio:.2f}x")

    # Both are sustained, warmed application workloads, not process-startup timing.
    if lz4_ratio > 1.15 or clox_ratio > 1.15:
        raise SystemExit("C native performance exceeded the 15% margin")
