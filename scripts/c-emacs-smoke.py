#!/usr/bin/env python3
"""Test a translated Emacs using real upstream-generated bootstrap assets."""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emacs", required=True)
    parser.add_argument("--assets-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    binary = pathlib.Path(args.emacs).resolve()
    assets = pathlib.Path(args.assets_root).resolve()
    output = pathlib.Path(args.output).resolve()
    for relative in ("lisp/loadup.el", "lisp/loaddefs.el", "lisp/international/charscript.el",
                     "lisp/international/charprop.el", "etc/DOC", "etc/charsets/8859-2.map"):
        if not (assets / relative).is_file():
            raise SystemExit(f"missing upstream bootstrap asset: {assets / relative}")
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, EMACSLOADPATH=str(assets / "lisp"),
               EMACSPATH=str(assets / "lib-src"), EMACSDATA=str(assets / "etc"),
               EMACSDOC=str(assets / "etc"))
    results = []
    with tempfile.TemporaryDirectory(prefix="c-emacs-smoke-") as directory:
        smoke = pathlib.Path(directory) / "smoke.el"
        smoke.write_text("(princ (+ 20 22))\n(terpri)\n(kill-emacs 0)\n")
        cases = [
            ("version", ["--version"], "GNU Emacs"),
            ("bare-batch", ["--batch", "--no-loadup", "-l", str(smoke)], "42\n"),
            ("quick-batch", ["--batch", "--quick", "--eval",
                             "(progn (princ (+ 20 22)) (terpri))"], "42\n"),
        ]
        for name, arguments, expected in cases:
            command = [str(binary), *arguments]
            started = time.monotonic()
            # Write logs as the child runs so a slow source-only bootstrap can
            # be distinguished from a stuck process without losing diagnostics.
            out_path, err_path = output / f"{name}.stdout", output / f"{name}.stderr"
            with out_path.open("wb") as out_file, err_path.open("wb") as err_file:
                try:
                    result = subprocess.run(command, env=env, cwd=directory,
                                            stdout=out_file, stderr=err_file, timeout=args.timeout)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = None
            stdout, stderr = out_path.read_bytes(), err_path.read_bytes()
            passed = code == 0 and (stdout.startswith(expected.encode()) if name == "version"
                                    else stdout == expected.encode())
            record = {"case": name, "command": command, "exit_status": code, "passed": passed,
                      "elapsed_s": round(time.monotonic() - started, 3)}
            results.append(record)
            print(json.dumps(record), flush=True)
            if not passed:
                print(stderr.decode(errors="replace")[-6000:], flush=True)
    (output / "smoke.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
