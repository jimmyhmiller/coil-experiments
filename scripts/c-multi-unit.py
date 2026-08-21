#!/usr/bin/env python3
"""Verify C translation-unit linkage against the platform C compiler."""
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/c/multi-unit"


def run(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


with tempfile.TemporaryDirectory() as temporary:
    temporary = pathlib.Path(temporary)
    clang = temporary / "clang-program"
    coil = temporary / "coil-program"
    sources = [FIXTURE / "alpha.c", FIXTURE / "beta.c"]
    run(["clang", "-std=gnu11", "-O3", "-fcommon", *map(str, sources), "-o", clang])
    run(["python3", str(ROOT / "scripts/c-build.py"), *map(str, sources), "-o", coil])
    expected = run([clang], capture_output=True)
    actual = run([coil], capture_output=True)
    assert (actual.returncode, actual.stdout, actual.stderr) == (expected.returncode, expected.stdout, expected.stderr)
    print("multi-unit functions, statics, globals, records, callbacks, and lifecycle match clang")

    bad_left = temporary / "bad-left.c"
    bad_right = temporary / "bad-right.c"
    bad_left.write_text("int mismatch(int x) { return x; }\n")
    bad_right.write_text("double mismatch(double); int main(void) { return 0; }\n")
    incompatible = subprocess.run(
        ["python3", str(ROOT / "scripts/c-build.py"), str(bad_left), str(bad_right),
         "-o", str(temporary / "bad-program")],
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
        ["python3", str(ROOT / "scripts/c-build.py"), str(nested_left), str(nested_right),
         "-o", str(temporary / "nested-program")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert nested.returncode != 0
    assert "incompatible declarations for consume" in nested.stderr
    print("multi-unit ABI validation follows nested record layouts")

    cjson = ROOT / "tests/c/projects/cjson"
    cjson_coil = temporary / "cjson-coil"
    run(["python3", str(ROOT / "scripts/c-build.py"), str(cjson / "cJSON.c"),
         str(cjson / "separate-program.c"), "-o", cjson_coil])
    cjson_actual = run([cjson_coil], capture_output=True)
    assert cjson_actual.stdout == b'{"name":"coil","values":[1,2,3,4],"ok":true}\n10\n'
    print("cJSON builds and runs as two real translation units")
