#!/usr/bin/env python3
"""Focused positive and diagnostic tests for the dependent metaprogram."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default="coil")
    args = parser.parse_args()

    positive = [
        [args.compiler, "run", "src/experiments/dependent/demo.coil"],
        [args.compiler, "test", "--suite", "dependent"],
    ]
    for command in positive:
        result = run(command)
        if result.returncode != 0:
            print(result.stdout + result.stderr)
            return 1

    negative = {
        "tests/dependent/type_mismatch.coil": "dependent: type mismatch",
        "tests/dependent/bad_refl.coil": "refl requires definitionally equal endpoints",
        "tests/dependent/vector_index.coil": "dependent: type mismatch",
        "tests/dependent/out_of_bounds.coil": "dependent: type mismatch",
        "tests/dependent/nontermination.coil": "normalization exceeded its reduction limit",
        "tests/dependent/non_exhaustive.coil": "dcase must contain exactly one branch per constructor",
        "tests/dependent/non_positive.coil": "recursive data occurrence is not strictly positive",
        "tests/dependent/non_structural_recursion.coil": "recursive def call is not on a structurally smaller pattern binder",
        "tests/dependent/duplicate_declaration.coil": "duplicate constructor or declaration name",
        "tests/dependent/universe_escape.coil": "dependent: type mismatch",
    }
    for fixture, expected in negative.items():
        result = run([args.compiler, "check", fixture])
        output = result.stdout + result.stderr
        if result.returncode == 0:
            print(f"FAIL {fixture}: unexpectedly typechecked")
            return 1
        if expected not in output:
            print(f"FAIL {fixture}: missing diagnostic {expected!r}\n{output}")
            return 1

    print("dependent: positive and negative tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
