#!/usr/bin/env python3
"""Build Doom Generic with the native C frontend, with no Clang in the pipeline.

The pinned sources and WAD come from the existing gate. Every translation unit
is handed to src/dialects/c/cc.coil at once, which lowers the whole program to
one Coil module; `coil build` turns that into the executable. Clang is not
invoked for anything but linking the object file `coil build` produces.

Without --play this runs the headless frame hasher and checks it against the
same expected hash the Clang-path gate uses, so the two frontends are held to
the same result. With --play it builds the Cocoa backend, sound included.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/dialects/c/target"
BACKEND = ROOT / "src/apps/doom/cocoa.c"


def gate_module():
    """Reuse the gate's pinned source and WAD provisioning verbatim."""
    spec = importlib.util.spec_from_file_location("c_doom", ROOT / "scripts/c-doom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def system_includes() -> list[str]:
    """Where this host keeps the C library's headers.

    A compiler has to be told; the driver takes -I like any other. The host
    toolchain is asked rather than guessed so this keeps working when the SDK
    moves.
    """
    paths = []
    sdk = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True, text=True)
    if sdk.returncode == 0:
        paths.append(f"{sdk.stdout.strip()}/usr/include")
    resource = subprocess.run(["clang", "-print-resource-dir"], capture_output=True, text=True)
    if resource.returncode == 0:
        paths.append(f"{resource.stdout.strip()}/include")
    return [f"-I{path}" for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"))
    parser.add_argument("--play", action="store_true",
                        help="build the windowed game instead of the frame hasher")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("-O", dest="optimization", default="-O2")
    args = parser.parse_args()

    gate = gate_module()
    source_root = gate.prepare_sources()
    gate.prepare_wad()

    sources = [path for path in gate.source_files(source_root) if path != gate.HEADLESS]
    defines = ["-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE",
               # Apple's headers redirect the string and stdio functions to
               # _FORTIFY_SOURCE builtins this frontend does not implement, and
               # Doom does not depend on the checked variants.
               "-D_FORTIFY_SOURCE=0"]
    link = ["-lm"]
    if args.play:
        # Upstream ships its sound and music modules but never builds them: the
        # pinned configuration leaves FEATURE_SOUND undefined. Both are built
        # here, against SDL2 and SDL2_mixer.
        sources += [source_root / "i_sdlsound.c",
                    source_root / "i_sdlmusic.c",
                    source_root / "mus2mid.c",
                    BACKEND]
        # SDL offers to pull in <arm_neon.h> for its own vector helpers; Doom
        # uses none of them, and the NEON intrinsic headers are a vector
        # dialect this frontend does not implement. SDL's own switch turns the
        # include off.
        defines += ["-DFEATURE_SOUND", "-DSDL_DISABLE_ARM_NEON_H",
                    "-I/opt/homebrew/include/SDL2"]
        link += ["-lobjc", "-L/opt/homebrew/lib", "-lSDL2", "-lSDL2_mixer",
                 "-framework", "AppKit", "-framework", "QuartzCore"]
        name = "doom-native-play"
    else:
        sources.append(gate.HEADLESS)
        name = "doom-native"

    lowered = gate.CACHE / f"{name}.coil"
    executable = gate.CACHE / name

    frontend = [args.compiler, "run", str(ROOT / "src/dialects/c/cc.coil"), "--",
                "-o", str(lowered), *map(str, sources),
                "-include", str(TARGET / "darwin-arm64.h"),
                "-include", str(TARGET / "builtins.h"),
                f"-I{source_root}", *defines, *system_includes()]
    if subprocess.run(frontend, cwd=ROOT).returncode != 0:
        return 1

    build = [args.compiler, "build", str(lowered), args.optimization, "-o", str(executable)]
    for flag in link:
        build.extend(["--link-flag", flag])
    if subprocess.run(build, cwd=ROOT).returncode != 0:
        return 1

    print(f"built {executable} ({len(sources)} translation units, no Clang frontend)")
    if args.build_only:
        return 0
    if args.play:
        return subprocess.run([str(executable), "-iwad", str(gate.WAD)], cwd=gate.CACHE).returncode

    actual = gate.frame_result(executable)
    if actual != gate.EXPECTED_FRAME:
        raise SystemExit(f"Doom framebuffer mismatch:\n"
                         f"expected: {gate.EXPECTED_FRAME}\nactual:   {actual}")
    print(f"Doom Generic ({len(sources)} translation units): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
