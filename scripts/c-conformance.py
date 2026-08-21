#!/usr/bin/env python3
"""Reproducible public C-suite scoring for the native C reader."""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "build/conformance/sources"
TINYCC_REV = "2ba12e83b3599ca8f5d50c179fe5138fe956f0c9"
CTEST_REV = "5c7275656d751de0e68b2d340a95b5681858ed07"
REPOSITORIES = {
    "tinycc": ("https://github.com/TinyCC/tinycc.git", TINYCC_REV),
    "c-testsuite": ("https://github.com/c-testsuite/c-testsuite.git", CTEST_REV),
}

# Not C-frontend tests, not applicable on x86-64 Linux, or skipped by upstream.
# Unsupported C features such as VLAs, bitfields, atomics, and TLS are deliberately
# not skipped: they must lower the score until the frontend implements them.
TINYCC_SKIPS = {
    "34": "invalid nonstandard array assignment; skipped by upstream",
    "38": "upstream expectation disagrees with source program output",
    "60": "diagnostic-driver test (-dt), not a native program",
    "70": "expected output requires TCC-only __TINYC__ binary floating literals",
    "71": "upstream expectation adds output absent from the source program",
    "76": "upstream expectation adds output absent from the source program",
    "85": "x86 inline assembly",
    "96": "diagnostic-driver test (-dt), not a native program",
    "98": "i386 register-extension ABI test",
    "99": "i386 fastcall ABI test",
    "104": "multi-translation-unit inline/linker test",
    "112": "TCC backtrace/bounds runtime",
    "113": "TCC shared-library/backtrace harness",
    "114": "TCC bounds runtime",
    "115": "TCC bounds runtime",
    "116": "TCC bounds runtime",
    "117": "TCC bounds runtime invocation",
    "120": "multi-translation-unit alias/linker test",
    "125": "diagnostic-driver test (-dt), not a native program",
    "126": "TCC bounds runtime",
    "127": "x86 inline assembly and asm goto",
    "128": "diagnostic-driver multi-run test (-dt), not a native program",
    "132": "TCC bounds runtime invocation",
    "138": "AArch64 encoding test",
    "139": "AArch64 diagnostic-driver test",
    "140": "AArch64 inline assembly",
    "141": "RISC-V inline assembly",
    "145": "Windows/AArch64 intrinsics",
    "146": "multi-translation-unit TLS linker test",
    "148": "ELF object/shared-library linker test",
}
TINYCC_ARGS = {"31": ["arg1", "arg2", "arg3", "arg4", "arg5"]}
TINYCC_LIBS = {"22": ["-lm"], "24": ["-lm"], "106": ["-lpthread"], "124": ["-lpthread"], "144": ["-lpthread"]}


@dataclasses.dataclass(frozen=True)
class Case:
    suite: str
    name: str
    source: pathlib.Path
    expected: bytes
    args: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    standard: str = ""


@dataclasses.dataclass
class Outcome:
    suite: str
    name: str
    standard: str
    status: str
    detail: str = ""
    seconds: float = 0.0


def run(command, *, cwd=ROOT, timeout=60, capture=True, merge_stderr=False):
    process = subprocess.Popen(command, cwd=cwd, start_new_session=True,
                               stdout=subprocess.PIPE if capture else None,
                               stderr=(subprocess.STDOUT if merge_stderr else subprocess.PIPE)
                               if capture else None)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        # coil launches a shell pipeline and parallel LLVM optimization jobs.
        # Killing only the immediate process leaks multi-gigabyte `opt` children.
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        error.output, error.stderr = stdout, stderr
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def checkout(name: str) -> pathlib.Path:
    url, revision = REPOSITORIES[name]
    destination = CACHE / f"{name}-{revision}"
    if (destination / ".git").is_dir():
        actual = run(["git", "rev-parse", "HEAD"], cwd=destination).stdout.decode().strip()
        if actual == revision:
            return destination
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=destination, check=True)
    subprocess.run(["git", "remote", "add", "origin", url], cwd=destination, check=True)
    subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", revision], cwd=destination, check=True)
    subprocess.run(["git", "checkout", "-q", "--detach", "FETCH_HEAD"], cwd=destination, check=True)
    actual = run(["git", "rev-parse", "HEAD"], cwd=destination).stdout.decode().strip()
    if actual != revision:
        raise RuntimeError(f"{name}: fetched {actual}, expected {revision}")
    return destination


