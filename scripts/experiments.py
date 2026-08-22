#!/usr/bin/env python3
"""Run every experiment that is a program rather than a test suite.

`coil test` covers the members with `deftest`s. Most of this repo is not that: it
is demos whose contract is "runs, prints this, exits N". This is the same shape as
Coil's own runtime gate -- a corpus list plus blessed stdout and exit status -- so
a silent change in what a demo prints is a failure rather than a shrug.

    python3 scripts/experiments.py --compiler "$(command -v coil)"
    python3 scripts/experiments.py --bless --compiler ...   # re-freeze expectations
    python3 scripts/experiments.py --only gc                # substring filter
    python3 scripts/experiments.py --list

Corpus lines are `<kind> <path> [argument]`:

    run    <file.coil>              build and run it; compare stdout and exit
    stdin  <file.coil> <input>      same, with <input> fed on stdin
    use    <file> <module>          run <file> with --use <module> (reader dialects)
    check  <dir>                    typecheck a member that cannot run headless (GUI)
    wasm   <file.coil>              build for wasm32; success is the whole check

Exit 0 iff every entry matches.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/experiments.txt"
REFERENCE = ROOT / "tests/reference"
TIMEOUT = 300


def entries() -> list[tuple[str, str, str]]:
    out = []
    for raw in CORPUS.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        kind, path = parts[0], parts[1]
        out.append((kind, path, parts[2] if len(parts) > 2 else ""))
    return out


def identity(kind: str, path: str) -> str:
    return f"{kind}-" + path.replace("/", "-").replace(".", "-")


def invoke(compiler: str, kind: str, path: str, arg: str) -> tuple[int, str]:
    """Return (exit status, stdout). Stderr is folded in on failure so a broken
    entry reports why, not just that."""
    stdin_text = ""
    if kind == "run":
        cmd = [compiler, "run", path]
    elif kind == "stdin":
        cmd = [compiler, "run", path]
        stdin_text = (ROOT / arg).read_text()
    elif kind == "use":
        cmd = [compiler, "run", path, "--use", arg]
    elif kind == "check":
        cmd = [compiler, "check"]
    elif kind == "wasm":
        cmd = [compiler, "build", path, "--target", "wasm32-unknown-unknown",
               "-o", os.path.join(tempfile.gettempdir(), "experiments-probe.wasm")]
    else:
        raise SystemExit(f"{CORPUS}: unknown kind {kind!r}")
    cwd = ROOT / path if kind == "check" else ROOT
    try:
        p = subprocess.run(cmd, cwd=cwd, input=stdin_text, text=True,
                           capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return 124, f"TIMED OUT after {TIMEOUT}s\n"
    if kind == "wasm" and p.returncode == 0:
        return 0, "built wasm\n"
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compiler", default="coil")
    ap.add_argument("--bless", action="store_true", help="freeze current output as expected")
    ap.add_argument("--only", default="", help="run only entries whose path contains this")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    selected = [e for e in entries() if args.only in e[1]]
    if args.list:
        for kind, path, extra in selected:
            print(f"{kind:6s} {path} {extra}".rstrip())
        return 0

    REFERENCE.mkdir(parents=True, exist_ok=True)
    passed, failed, blessed = 0, [], 0
    for kind, path, extra in selected:
        ident = identity(kind, path)
        out_file = REFERENCE / f"{ident}.stdout"
        exit_file = REFERENCE / f"{ident}.exit"
        code, out = invoke(args.compiler, kind, path, extra)

        if args.bless:
            out_file.write_text(out)
            exit_file.write_text(f"{code}\n")
            print(f"blessed {kind} {path} (exit {code})")
            blessed += 1
            continue

        if not out_file.is_file():
            failed.append((path, "no blessed output; run with --bless"))
            continue
        want_out, want_code = out_file.read_text(), int(exit_file.read_text())
        if code != want_code:
            failed.append((path, f"exit {code}, want {want_code}"))
        elif out != want_out:
            failed.append((path, "stdout differs from the blessed output"))
        else:
            passed += 1

    if args.bless:
        print(f"\nblessed {blessed} entries into {REFERENCE.relative_to(ROOT)}")
        return 0
    for path, why in failed:
        print(f"FAIL {path}: {why}")
    print(f"\nexperiments: {passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
