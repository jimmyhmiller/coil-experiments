#!/usr/bin/env python3
"""Build Doom Generic with the native C frontend, with no Clang in the pipeline.

Every translation unit is handed to src/dialects/c/cc.coil at once, which lowers
the whole program to one Coil module; `coil build` turns that into the
executable. Clang is not involved in reading a single line of C -- it only links
the object file `coil build` produces.

Without --play this runs the headless frame hasher and checks it against the
pinned hash, which is the same hash a Clang-built Doom produces. With --play it
builds the windowed game, sound included.
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
TARGET = ROOT / "src/dialects/c/target"
BACKEND = ROOT / "src/apps/doom/cocoa.c"


def system_includes() -> list[str]:
    """Where this host keeps the C library's headers.

    A compiler has to be told; the driver takes -I like any other. The host
    toolchain is asked rather than guessed, so this keeps working when the SDK
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

    source_root = doom.prepare_sources()
    doom.prepare_wad()

    sources = doom.source_files(source_root)
    defines = ["-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE",
               # Apple's headers redirect the string and stdio functions to
               # _FORTIFY_SOURCE builtins this frontend does not implement, and
               # Doom does not depend on the checked variants.
               "-D_FORTIFY_SOURCE=0"]
    link = ["-lm"]
    if args.play:
        # Upstream ships its sound and music modules but never builds them: the
        # pinned configuration leaves FEATURE_SOUND undefined. Both are built
        # here, against SDL2 and SDL2_mixer, along with the MUS-to-MIDI
        # converter the music module needs.
        sources += [source_root / "i_sdlsound.c",
                    source_root / "i_sdlmusic.c",
                    source_root / "mus2mid.c",
                    BACKEND]
        # SDL offers to pull in <arm_neon.h> for its own vector helpers; Doom
        # uses none of them, and the NEON intrinsic headers are a vector dialect
        # this frontend does not implement. SDL's own switch turns it off.
        defines += ["-DFEATURE_SOUND", "-DSDL_DISABLE_ARM_NEON_H",
                    "-I/opt/homebrew/include/SDL2"]
        link += ["-lobjc", "-L/opt/homebrew/lib", "-lSDL2", "-lSDL2_mixer",
                 "-framework", "AppKit", "-framework", "QuartzCore"]
        name = "doom-native-play"
    else:
        sources.append(doom.HEADLESS)
        name = "doom-native"

    lowered = doom.CACHE / f"{name}.coil"
    executable = doom.CACHE / name

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
        return subprocess.run([str(executable), "-iwad", str(doom.WAD)],
                              cwd=doom.CACHE).returncode

    actual = doom.frame_result(executable)
    if actual != doom.EXPECTED_FRAME:
        raise SystemExit(f"Doom framebuffer mismatch:\n"
                         f"expected: {doom.EXPECTED_FRAME}\nactual:   {actual}")
    print(f"Doom Generic ({len(sources)} translation units): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