def tinycc_cases(source_root: pathlib.Path) -> tuple[list[Case], dict[str, str]]:
    directory = source_root / "tests/tests2"
    cases = []
    skipped = {}
    for source in sorted(directory.glob("[0-9][0-9]*_*.c")):
        number = source.name.split("_", 1)[0]
        if "+" in source.name:
            continue
        if number in TINYCC_SKIPS:
            skipped[source.name] = TINYCC_SKIPS[number]
            continue
        expected_path = source.with_suffix(".expect")
        if not expected_path.exists():
            skipped[source.name] = "no upstream expected output"
            continue
        arguments = tuple(TINYCC_ARGS.get(number, ()))
        if number == "46":
            arguments = (r"[^* ]*[:a:d: ]+\:\*-/: $", str(source))
        expected = expected_path.read_bytes()
        # tests2 .expect files occasionally prefix runtime output with diagnostics
        # emitted by TCC's compile step. This harness scores program behavior, so
        # compare only the runtime portion rather than skipping otherwise-valid tests.
        expected = re.sub(rb"^(?:[^\r\n]+\.c:\d+: (?:warning|error|note):[^\r\n]*\r?\n)+", b"", expected)
        cases.append(Case("tinycc", source.name, source, expected,
                          arguments, tuple(TINYCC_LIBS.get(number, ()))))
    return cases, skipped


def ctests_cases(source_root: pathlib.Path) -> tuple[list[Case], dict[str, str]]:
    directory = source_root / "tests/single-exec"
    cases = []
    skipped = {}
    for source in sorted(directory.glob("*.c")):
        tags_path = source.with_suffix(".c.tags")
        tags = set(tags_path.read_text().split()) if tags_path.exists() else set()
        if "portable" not in tags or not tags.intersection(("c89", "c99", "c11")):
            skipped[source.name] = "not tagged portable C89/C99/C11"
            continue
        standard = "c89" if "c89" in tags else ("c99" if "c99" in tags else "c11")
        expected_path = source.with_suffix(".c.expected")
        expected = expected_path.read_bytes() if expected_path.exists() else b""
        cases.append(Case("c-testsuite", source.name, source, expected, standard=standard))
    return cases, skipped


