#!/usr/bin/env python3
"""Run the pinned Carp corpus against a Carp-compatible compiler driver.

This is repository-development tooling only. The Carp implementation and every
compiler phase remain Coil code; no generated program invokes this harness.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import difflib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests" / "carp" / "corpus.tsv"


@dataclasses.dataclass(frozen=True)
class Case:
    index: int
    kind: str
    source: str
    expected: str | None


@dataclasses.dataclass
class Outcome:
    index: int
    kind: str
    source: str
    passed: bool
    stage: str
    seconds: float
    command: list[str]
    log: str
    detail: str = ""


def parse_manifest(path: Path) -> list[Case]:
    cases: list[Case] = []
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw or raw.startswith("#"):
            continue
        fields = raw.split("\t")
        if len(fields) != 3:
            raise SystemExit(f"{path}:{line_number}: expected three tab-separated fields")
        kind, source, expected = fields
        if kind not in {"output", "run", "reject", "build", "build-no-core"}:
            raise SystemExit(f"{path}:{line_number}: unknown case kind {kind!r}")
        cases.append(Case(len(cases), kind, source, None if expected == "-" else expected))
    if not cases:
        raise SystemExit(f"{path}: corpus is empty")
    return cases


def safe_name(case: Case) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in case.source)
    return f"{case.index:03d}-{cleaned}"


def invoke(
    command: list[str],
    cwd: Path,
    timeout: float,
    log_path: Path,
    env_overrides: dict[str, str] | None = None,
) -> tuple[int, bytes, str]:
    try:
        environment = os.environ.copy()
        environment.update(env_overrides or {})
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env=environment,
        )
        log_path.write_bytes(completed.stdout)
        return completed.returncode, completed.stdout, ""
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"")
        log_path.write_bytes(output)
        return 124, output, f"timeout after {timeout:g}s"
    except OSError as error:
        message = f"unable to execute compiler: {error}"
        log_path.write_text(message + "\n")
        return 127, b"", message


def run_case(
    case: Case,
    compiler: list[str],
    carp_root: Path,
    core: Path,
    out: Path,
    timeout: float,
    mode: str,
    provider: str,
    registry: str,
) -> Outcome:
    started = time.monotonic()
    name = safe_name(case)
    log_path = out / "logs" / f"{name}.log"
    binary = out / "bin" / name
    c_output = out / "c" / f"{name}.c"
    source = carp_root / case.source
    case_workdir = out / "work" / name

    env_overrides: dict[str, str] = {}
    if mode == "coil":
        env_overrides["COIL_CARP_REGISTRY"] = registry
        if case.kind == "build-no-core":
            env_overrides["COIL_CARP_NO_CORE"] = "1"
        common = [str(source), "--use", provider]
        if case.kind in {"output", "run", "build", "build-no-core"}:
            command = compiler + ["build", *common, "-o", str(binary)]
        else:
            command = compiler + ["build", *common, "-o", str(binary)]
    else:
        case_workdir.mkdir(parents=True, exist_ok=True)
        env_overrides["CARP_DIR"] = str(carp_root)
        output_directory = str(case_workdir / "out")
        configured = [
            "--eval-preload",
            f'(Project.config "output-directory" "{output_directory}")',
        ]
        if case.kind == "output":
            command = compiler + [*configured, "-b", "--log-memory", str(source)]
        elif case.kind == "run":
            command = compiler + [*configured, "-b", "--log-memory", str(source)]
        elif case.kind == "reject":
            command = compiler + [*configured, "--check", str(source)]
        elif case.kind == "build":
            command = compiler + [*configured, "-b", str(source)]
        else:
            command = compiler + ["-b", "--no-core", str(source)]
        binary = case_workdir / "out" / "main"

    if mode == "coil":
        compiler_cwd = ROOT
    elif case.kind == "build-no-core":
        compiler_cwd = case_workdir
    else:
        compiler_cwd = carp_root
    status, compiler_output, detail = invoke(
        command, compiler_cwd, timeout, log_path, env_overrides
    )
    stage = "compile"
    if case.kind == "reject":
        # Current Carp's --check reports diagnostics but deliberately exits 0.
        # Coil uses a conventional nonzero compile status. In either mode a
        # rejection must have observable diagnostic output or failure status.
        passed = status != 0 or (mode == "carp" and bool(compiler_output.strip()))
    else:
        passed = status == 0

    if mode == "carp" and case.kind in {"output", "run", "build", "build-no-core"} and passed:
        products = sorted(
            path
            for path in (case_workdir / "out").glob("*")
            if path.is_file() and os.access(path, os.X_OK)
        )
        if len(products) == 1:
            binary = products[0]
        elif not products:
            passed = False
            detail = "compiler succeeded without producing an executable"
        else:
            passed = False
            detail = "compiler produced multiple executable candidates"

    if case.kind in {"build", "build-no-core"} and passed:
        if not binary.is_file():
            passed = False
            detail = "compiler succeeded without producing a linkable executable"

    if case.kind == "run" and passed:
        stage = "run"
        run_log = out / "logs" / f"{name}.actual"
        run_status, _, run_detail = invoke([str(binary)], carp_root, timeout, run_log)
        if run_status != 0:
            passed = False
            detail = run_detail or f"program exited {run_status}"

    if case.kind == "output" and passed:
        stage = "run"
        run_log = out / "logs" / f"{name}.actual"
        run_status, actual, run_detail = invoke([str(binary)], carp_root, timeout, run_log)
        if run_status != 0:
            passed = False
            detail = run_detail or f"program exited {run_status}"
        else:
            stage = "output"
            expected_path = carp_root / (case.expected or "")
            expected = expected_path.read_bytes()
            if actual != expected:
                passed = False
                diff = "".join(
                    difflib.unified_diff(
                        expected.decode(errors="replace").splitlines(keepends=True),
                        actual.decode(errors="replace").splitlines(keepends=True),
                        fromfile=str(expected_path),
                        tofile=str(run_log),
                    )
                )
                detail = diff[:12000]

    if not passed and not detail:
        if case.kind == "reject":
            detail = "compiler accepted an expected-rejection case"
        else:
            detail = f"compiler exited {status}"

    return Outcome(
        index=case.index,
        kind=case.kind,
        source=case.source,
        passed=passed,
        stage=stage,
        seconds=time.monotonic() - started,
        command=command,
        log=str(log_path),
        detail=detail,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", required=True, help="Carp-compatible command, shell-quoted")
    parser.add_argument("--carp-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--mode", choices=("carp", "coil"), default="carp")
    parser.add_argument("--provider", default="experiments.carp.lang")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    cases = parse_manifest(args.manifest)
    if args.list:
        for case in cases:
            print(f"{case.kind}\t{case.source}")
        print(f"total\t{len(cases)}")
        return 0

    carp_root = args.carp_root.resolve()
    core = (args.core or carp_root / "core").resolve()
    for required in (carp_root, core):
        if not required.is_dir():
            raise SystemExit(f"not a directory: {required}")
    compiler = shlex.split(args.compiler)
    if not compiler:
        raise SystemExit("--compiler must not be empty")
    registry = ":".join(str(path.resolve()) for path in sorted(core.glob("*.carp")))

    if args.out:
        out = args.out.resolve()
        out.mkdir(parents=True, exist_ok=True)
    else:
        out = Path(tempfile.mkdtemp(prefix="coil-carp-progress-"))
    for child in ("logs", "bin", "c"):
        (out / child).mkdir(exist_ok=True)

    outcomes: list[Outcome] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(
                run_case,
                case,
                compiler,
                carp_root,
                core,
                out,
                args.timeout,
                args.mode,
                args.provider,
                registry,
            )
            for case in cases
        ]
        for future in concurrent.futures.as_completed(futures):
            outcome = future.result()
            outcomes.append(outcome)
            verdict = "PASS" if outcome.passed else "FAIL"
            print(f"{verdict} {outcome.kind:13} {outcome.source} ({outcome.seconds:.2f}s)", flush=True)

    outcomes.sort(key=lambda outcome: outcome.index)
    by_kind: dict[str, dict[str, int]] = {}
    for outcome in outcomes:
        counts = by_kind.setdefault(outcome.kind, {"passed": 0, "failed": 0, "total": 0})
        counts["total"] += 1
        counts["passed" if outcome.passed else "failed"] += 1
    passed = sum(outcome.passed for outcome in outcomes)
    total = len(outcomes)
    summary = {
        "passed": passed,
        "failed": total - passed,
        "total": total,
        "compatibility_percent": round(100.0 * passed / total, 2),
        "by_kind": by_kind,
        "outcomes": [dataclasses.asdict(outcome) for outcome in outcomes],
    }
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"passed={passed} failed={total - passed} total={total} "
        f"compatibility={summary['compatibility_percent']:.2f}% out={out}"
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
