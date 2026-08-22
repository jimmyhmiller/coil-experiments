#!/usr/bin/env python3
"""Bootstrap and invoke the native Coil C builder.

This file deliberately contains no frontend behavior. C translation units,
Clang JSON, linkage, and lowering are all handled by experiments.c.build.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/dialects/c"
DEFAULT_BUILDER = ROOT / "build/c-native/c-build"


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="bootstrap and invoke the native Coil C frontend",
        epilog="all remaining arguments are forwarded to experiments.c.build",
    )
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"),
                        help="Coil toolchain used to build the frontend and final program")
    parser.add_argument("--builder", type=pathlib.Path, default=DEFAULT_BUILDER,
                        help="path to the native frontend executable")
    parser.add_argument("--rebuild-builder", action="store_true")
    return parser.parse_known_args()


def compiler_identity(compiler: str) -> pathlib.Path:
    return pathlib.Path(shutil.which(compiler) or compiler).resolve()


def builder_sources() -> list[pathlib.Path]:
    return [PACKAGE / "Coil.toml", *PACKAGE.glob("*.coil")]


def builder_current(builder: pathlib.Path, compiler: str) -> bool:
    stamp = builder.with_suffix(builder.suffix + ".toolchain")
    if not builder.is_file() or not stamp.is_file():
        return False
    identity = f"{compiler_identity(compiler)}\n"
    return (stamp.read_text() == identity and
            all(source.stat().st_mtime_ns <= builder.stat().st_mtime_ns
                for source in builder_sources()))


def build_builder(builder: pathlib.Path, compiler: str) -> int:
    builder.parent.mkdir(parents=True, exist_ok=True)
    command = [compiler, "build", str(PACKAGE / "build.coil"),
               "-O3", "-o", str(builder)]
    status = subprocess.run(command, cwd=ROOT).returncode
    if status == 0:
        builder.with_suffix(builder.suffix + ".toolchain").write_text(
            f"{compiler_identity(compiler)}\n")
    return status


def main() -> int:
    args, forwarded = parse_args()
    builder = args.builder.resolve()
    if args.rebuild_builder or not builder_current(builder, args.compiler):
        status = build_builder(builder, args.compiler)
        if status != 0:
            return status
    if "--coil" not in forwarded:
        forwarded.extend(["--coil", args.compiler])
    return subprocess.run([str(builder), *forwarded], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