def stage_local_includes(source: pathlib.Path, destination: pathlib.Path, seen: set[pathlib.Path]) -> None:
    source = source.resolve()
    if source in seen:
        return
    seen.add(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    text = source.read_text(errors="replace")
    for include in re.findall(r'^\s*#\s*include\s+"([^"]+)"', text, re.MULTILINE):
        dependency = (source.parent / include).resolve()
        if dependency.is_file():
            stage_local_includes(dependency, destination.parent / include, seen)


def execute_case(case: Case, coil: str, work: pathlib.Path) -> Outcome:
    started = time.monotonic()
    case_dir = work / case.suite / case.name.removesuffix(".c")
    case_dir.mkdir(parents=True, exist_ok=True)
    source_dir = case_dir / "tests2" if case.suite == "tinycc" else case_dir
    source_dir.mkdir(parents=True, exist_ok=True)
    executable = case_dir / "program"
    for header in case.source.parent.glob("*.h"):
        shutil.copy2(header, source_dir / header.name)
    staged_source = source_dir / case.source.name
    stage_local_includes(case.source, staged_source, set())
    command = [coil, "build", str(staged_source), "--use", "experiments.c.lang", "-O3", "-o", str(executable), *case.flags]
    try:
        built = run(command, timeout=90)
    except subprocess.TimeoutExpired:
        return Outcome(case.suite, case.name, case.standard, "compile-timeout", seconds=time.monotonic()-started)
    if built.returncode:
        diagnostic = (built.stderr or built.stdout).decode(errors="replace")
        detail = diagnostic.replace(str(work), "{work}").strip().splitlines()
        return Outcome(case.suite, case.name, case.standard, "compile-fail",
                       detail[-1][:240] if detail else f"exit {built.returncode}", time.monotonic()-started)
    try:
        arguments = tuple(case.source.name if value == str(case.source) else value for value in case.args)
        result = run([str(executable), *arguments], cwd=source_dir, timeout=15,
                     merge_stderr=True)
    except subprocess.TimeoutExpired:
        return Outcome(case.suite, case.name, case.standard, "run-timeout", seconds=time.monotonic()-started)
    output = result.stdout
    if result.returncode:
        return Outcome(case.suite, case.name, case.standard, "run-fail", f"exit {result.returncode}", time.monotonic()-started)
    if output != case.expected:
        return Outcome(case.suite, case.name, case.standard, "output-mismatch",
                       f"expected {len(case.expected)} bytes, got {len(output)}", time.monotonic()-started)
    return Outcome(case.suite, case.name, case.standard, "pass", seconds=time.monotonic()-started)


def summary(outcomes: list[Outcome], skipped: dict[str, dict[str, str]]) -> dict:
    result = {"revisions": {name: revision for name, (_, revision) in REPOSITORIES.items()}, "suites": {}}
    for suite in sorted({o.suite for o in outcomes} | set(skipped)):
        selected = [o for o in outcomes if o.suite == suite]
        counts = {}
        for outcome in selected:
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
        passed = counts.get("pass", 0)
        total = len(selected)
        by_standard = {}
        for standard in sorted({o.standard for o in selected if o.standard}):
            group = [o for o in selected if o.standard == standard]
            group_passed = sum(o.status == "pass" for o in group)
            by_standard[standard] = {"passed": group_passed, "applicable": len(group),
                                     "percent": round(100 * group_passed / len(group), 1)}
        result["suites"][suite] = {
            "passed": passed, "applicable": total,
            "percent": round(100 * passed / total, 1) if total else 0,
            "status_counts": counts, "skipped": len(skipped.get(suite, {})),
            "by_standard": by_standard,
            "failures": [dataclasses.asdict(o) for o in selected if o.status != "pass"],
            "skip_reasons": skipped.get(suite, {}),
        }
    return result


def markdown(report: dict) -> str:
    lines = ["# C frontend conformance baseline", "",
             "This is a reproducible corpus pass rate, not an ISO conformance percentage.", "",
             "| Suite | Revision | Passed | Applicable | Pass rate | Explicit skips |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for name, data in report["suites"].items():
        lines.append(f"| {name} | `{report['revisions'][name]}` | {data['passed']} | {data['applicable']} | {data['percent']:.1f}% | {data['skipped']} |")
    for name, data in report["suites"].items():
        lines += ["", f"## {name}", ""]
        if data["by_standard"]:
            for standard, group in data["by_standard"].items():
                lines.append(f"- {standard}: {group['passed']}/{group['applicable']} ({group['percent']:.1f}%)")
        lines.append("- outcomes: " + ", ".join(f"{key}={value}" for key, value in sorted(data["status_counts"].items())))
        lines.append(f"- explicit non-frontend/platform skips: {data['skipped']}")
        if data["failures"]:
            lines += ["", "### Failures", "", "| Test | Result | Detail |", "| --- | --- | --- |"]
            for failure in data["failures"]:
                detail = failure["detail"].replace("|", "\\|")
                lines.append(f"| `{failure['name']}` | {failure['status']} | {detail} |")
    lines += ["", "Regenerate with:", "", "```sh", "python3 scripts/c-conformance.py --suite all --write-report tests/c/conformance/BASELINE.md", "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("tinycc", "c-testsuite", "all"), default="all")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--write-report", type=pathlib.Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    coil = shutil.which("coil")
    if not coil:
        raise SystemExit("coil is required")
    names = list(REPOSITORIES) if args.suite == "all" else [args.suite]
    cases = []
    skipped = {}
    for name in names:
        source = checkout(name)
        selected, omitted = tinycc_cases(source) if name == "tinycc" else ctests_cases(source)
        cases.extend(selected)
        skipped[name] = omitted
    with tempfile.TemporaryDirectory(prefix="c-conformance-", dir=ROOT / "build") as raw_work:
        work = pathlib.Path(raw_work)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(execute_case, case, coil, work) for case in cases]
            outcomes = []
            for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
                outcomes.append(future.result())
                if completed % 25 == 0 or completed == len(futures):
                    print(f"conformance: {completed}/{len(futures)}", file=sys.stderr, flush=True)
    outcomes.sort(key=lambda outcome: (outcome.suite, outcome.name))
    report = summary(outcomes, skipped)
    text = markdown(report)
    print(json.dumps(report, indent=2) if args.json else text)
    if args.write_report:
        destination = args.write_report if args.write_report.is_absolute() else ROOT / args.write_report
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)


if __name__ == "__main__":
    main()
