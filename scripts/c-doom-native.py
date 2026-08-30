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
import socket
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import doom_sources as doom  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/dialects/c/target"
BACKEND = ROOT / "src/apps/doom/cocoa.c"
INSPECTOR = "experiments.heap-inspector.transform"


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


def available_inspector_port(preferred: int) -> int:
    """Choose the first free loopback port at or above the requested port."""
    for port in range(preferred, min(preferred + 20, 65536)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            try:
                candidate.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"no free heap-inspector port in {preferred}..{preferred + 19}")


def run_playable(executable: pathlib.Path, inspected: bool, open_inspector: bool,
                 inspector_port: int) -> int:
    """Run windowed Doom and, when requested, open its in-process heap viewer."""
    command = [str(executable), "-iwad", str(doom.WAD)]
    if not inspected:
        return subprocess.run(command, cwd=doom.CACHE).returncode

    environment = os.environ.copy()
    environment["COIL_HEAP_INSPECTOR_VIEWER"] = str(
        ROOT / "src/experiments/heap-inspector/viewer")
    environment["COIL_HEAP_INSPECTOR_PORT"] = str(inspector_port)
    inspector_url = f"http://127.0.0.1:{inspector_port}/"
    process = subprocess.Popen(command, cwd=doom.CACHE, env=environment)
    if open_inspector:
        deadline = time.monotonic() + 15.0
        while process.poll() is None and time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(inspector_url, timeout=0.25) as response:
                    if response.status == 200:
                        subprocess.run(["open", inspector_url], check=False)
                        break
            except OSError:
                time.sleep(0.1)
        else:
            if process.poll() is None:
                print(f"heap inspector did not become ready at {inspector_url}",
                      file=sys.stderr)
    return process.wait()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"))
    parser.add_argument("--play", action="store_true",
                        help="build the windowed game instead of the frame hasher")
    parser.add_argument("--heap-inspector", action="store_true",
                        help="instrument windowed Doom and serve its live heap viewer")
    parser.add_argument("--no-open-inspector", action="store_true",
                        help="do not open the heap viewer in the default browser")
    parser.add_argument("--inspector-port", type=int, default=7391,
                        help="preferred heap-viewer port (default: 7391)")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("-O", dest="optimization")
    args = parser.parse_args()

    if args.heap_inspector and not args.play:
        parser.error("--heap-inspector requires --play")
    if not 1 <= args.inspector_port <= 65535:
        parser.error("--inspector-port must be between 1 and 65535")
    optimization = args.optimization or "-O2"

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
        name = "doom-native-play-inspected" if args.heap_inspector else "doom-native-play"
    else:
        sources.append(doom.HEADLESS)
        name = "doom-native"

    lowered = doom.CACHE / f"{name}.coil"
    executable = doom.CACHE / name

    # The frontend is a Coil program like any other: it is built once and then
    # run, which is what `coil run` does and saves repeating for every build.
    cc = doom.CACHE / "cc"
    built = subprocess.run([args.compiler, "build", str(ROOT / "src/dialects/c/cc.coil"),
                            "-O2", "-o", str(cc)], cwd=ROOT)
    if built.returncode != 0:
        return 1

    frontend = [str(cc),
                "-o", str(lowered), *map(str, sources),
                "-include", str(TARGET / "darwin-arm64.h"),
                "-include", str(TARGET / "builtins.h"),
                f"-I{source_root}", *defines, *system_includes()]
    if subprocess.run(frontend, cwd=ROOT).returncode != 0:
        return 1

    build = [args.compiler, "build", str(lowered), optimization, "-o", str(executable)]
    if args.heap_inspector:
        build.extend(["--use", INSPECTOR])
    for flag in link:
        build.extend(["--link-flag", flag])
    if subprocess.run(build, cwd=ROOT).returncode != 0:
        return 1

    print(f"built {executable} ({len(sources)} translation units, no Clang frontend)")
    if args.build_only:
        return 0
    if args.play:
        inspector_port = (available_inspector_port(args.inspector_port)
                          if args.heap_inspector else args.inspector_port)
        if args.heap_inspector:
            print(f"heap inspector: http://127.0.0.1:{inspector_port}/")
        return run_playable(executable, args.heap_inspector, not args.no_open_inspector,
                            inspector_port)

    actual = doom.frame_result(executable)
    if actual != doom.EXPECTED_FRAME:
        raise SystemExit(f"Doom framebuffer mismatch:\n"
                         f"expected: {doom.EXPECTED_FRAME}\nactual:   {actual}")
    print(f"Doom Generic ({len(sources)} translation units): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
