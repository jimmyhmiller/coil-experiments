#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: scripts/safety-check.sh FILE.coil [coil arguments...]" >&2
  exit 2
fi

safety_entry=$1
shift

# Sanitizer modes are mutually exclusive, so compile separate instrumented
# objects. `coil check` stops before code generation and therefore cannot prove
# that the requested checks were actually emitted.
safety_ubsan_object=$(mktemp /tmp/coil-safety-ubsan.o.XXXXXX)
safety_debug_object=$(mktemp /tmp/coil-safety-debug.o.XXXXXX)
trap 'rm -f "$safety_ubsan_object" "$safety_debug_object"' EXIT HUP INT TERM

coil emit-obj "$safety_entry" -o "$safety_ubsan_object" --sanitize=undefined "$@"
coil emit-obj "$safety_entry" -o "$safety_debug_object" --debug-runtime "$@"

echo "safety code generation passed: undefined behavior and debug runtime + address sanitizer"
echo "CI should additionally check --sanitize=thread and, on Linux, --sanitize=memory."
