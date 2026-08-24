#!/usr/bin/env python3
"""Differential gate for the native C frontend.

Each case is compiled twice -- once by Clang, once by the Coil pipeline in
src/dialects/c -- and both binaries are run. Clang is the oracle; it is never
part of the native build.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/c/native"


def run(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, **kwargs)


def reference(source: pathlib.Path, work: pathlib.Path) -> tuple[int, str]:
    binary = work / (source.stem + "-clang")
    built = run(["clang", "-std=c11", "-O0", "-w", str(source), "-o", str(binary)])
    if built.returncode:
        raise SystemExit(f"clang could not build {source.name}:\n{built.stderr}")
    got = run([str(binary)])
    return got.returncode, got.stdout


def system_includes() -> list[str]:
    """Where the target's headers live.

    A C compiler has to be told this; the driver takes -I like any other. The
    host toolchain is asked rather than guessed, so the gate keeps working when
    the SDK moves.
    """
    paths = []
    for command in (["xcrun", "--show-sdk-path"], ["clang", "-print-resource-dir"]):
        got = subprocess.run(command, capture_output=True, text=True)
        if got.returncode == 0:
            root = got.stdout.strip()
            paths.append(f"{root}/usr/include" if command[0] == "xcrun" else f"{root}/include")
    return [f"-I{p}" for p in paths]


def native(coil: str, source: pathlib.Path, work: pathlib.Path) -> tuple[int, str, str]:
    generated = work / (source.stem + ".coil")
    binary = work / (source.stem + "-coil")
    target = ROOT / "src/dialects/c/target"
    lowered = run([coil, "run", str(ROOT / "src/dialects/c/cc.coil"), "--",
                   "-o", str(generated), str(source),
                   "-include", str(target / "darwin-arm64.h"),
                   "-include", str(target / "builtins.h")] + system_includes())
    if lowered.returncode or not generated.exists():
        return -1, "", (lowered.stdout + lowered.stderr).strip()
    built = run([coil, "build", str(generated), "-O0", "-o", str(binary)])
    if built.returncode:
        return -1, "", (built.stdout + built.stderr).strip()
    got = run([str(binary)])
    return got.returncode, got.stdout, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=shutil.which("coil") or "coil")
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    sources = sorted(CASES.glob("*.c"))
    if args.only:
        sources = [s for s in sources if args.only in s.name]
    if not sources:
        raise SystemExit(f"no cases in {CASES}")

    passed = 0
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        for source in sources:
            want_code, want_out = reference(source, work)
            got_code, got_out, error = native(args.compiler, source, work)
            if error:
                failures.append((source.name, f"did not compile: {error.splitlines()[-1][:120]}"))
            elif (got_code, got_out) != (want_code, want_out):
                failures.append((source.name,
                                 f"clang exit={want_code} out={want_out!r} "
                                 f"native exit={got_code} out={got_out!r}"))
            else:
                passed += 1
                print(f"  {source.name}: matches clang")

    for name, detail in failures:
        print(f"  {name}: {detail}")
    print(f"\n{passed}/{len(sources)} cases match Clang")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
