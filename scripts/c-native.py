#!/usr/bin/env python3
"""Differential gate for the C frontend written in Coil.

Each case is compiled twice -- once by Clang, once by src/dialects/c/cc.coil --
and both binaries are run. The two must agree on exit status and output. Clang is
the oracle here and nothing else: it takes no part in the build being tested.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/c/native"
TARGET = ROOT / "src/dialects/c/target"

# Whole programs of more than one translation unit, which is where linkage,
# `static` privacy, and shared headers are actually exercised.
PROJECTS = [
    # Two units that share a header and nothing else: cross-unit calls, globals
    # with one definition and several declarations, same-named `static`s that
    # must stay apart, a function pointer handed across, a variadic function
    # defined in one unit and called from the other, and constructors and
    # destructors around `main`.
    ("multi-unit", [ROOT / "tests/c/multi-unit/alpha.c",
                    ROOT / "tests/c/multi-unit/beta.c"],
     ["-I" + str(ROOT / "tests/c/multi-unit"), "-D_FORTIFY_SOURCE=0"]),
    ("cjson", [ROOT / "tests/c/projects/cjson/cJSON.c",
               ROOT / "tests/c/projects/cjson/separate-program.c"],
     # Apple's headers redirect the string functions to _FORTIFY_SOURCE builtins
     # this frontend does not implement; cJSON does not need the checked ones.
     ["-D_FORTIFY_SOURCE=0"]),
]


def run(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, **kwargs)


def system_includes() -> list[str]:
    """Where this host keeps the C library's headers.

    A compiler has to be told; the driver takes -I like any other. The host
    toolchain is asked rather than guessed, so the gate keeps working when the
    SDK moves.
    """
    paths = []
    for command in (["xcrun", "--show-sdk-path"], ["clang", "-print-resource-dir"]):
        got = subprocess.run(command, capture_output=True, text=True)
        if got.returncode == 0:
            root = got.stdout.strip()
            paths.append(f"{root}/usr/include" if command[0] == "xcrun" else f"{root}/include")
    return [f"-I{path}" for path in paths]


def reference(name, sources, flags, work) -> tuple[int, str]:
    binary = work / f"{name}-clang"
    # -fcommon: `int shared;` in two units is one object, which is what C meant
    # by a tentative definition and what compiling the whole program at once
    # gives. Clang defaults to rejecting it; the frontend under test does not.
    built = run(["clang", "-std=gnu11", "-O0", "-w", "-fcommon", *flags,
                 *map(str, sources), "-o", str(binary), "-lm"])
    if built.returncode:
        raise SystemExit(f"clang could not build {name}:\n{built.stderr}")
    got = run([str(binary)])
    return got.returncode, got.stdout


def frontend(coil, work) -> str:
    """The C frontend, built once.

    It is a Coil program like any other; building it and running the binary is
    the same thing as `coil run` and does not repeat the build for every case.
    """
    binary = work / "cc"
    built = run([coil, "build", str(ROOT / "src/dialects/c/cc.coil"), "-O2",
                 "-o", str(binary)])
    if built.returncode:
        raise SystemExit(f"could not build the C frontend:\n{built.stdout}{built.stderr}")
    return str(binary)


def native(coil, cc, name, sources, flags, work) -> tuple[int, str, str]:
    generated = work / f"{name}.coil"
    binary = work / f"{name}-coil"
    lowered = run([cc,
                   "-o", str(generated), *map(str, sources),
                   "-include", str(TARGET / "darwin-arm64.h"),
                   "-include", str(TARGET / "builtins.h"),
                   *flags, *system_includes()])
    if lowered.returncode or not generated.exists():
        return -1, "", (lowered.stdout + lowered.stderr).strip()
    built = run([coil, "build", str(generated), "-O0", "-o", str(binary),
                 "--link-flag", "-lm"])
    if built.returncode:
        return -1, "", (built.stdout + built.stderr).strip()
    got = run([str(binary)])
    return got.returncode, got.stdout, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=shutil.which("coil") or "coil")
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    cases = [(source.stem, [source], []) for source in sorted(CASES.glob("*.c"))]
    cases += PROJECTS
    if args.only:
        cases = [case for case in cases if args.only in case[0]]
    if not cases:
        raise SystemExit(f"no cases in {CASES}")

    passed = 0
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        cc = frontend(args.compiler, work)
        for name, sources, flags in cases:
            want_code, want_out = reference(name, sources, flags, work)
            got_code, got_out, error = native(args.compiler, cc, name, sources, flags, work)
            if error:
                failures.append((name, f"did not compile: {error.splitlines()[-1][:120]}"))
            elif (got_code, got_out) != (want_code, want_out):
                failures.append((name,
                                 f"clang exit={want_code} out={want_out!r} "
                                 f"native exit={got_code} out={got_out!r}"))
            else:
                passed += 1
                print(f"  {name}: matches clang")

    for name, detail in failures:
        print(f"  {name}: {detail}")
    print(f"\n{passed}/{len(cases)} cases match Clang")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
