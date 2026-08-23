#!/usr/bin/env python3
"""Build and run playable Doom through the native Coil C frontend.

Same pinned Doom Generic sources and shareware WAD as the integration gate,
with src/apps/doom/cocoa.c as the platform backend instead of the headless
frame hasher.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src/apps/doom/cocoa.c"


def gate_module():
    """Reuse the gate's pinned source and WAD provisioning verbatim."""
    spec = importlib.util.spec_from_file_location("c_doom", ROOT / "scripts/c-doom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"))
    parser.add_argument("--build-dir", type=pathlib.Path)
    parser.add_argument("-O", dest="optimization", default="-O2")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()

    gate = gate_module()
    source_root = gate.prepare_sources()
    gate.prepare_wad()

    sources = [path for path in gate.source_files(source_root) if path != gate.HEADLESS]
    # Upstream ships its sound and music modules but never builds them: the
    # pinned configuration leaves FEATURE_SOUND undefined, so sound_modules[]
    # is empty. Both are compiled here, against SDL2 and SDL2_mixer.
    sources.append(source_root / "i_sdlsound.c")
    sources.append(source_root / "i_sdlmusic.c")
    # Music arrives as MUS lumps; the converter is not in SRC_DOOM either,
    # because nothing in the pinned configuration ever called it.
    sources.append(source_root / "mus2mid.c")
    sources.append(BACKEND)

    executable = gate.CACHE / "doom-play"
    command = [sys.executable, str(ROOT / "scripts/c-build.py"),
               "--compiler", args.compiler,
               *map(str, sources), "-o", str(executable), args.optimization]
    if args.build_dir is not None:
        command.extend(["--build-dir", str(args.build_dir)])
    for flag in ["-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE",
                 "-D_FORTIFY_SOURCE=0", "-DFEATURE_SOUND", f"-I{source_root}",
                 "-I/opt/homebrew/include/SDL2"]:
        command.append(f"--cflag={flag}")
    for flag in ["-lm", "-lobjc", "-L/opt/homebrew/lib", "-lSDL2", "-lSDL2_mixer",
                 "-framework", "AppKit", "-framework", "QuartzCore"]:
        command.append(f"--link-flag={flag}")
    subprocess.run(command, cwd=ROOT, check=True)

    print(f"built {executable} ({len(sources)} translation units)")
    if args.build_only:
        return 0
    return subprocess.run([str(executable), "-iwad", str(gate.WAD)], cwd=gate.CACHE).returncode


if __name__ == "__main__":
    raise SystemExit(main())
