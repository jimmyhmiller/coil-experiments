#!/usr/bin/env python3
"""End-to-end tests of the opt-in, bounded-memory C reader (not production code)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c_native", ROOT / "scripts/c-native.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def invoke(command, cwd):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise SystemExit(f"failed ({result.returncode}): {command}\n{result.stdout}{result.stderr}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--backend", default="arm64")
    parser.add_argument("--case", choices=["multi-unit", "aggregate", "inline", "stack", "constant", "extern", "public-data", "sparse"], default="multi-unit")
    args = parser.parse_args()
    compiler = str(pathlib.Path(args.compiler).resolve())
    with tempfile.TemporaryDirectory(prefix="c-generated-test-") as directory:
        work = pathlib.Path(directory)
        fixture = ROOT / "tests/c" / {"aggregate": "generated", "inline": "generated-inline", "stack": "generated-stack", "constant": "generated-constant", "extern": "generated-extern", "public-data": "generated-public-data", "sparse": "generated-sparse", "multi-unit": "multi-unit"}[args.case]
        sources = [fixture / name for name in (["alpha.c", "beta.c"] if args.case == "multi-unit" else ["owner.c", "consumer.c"])]
        native_sources = [fixture / "native.c"] if args.case in ("inline", "extern", "public-data", "sparse") else []
        includes = [str(fixture)] + [p[2:] for p in native.system_includes()]
        manifest = f'''[package]
name = "experiments"
entry = "main.coil"
source-roots = [".", {json.dumps(str(ROOT / "src/dialects/c"))}]
[manifest.providers]
c = "experiments.c.reader"
[readers]
".h" = "experiments.c.reader"
[modules]
"experiments.generated.core" = "api.h"
[c.api]
generated-modules = true
sources = {json.dumps(list(map(str, sources)))}
include-paths = {json.dumps(includes)}
defines = ["_FORTIFY_SOURCE=0"]
prefixes = {json.dumps([str(ROOT / "src/dialects/c/target/darwin-arm64.h"), str(ROOT / "src/dialects/c/target/builtins.h")])}
'''
        if native_sources:
            native_object = work / "native.o"
            invoke(["cc", "-c", str(native_sources[0]), "-o", str(native_object)], work)
            manifest += "[link]\nobjects = " + json.dumps([str(native_object)]) + "\n"
        (work / "Coil.toml").write_text(manifest)
        (work / "api.h").write_text("int main(int argc, char **argv);\n")
        (work / "main.coil").write_text('''(module experiments.generated.main)
(import "experiments.generated.core" :as c)
(defn main [(argc i32) (argv (ptr (ptr i8)))] (-> i64)
  (c/initialize-c-library)
  (cast i64 (c/c-main argc argv)))
''')
        expected = native.reference(args.case, sources + native_sources, ["-I" + includes[0], "-D_FORTIFY_SOURCE=0"], work)
        binary = work / "generated"
        invoke([compiler, "build", "-O0", "--backend", args.backend, "-o", str(binary)], work)
        actual = subprocess.run([str(binary)], text=True, capture_output=True, timeout=15)
        assert (actual.returncode, actual.stdout) == expected, (expected, actual.returncode, actual.stdout, actual.stderr)
        print(f"PASS {args.backend} {args.case}: matches Clang exit status and output")


if __name__ == "__main__":
    main()
