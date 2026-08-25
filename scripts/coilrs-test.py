#!/usr/bin/env python3
"""Lossless and end-to-end checks for the CoilRS reader/converter."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "src/dialects/rust/coilrs.py"
FIXTURE = ROOT / "tests/rust/native_roundtrip.coil"
STRUCTURED_FIXTURE = ROOT / "tests/rust/structured.coilrs"
ADVANCED_FIXTURE = ROOT / "tests/rust/advanced.coilrs"
SURFACE_FIXTURE = ROOT / "tests/rust/surface.coilrs"
FFI_FIXTURE = ROOT / "tests/rust/ffi.coilrs"


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def require(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise SystemExit(f"{label} failed ({result.returncode})\n{result.stdout}{result.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default="coil")
    parser.add_argument(
        "--compiler-source", type=Path, default=ROOT.parent / "coil" / "src" / "compiler"
    )
    parser.add_argument("--compiler-repo", type=Path, default=ROOT.parent / "coil")
    parser.add_argument("--build-compiler-copy", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="coilrs-test-") as raw_tmp:
        tmp = Path(raw_tmp)
        encoded = tmp / "native_roundtrip.coilrs"
        decoded = tmp / "native_roundtrip.coil"
        with encoded.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "from-coil", str(FIXTURE)],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "fixture conversion")
        with decoded.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "to-coil", str(encoded)],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "fixture decoding")
        if FIXTURE.read_bytes() != decoded.read_bytes():
            raise SystemExit("fixture did not round-trip byte-for-byte")

        pretty_once = tmp / "pretty-once.coilrs"
        pretty_native = tmp / "pretty-native.coil"
        pretty_twice = tmp / "pretty-twice.coilrs"
        with pretty_once.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "from-coil", str(FIXTURE), "--pretty"],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "pretty conversion")
        with pretty_native.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "to-coil", str(pretty_once)],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "pretty native conversion")
        with pretty_twice.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "from-coil", str(pretty_native), "--pretty"],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "pretty reconversion")
        if pretty_once.read_bytes() != pretty_twice.read_bytes():
            raise SystemExit("canonical pretty conversion is not idempotent")

        structured_once = tmp / "structured-once.coilrs"
        structured_native = tmp / "structured-native.coil"
        structured_twice = tmp / "structured-twice.coilrs"
        with structured_once.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "from-coil", str(FIXTURE), "--structured-pretty"],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "structured pretty conversion")
        with structured_native.open("w") as output:
            result = subprocess.run(
                ["python3", str(TOOL), "to-coil", str(structured_once)],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "structured native conversion")
        with structured_twice.open("w") as output:
            result = subprocess.run(
                [
                    "python3",
                    str(TOOL),
                    "from-coil",
                    str(structured_native),
                    "--structured-pretty",
                ],
                cwd=ROOT,
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        require(result, "structured pretty reconversion")
        if structured_once.read_bytes() != structured_twice.read_bytes():
            raise SystemExit("canonical structured conversion is not idempotent")
        original_dump = run(args.compiler, "dump-read", str(FIXTURE))
        structured_dump = run(args.compiler, "dump-read", str(structured_native))
        require(original_dump, "original fixture Code dump")
        require(structured_dump, "structured fixture Code dump")
        original_read = original_dump.stdout
        structured_read = structured_dump.stdout
        span = re.compile(r"@[0-9]+:[0-9]+:[0-9]+:[0-9]+")
        if span.sub("", original_read) != span.sub("", structured_read):
            raise SystemExit("structured conversion changed the parsed Coil Code tree")

        result = run(args.compiler, "run", str(encoded), "--use", "experiments.rust.lang")
        require(result, "reader execution")
        result = run(
            args.compiler,
            "run",
            str(STRUCTURED_FIXTURE),
            "--use",
            "experiments.rust.lang",
        )
        require(result, "structured reader execution")
        result = run(
            args.compiler,
            "run",
            str(ADVANCED_FIXTURE),
            "--use",
            "experiments.rust.lang",
        )
        require(result, "advanced structured reader execution")
        result = run(
            args.compiler,
            "run",
            str(SURFACE_FIXTURE),
            "--use",
            "experiments.rust.lang",
        )
        require(result, "generic/control structured reader execution")
        result = run(
            args.compiler,
            "run",
            str(FFI_FIXTURE),
            "--use",
            "experiments.rust.lang",
        )
        require(result, "FFI structured reader execution")

        compiler_src = args.compiler_source.resolve()
        converted = tmp / "compiler-coilrs"
        restored = tmp / "compiler-restored"
        result = run("python3", str(TOOL), "from-coil-tree", str(compiler_src), str(converted))
        require(result, "compiler tree conversion")
        result = run("python3", str(TOOL), "to-coil-tree", str(converted), str(restored))
        require(result, "compiler tree restoration")

        originals = sorted(compiler_src.rglob("*.coil"))
        if not originals:
            raise SystemExit(f"no compiler sources found under {compiler_src}")
        for original in originals:
            restored_file = restored / original.relative_to(compiler_src)
            if original.read_bytes() != restored_file.read_bytes():
                raise SystemExit(f"compiler source changed across round trip: {original}")

        structured_compiler = tmp / "compiler-structured"
        structured_restored = tmp / "compiler-structured-restored"
        result = run(
            "python3",
            str(TOOL),
            "from-coil-tree",
            str(compiler_src),
            str(structured_compiler),
            "--structured-pretty",
        )
        require(result, "structured compiler tree conversion")
        result = run(
            "python3",
            str(TOOL),
            "to-coil-tree",
            str(structured_compiler),
            str(structured_restored),
        )
        require(result, "structured compiler tree restoration")
        compiler_structured_functions = sum(
            sum(line.startswith("fn ") for line in source.read_text().splitlines())
            for source in structured_compiler.glob("*.coilrs")
        )
        if compiler_structured_functions < 1000:
            raise SystemExit(
                "structured compiler round trip used too little dedicated syntax: "
                f"{compiler_structured_functions} functions"
            )
        for original in originals:
            restored_file = structured_restored / original.relative_to(compiler_src)
            original_dump = run(args.compiler, "dump-read", str(original))
            restored_dump = run(args.compiler, "dump-read", str(restored_file))
            require(original_dump, f"dump original {original.name}")
            require(restored_dump, f"dump restored {original.name}")
            if span.sub("", original_dump.stdout) != span.sub("", restored_dump.stdout):
                raise SystemExit(f"structured Code-tree round trip changed {original}")
        print(
            f"CoilRS: structured/native readers ran and {len(originals)} "
            "compiler source files round-tripped exactly "
            f"({compiler_structured_functions} structured functions)"
        )

        if args.build_compiler_copy:
            converted_repo = tmp / "compiler-copy"
            candidate = tmp / "coilrs-compiler-a64"
            result = run(
                "python3",
                str(TOOL),
                "from-coil-tree",
                str(args.compiler_repo.resolve()),
                str(converted_repo),
                "--install-reader",
                "--structured-pretty",
            )
            require(result, "full compiler-copy conversion")
            structured_functions = 0
            fallback_forms = 0
            for converted_source in converted_repo.rglob("*.coilrs"):
                text = converted_source.read_text()
                structured_functions += sum(line.startswith("fn ") for line in text.splitlines())
                fallback_forms += sum(
                    line.startswith("coil_item {") for line in text.splitlines()
                )
            if structured_functions < 1000:
                raise SystemExit(
                    "compiler conversion used too little dedicated syntax: "
                    f"only {structured_functions} structured functions"
                )
            result = run(
                args.compiler,
                "build",
                "src/compiler/main_a64.coilrs",
                "--use",
                "experiments.rust.lang",
                "-o",
                str(candidate),
                cwd=converted_repo,
            )
            require(result, "converted compiler build")
            result = run(str(candidate), "--version", cwd=converted_repo)
            require(result, "converted compiler execution")
            if "coil 0.1.0" not in result.stdout:
                raise SystemExit(f"unexpected converted compiler version output: {result.stdout!r}")
            print(
                "CoilRS: converted compiler copy built and executed through one --use "
                f"({structured_functions} structured functions, {fallback_forms} fallbacks)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
