#!/usr/bin/env python3
"""Measure the real Emacs build and its complete live process tree."""
import argparse
import json
import pathlib
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--backend", default="arm64")
    args = parser.parse_args()
    directory = pathlib.Path(tempfile.mkdtemp(prefix="emacs-generated-measure-"))
    command = [str(pathlib.Path(args.compiler).resolve()), "build", "-O0",
               "--backend", args.backend, "-o", str(directory / "emacs")]
    peak_tree = peak_process = peak_parent = 0
    peak_owner = ""
    started = time.monotonic()
    with (directory / "build.stdout").open("w") as output, (directory / "build.stderr").open("w") as error:
        process = subprocess.Popen(command, cwd=ROOT / "src/apps/emacs", stdout=output, stderr=error)
        print(json.dumps({"directory": str(directory), "pid": process.pid, "command": command}), flush=True)
        next_status = started
        while process.poll() is None:
            rows = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss=,comm="], text=True)
            entries = {}
            for row in rows.splitlines():
                fields = row.split(None, 3)
                if len(fields) == 4:
                    entries[int(fields[0])] = (int(fields[1]), int(fields[2]) * 1024, fields[3])
            tree = {process.pid}
            while True:
                larger = tree | {pid for pid, (parent, _, _) in entries.items() if parent in tree}
                if larger == tree:
                    break
                tree = larger
            live = [(pid, entries[pid]) for pid in tree if pid in entries]
            total = sum(entry[1] for _, entry in live)
            peak_tree = max(peak_tree, total)
            peak_parent = max(peak_parent, entries.get(process.pid, (0, 0, ""))[1])
            for pid, (_, rss, name) in live:
                if rss > peak_process:
                    peak_process, peak_owner = rss, f"{pid} {name}"
            now = time.monotonic()
            if now >= next_status:
                print(json.dumps({"elapsed_s": round(now - started, 2), "rss_bytes": total,
                                  "peak_tree_rss_bytes": peak_tree}), flush=True)
                next_status = now + 10
            time.sleep(0.1)
        artifact = directory / "emacs"
        artifact_ready = artifact.is_file() and artifact.stat().st_size > 0
        result = {"command": command, "exit_status": process.returncode,
                  "artifact_ready": artifact_ready,
                  "elapsed_s": round(time.monotonic() - started, 3),
                  "peak_tree_rss_bytes": peak_tree, "peak_parent_rss_bytes": peak_parent,
                  "peak_process_rss_bytes": peak_process, "peak_process": peak_owner,
                  "sampling_interval_s": 0.1, "directory": str(directory)}
        (directory / "measurement.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    print((directory / "build.stdout").read_text()[-8000:])
    print((directory / "build.stderr").read_text()[-8000:])
    return process.returncode if process.returncode else (0 if artifact_ready else 1)


if __name__ == "__main__":
    raise SystemExit(main())
