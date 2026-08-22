#!/usr/bin/env python3
"""Build pinned Doom Generic through the native Coil C frontend."""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "build/c-doom"
DOOM = CACHE / "doomgeneric"
DOOM_REVISION = "fc601639494e089702a1ada082eb51aaafc03722"
DOOM_REPOSITORY = "https://github.com/ozkl/doomgeneric.git"
WAD = CACHE / "doom1.wad"
WAD_REVISION = "9b384dc68add3eb2f5eb7754654cafeeaea5103b"
WAD_SHA256 = "1d7d43be501e67d927e415e0b8f3e29c3bf33075e859721816f652a526cac771"
WAD_URL = f"https://raw.githubusercontent.com/Akbar30Bill/DOOM_wads/{WAD_REVISION}/doom1.wad"
HEADLESS = ROOT / "tests/c/projects/doom/headless.c"
EXPECTED_FRAME = "doomgeneric: frames=1000 frame=640x400 hash=734a03fe31906bc3"


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def prepare_sources() -> pathlib.Path:
    if not DOOM.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", "--no-checkout", DOOM_REPOSITORY, str(DOOM)])
    run(["git", "-C", str(DOOM), "fetch", "--depth=1", "origin", DOOM_REVISION],
        stdout=subprocess.DEVNULL)
    run(["git", "-C", str(DOOM), "checkout", "--detach", "--force", DOOM_REVISION],
        stdout=subprocess.DEVNULL)
    return DOOM / "doomgeneric"


def prepare_wad() -> None:
    if not WAD.exists() or hashlib.sha256(WAD.read_bytes()).hexdigest() != WAD_SHA256:
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(WAD_URL) as response:
            WAD.write_bytes(response.read())
    actual = hashlib.sha256(WAD.read_bytes()).hexdigest()
    if actual != WAD_SHA256:
        raise SystemExit(f"doom1.wad checksum mismatch: expected {WAD_SHA256}, got {actual}")


def source_files(source_root: pathlib.Path) -> list[pathlib.Path]:
    source_line = next((line for line in (source_root / "Makefile").read_text().splitlines()
                        if line.startswith("SRC_DOOM = ")), None)
    if source_line is None:
        raise SystemExit("pinned Doom Generic Makefile has no SRC_DOOM list")
    engine = [source_root / (name[:-2] + ".c") for name in source_line.removeprefix("SRC_DOOM = ").split()
              if name != "doomgeneric_xlib.o"]
    return engine + [HEADLESS]


def frame_result(executable: pathlib.Path) -> str:
    process = run([str(executable), "-iwad", str(WAD)], capture_output=True, text=True, timeout=30)
    marker = next((line for line in process.stdout.splitlines() if line.startswith("doomgeneric: frames=")), None)
    if marker is None:
        raise SystemExit(f"{executable.name} did not complete the frame run")
    return marker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"))
    parser.add_argument("--builder", type=pathlib.Path)
    parser.add_argument("--build-dir", type=pathlib.Path, default=CACHE / "coil-build")
    args = parser.parse_args()
    source_root = prepare_sources()
    prepare_wad()
    sources = source_files(source_root)
    common = ["-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE", f"-I{source_root}"]
    coil = CACHE / "doom-coil"
    command = [sys.executable, str(ROOT / "scripts/c-build.py"),
               "--compiler", args.compiler]
    if args.builder is not None:
        command.extend(["--builder", str(args.builder)])
    command.extend([*map(str, sources), "-o", str(coil), "-O0",
                    "--build-dir", str(args.build_dir)])
    for flag in common:
        command.append(f"--cflag={flag}")
    command.append("--link-flag=-lm")
    run(command)
    actual = frame_result(coil)
    if actual != EXPECTED_FRAME:
        raise SystemExit(f"Doom framebuffer mismatch:\nexpected: {EXPECTED_FRAME}\nactual:   {actual}")
    print(f"Doom Generic ({len(sources)} translation units): {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
