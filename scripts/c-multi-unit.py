#!/usr/bin/env python3
"""Verify native C translation-unit linkage and structural ABI checks."""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/c/multi-unit"


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def native_command(compiler: str, builder: pathlib.Path | None,
                   *arguments: str) -> list[str]:
    command = [sys.executable, str(ROOT / "scripts/c-build.py"),
               "--compiler", compiler]
    if builder is not None:
        command.extend(["--builder", str(builder)])
    return [*command, *arguments, "-O0"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=os.environ.get("COIL", "coil"))
    parser.add_argument("--builder", type=pathlib.Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary_name:
        temporary = pathlib.Path(temporary_name)
        coil = temporary / "coil-program"
        sources = [FIXTURE / "alpha.c", FIXTURE / "beta.c"]
        run(native_command(args.compiler, args.builder, *map(str, sources),
                           "-o", str(coil)))
        actual = run([str(coil)], capture_output=True)
        expected = (b"alpha+\nbeta+\nlinked-varargs=1\nmain=1\n"
                    b"beta-\nalpha-\n")
        assert (actual.returncode, actual.stdout, actual.stderr) == (0, expected, b"")
        print("multi-unit functions, statics, globals, records, callbacks, and lifecycle pass")

        bad_left = temporary / "bad-left.c"
        bad_right = temporary / "bad-right.c"
        bad_left.write_text("int mismatch(int x) { return x; }\n")
        bad_right.write_text("double mismatch(double); int main(void) { return 0; }\n")
        incompatible = subprocess.run(
            native_command(args.compiler, args.builder, str(bad_left), str(bad_right),
                           "-o", str(temporary / "bad-program")),
            cwd=ROOT, capture_output=True, text=True,
        )
        assert incompatible.returncode != 0
        assert "incompatible declarations for mismatch" in incompatible.stderr
        print("multi-unit incompatible declarations fail before lowering")

        nested_left = temporary / "nested-left.c"
        nested_right = temporary / "nested-right.c"
        nested_left.write_text(
            "struct Inner { int value; }; struct Outer { struct Inner inner; }; "
            "int consume(struct Outer *x) { return x->inner.value; }\n")
        nested_right.write_text(
            "struct Inner { double value; }; struct Outer { struct Inner inner; }; "
            "int consume(struct Outer *); int main(void) { return 0; }\n")
        nested = subprocess.run(
            native_command(args.compiler, args.builder, str(nested_left), str(nested_right),
                           "-o", str(temporary / "nested-program")),
            cwd=ROOT, capture_output=True, text=True,
        )
        assert nested.returncode != 0
        assert "incompatible declarations for consume" in nested.stderr
        print("multi-unit ABI validation follows nested record layouts")

        cjson = ROOT / "tests/c/projects/cjson"
        cjson_coil = temporary / "cjson-coil"
        run(native_command(args.compiler, args.builder, str(cjson / "cJSON.c"),
                           str(cjson / "separate-program.c"), "-o", str(cjson_coil),
                           "--link-flag=-lm"))
        cjson_actual = run([str(cjson_coil)], capture_output=True)
        expected_cjson = b'{"name":"coil","values":[1,2,3,4],"ok":true}\n10\n'
        assert (cjson_actual.returncode, cjson_actual.stdout) == (0, expected_cjson)
        print("cJSON builds and runs as two real translation units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
