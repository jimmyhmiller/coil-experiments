#!/usr/bin/env python3
"""The pinned Doom Generic sources and shareware WAD the gates build.

Both C-frontend gates measure themselves against the same program at the same
revision, so the provisioning lives here rather than in either of them.
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
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
    """The engine's own translation units, as its Makefile lists them."""
    source_line = next((line for line in (source_root / "Makefile").read_text().splitlines()
                        if line.startswith("SRC_DOOM = ")), None)
    if source_line is None:
        raise SystemExit("pinned Doom Generic Makefile has no SRC_DOOM list")
    return [source_root / (name[:-2] + ".c")
            for name in source_line.removeprefix("SRC_DOOM = ").split()
            if name != "doomgeneric_xlib.o"]


def frame_result(executable: pathlib.Path, timeout: int = 120) -> str:
    process = subprocess.run([str(executable), "-iwad", str(WAD)], cwd=ROOT,
                             capture_output=True, text=True, timeout=timeout)
    marker = next((line for line in process.stdout.splitlines()
                   if line.startswith("doomgeneric: frames=")), None)
    if marker is None:
        raise SystemExit(f"{executable.name} did not complete the frame run")
    return marker
