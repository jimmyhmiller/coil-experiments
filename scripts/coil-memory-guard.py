#!/usr/bin/env python3
"""Bound a Coil command's whole process tree and preserve a useful RSS trace.

This is repository-development tooling for compiler processes, which a program
metaprogram cannot instrument. Production allocation tracing lives in Coil.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def process_rows():
    output = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,rss=,comm="], text=True
    )
    for line in output.splitlines():
        fields = line.strip().split(None, 3)
        if len(fields) == 4 and all(part.isdigit() for part in fields[:3]):
            yield int(fields[0]), int(fields[1]), int(fields[2]), fields[3]


def descendants(root, rows):
    family = {root}
    while True:
        enlarged = family | {pid for pid, parent, _, _ in rows if parent in family}
        if enlarged == family:
            return [row for row in rows if row[0] in family]
        family = enlarged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-mib", type=int, default=2048)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--log", type=Path, default=Path("/tmp/coil-memory-guard.log"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.limit_mib <= 0 or args.interval <= 0:
        parser.error("provide a command, positive limit, and positive interval")

    with args.log.open("w") as log:
        process = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        started = time.monotonic()
        peak = 0
        exceeded = False
        print(f"guard pid={process.pid} limit={args.limit_mib} MiB log={args.log}", flush=True)
        while process.poll() is None:
            members = descendants(process.pid, list(process_rows()))
            rss_kib = sum(row[2] for row in members)
            peak = max(peak, rss_kib)
            print(
                f"{time.monotonic() - started:.1f}s rss={rss_kib / 1024:.1f} MiB "
                f"peak={peak / 1024:.1f} MiB "
                + " ".join(f"{pid}:{rss / 1024:.0f}MiB:{name}" for pid, _, rss, name in members),
                flush=True,
            )
            if rss_kib >= args.limit_mib * 1024:
                exceeded = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(args.interval)
        status = process.wait()
    print(f"exit={status} peak={peak / 1024:.1f} MiB log={args.log}", flush=True)
    return 124 if exceeded else status


if __name__ == "__main__":
    sys.exit(main())
