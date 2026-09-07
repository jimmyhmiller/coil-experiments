#!/usr/bin/env bash
# Phase G: a cooperative computation captured mid-flight in one process and
# resumed to completion in another. Not Python; a test harness only.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
coil="${COIL:-coil}"
bin="build/image-coop-demo"
img="$(mktemp -t coil-coop.XXXXXX).coilimage"
trap 'rm -f "$img"' EXIT

echo "building $bin"
"$coil" build src/experiments/image/coop_demo.coil -o "$bin"

echo "process 1: run 5 turns, park, image"
s1="$("$bin" save "$img")"; echo "  $s1"
[ "$s1" = "SAVE-OK i=5 acc=10 n=10" ] || { echo "FAIL: save"; exit 1; }

echo "process 2: reload and finish"
s2="$("$bin" resume "$img")"; echo "  $s2"
[ "$s2" = "COOP-OK i=10 acc=45 n=10" ] || { echo "FAIL: resume"; exit 1; }

echo "PASS: cooperative computation resumed across processes"
