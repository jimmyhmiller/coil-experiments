#!/usr/bin/env python3
"""Build pinned Doom Generic through the Clang-fed Coil C frontend.

This is the older of the two C paths: Clang preprocesses and type-checks each
translation unit and emits a typed JSON AST, which Coil code links and lowers.
The frontend written entirely in Coil, which reads the C itself, has its own gate
in scripts/c-doom-native.py; both are held to the same framebuffer hash.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import doom_sources as doom  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"))
    parser.add_argument("--builder", type=pathlib.Path)
    parser.add_argument("--build-dir", type=pathlib.Path, default=doom.CACHE / "coil-build")
    args = parser.parse_args()
    source_root = doom.prepare_sources()
    doom.prepare_wad()
    sources = doom.source_files(source_root) + [doom.HEADLESS]
    # Apple's headers redirect the string and stdio functions to _FORTIFY_SOURCE
    # builtins (__builtin___memcpy_chk and friends) that the frontend does not
    # implement. Doom does not depend on the checked variants.
    common = ["-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE",
              "-D_FORTIFY_SOURCE=0", f"-I{source_root}"]
    coil = doom.CACHE / "doom-coil"
    command = [sys.executable, str(ROOT / "scripts/c-build.py"),
               "--compiler", args.compiler]
    if args.builder is not None:
        command.extend(["--builder", str(args.builder)])
    command.extend([*map(str, sources), "-o", str(coil), "-O0",
                    "--build-dir", str(args.build_dir)])
    for flag in common:
        command.append(f"--cflag={flag}")
    command.append("--link-flag=-lm")
    subprocess.run(command, cwd=ROOT, check=True)
    actual = doom.frame_result(coil)
    if actual != doom.EXPECTED_FRAME:
        raise SystemExit(f"Doom framebuffer mismatch:\n"
                         f"expected: {doom.EXPECTED_FRAME}\nactual:   {actual}")
    print(f"Doom Generic ({len(sources)} translation units): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
