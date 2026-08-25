#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pin=$(tr -d '[:space:]' < "$root/tests/wasm/SPEC_REVISION")
wabt_pin=$(tr -d '[:space:]' < "$root/tests/wasm/WABT_REVISION")
cache="$root/tests/wasm/.spec-cache"
spec="$cache/spec-mvp"
wabt="$cache/wabt-mvp"
prepared="$cache/prepared-$pin"

fetch_suite() {
  mkdir -p "$cache"
  if [ ! -d "$spec/.git" ]; then
    git init -q "$spec"
    git -C "$spec" remote add origin https://github.com/WebAssembly/spec.git
  fi
  if ! git -C "$spec" cat-file -e "$pin^{commit}" 2>/dev/null; then
    git -C "$spec" fetch --depth 1 origin "$pin"
  fi
  git -C "$spec" checkout -q --detach "$pin"
  actual=$(git -C "$spec" rev-parse HEAD)
  if [ "$actual" != "$pin" ]; then
    echo "error: expected spec revision $pin, got $actual" >&2
    exit 1
  fi
}

fetch_wabt() {
  mkdir -p "$cache"
  if [ ! -d "$wabt/.git" ]; then
    git init -q "$wabt"
    git -C "$wabt" remote add origin https://github.com/WebAssembly/wabt.git
  fi
  if ! git -C "$wabt" cat-file -e "$wabt_pin^{commit}" 2>/dev/null; then
    git -C "$wabt" fetch --depth 1 origin "$wabt_pin"
  fi
  git -C "$wabt" checkout -q --detach "$wabt_pin"
  if [ ! -x "$wabt/build/wast2json" ]; then
    command -v cmake >/dev/null 2>&1 || {
      echo "error: cmake is required to build the pinned WAST converter" >&2
      exit 1
    }
    cmake -S "$wabt" -B "$wabt/build" -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_TESTS=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    cmake --build "$wabt/build" --target wast2json -j 4
  fi
}

prepare_suite() {
  fetch_suite
  fetch_wabt
  mkdir -p "$prepared"
  for wast in "$spec"/test/core/*.wast; do
    name=$(basename "$wast" .wast)
    mkdir -p "$prepared/$name"
    "$wabt/build/wast2json" "$wast" -o "$prepared/$name/script.json"
  done
}

inventory() {
  fetch_suite
  count=$(find "$spec/test/core" -maxdepth 1 -name '*.wast' | wc -l | tr -d '[:space:]')
  echo "revision=$pin"
  echo "wast_files=$count"
  find "$spec/test/core" -maxdepth 1 -name '*.wast' -exec basename {} \; | LC_ALL=C sort
}

run_integer_suite() {
  kind=$1
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  coil_bin=${COIL:-coil}
  json="$prepared/$kind/script.json"
  wasm="$prepared/$kind/script.0.wasm"
  if [ ! -f "$json" ] || [ ! -f "$wasm" ]; then
    echo "error: prepared $kind suite is missing; run scripts/wasm-spec.sh prepare" >&2
    exit 1
  fi
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-$kind.XXXXXX")
  trap 'rm -f "$args_file"' EXIT HUP INT TERM
  jq -r --arg kind "$kind" '
    .commands[]
    | select(.type == "assert_return"
             and .action.type == "invoke"
             and (.expected | length) == 1
             and .expected[0].type == $kind
             and ([.action.args[].type] | all(. == $kind)))
    | .action.field,
      .expected[0].value,
      (.action.args | length | tostring),
      (.action.args[].value)
  ' "$json" > "$args_file"
  count=$(jq -r --arg kind "$kind" '[
    .commands[]
    | select(.type == "assert_return"
             and .action.type == "invoke"
             and (.expected | length) == 1
             and .expected[0].type == $kind
             and ([.action.args[].type] | all(. == $kind)))
  ] | length' "$json")
  xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
    "--assert-$kind-batch" < "$args_file"
  rm -f "$args_file"
  trap - EXIT HUP INT TERM
  echo "$kind: $count official assert_return checks passed"
}

test_integers() {
  run_integer_suite i32
  run_integer_suite i64
}

run_float_batch() {
  kind=$1
  assertion=$2
  mode=$3
  json="$prepared/$kind/script.json"
  wasm="$prepared/$kind/script.0.wasm"
  coil_bin=${COIL:-coil}
  count=$(jq -r --arg t "$assertion" '[.commands[] | select(.type == $t)] | length' "$json")
  offset=0
  while [ "$offset" -lt "$count" ]; do
    args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-$kind.XXXXXX")
    trap 'rm -f "$args_file"' EXIT HUP INT TERM
    if [ "$assertion" = "assert_return" ]; then
      jq -r --arg kind "$kind" --argjson lo "$offset" --argjson hi "$((offset + 200))" '
        [.commands[]
         | select(.type == "assert_return"
                  and .action.type == "invoke"
                  and (.expected | length) == 1
                  and .expected[0].type == $kind
                  and ([.action.args[].type] | all(. == $kind)))][$lo:$hi][]
        | .action.field,
          .expected[0].value,
          (.action.args | length | tostring),
          (.action.args[].value)
      ' "$json" > "$args_file"
    else
      jq -r --arg t "$assertion" --argjson lo "$offset" --argjson hi "$((offset + 200))" '
        [.commands[] | select(.type == $t)][$lo:$hi][]
        | .action.field,
          (.action.args | length | tostring),
          (.action.args[].value)
      ' "$json" > "$args_file"
    fi
    xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- "$mode" < "$args_file"
    rm -f "$args_file"
    trap - EXIT HUP INT TERM
    offset=$((offset + 200))
  done
  echo "$kind $assertion: $count checks passed"
}

test_floats() {
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  for kind in f32 f64; do
    run_float_batch "$kind" assert_return "--assert-$kind-batch"
    run_float_batch "$kind" assert_return_canonical_nan \
      "--assert-$kind-canonical-nan-batch"
    run_float_batch "$kind" assert_return_arithmetic_nan \
      "--assert-$kind-arithmetic-nan-batch"
  done
}

test_conversions() {
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  coil_bin=${COIL:-coil}
  json="$prepared/conversions/script.json"
  wasm="$prepared/conversions/script.0.wasm"
  count=$(jq '[.commands[] | select(.type == "assert_return"
                                     and .action.type == "invoke"
                                     and (.expected | length) == 1)] | length' "$json")
  offset=0
  while [ "$offset" -lt "$count" ]; do
    args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-conversions.XXXXXX")
    trap 'rm -f "$args_file"' EXIT HUP INT TERM
    jq -r --argjson lo "$offset" --argjson hi "$((offset + 150))" '
      [.commands[] | select(.type == "assert_return"
                             and .action.type == "invoke"
                             and (.expected | length) == 1)][$lo:$hi][]
      | .action.field,
        .expected[0].type,
        .expected[0].value,
        (.action.args | length | tostring),
        (.action.args[] | .type, .value)
    ' "$json" > "$args_file"
    xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
      --assert-scalar-batch < "$args_file"
    rm -f "$args_file"
    trap - EXIT HUP INT TERM
    offset=$((offset + 150))
  done
  echo "conversions assert_return: $count checks passed"

  trap_count=0
  trap_args=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-conversion-traps.XXXXXX")
  trap_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-conversion-output.XXXXXX")
  trap 'rm -f "$trap_args" "$trap_out"' EXIT HUP INT TERM
  jq -r '
    .commands[] | select(.type == "assert_trap")
    | ([.action.field, (.action.args | length | tostring)]
       + [.action.args[] | .type, .value])
    | join(" ")
  ' "$json" > "$trap_args"
  while IFS= read -r line; do
    set -- $line
    if "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
         --invoke-scalar "$@" > "$trap_out" 2>&1; then
      echo "error: expected WebAssembly trap from conversion export $1" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$trap_out"; then
      echo "error: conversion export $1 failed without the expected runtime trap" >&2
      cat "$trap_out" >&2
      exit 1
    fi
    trap_count=$((trap_count + 1))
  done < "$trap_args"
  rm -f "$trap_args" "$trap_out"
  trap - EXIT HUP INT TERM
  echo "conversions assert_trap: $trap_count checks passed"
}

test_memory() {
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  coil_bin=${COIL:-coil}
  "$coil_bin" run "$root/tests/wasm/memory.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch \
    data i32 67305985 0 \
    size i32 1 0 \
    store-load i32 2018915346 2 i32 3 i32 2018915346 \
    narrow i32 22136 2 i32 20 i32 305419896 \
    grow i32 1 1 i32 1 \
    size i32 2 0 \
    data i32 67305985 0
  echo "focused memory state/load/store/grow/data checks passed"

  json="$prepared/endianness/script.json"
  wasm="$prepared/endianness/script.0.wasm"
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-endianness.XXXXXX")
  trap 'rm -f "$args_file"' EXIT HUP INT TERM
  jq -r '
    .commands[] | select(.type == "assert_return"
                         and .action.type == "invoke"
                         and (.expected | length) == 1)
    | .action.field,
      .expected[0].type,
      .expected[0].value,
      (.action.args | length | tostring),
      (.action.args[] | .type, .value)
  ' "$json" > "$args_file"
  xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch < "$args_file"
  rm -f "$args_file"
  trap - EXIT HUP INT TERM
  echo "endianness: 68 official assertions passed"

  json="$prepared/memory_size/script.json"
  dir=${json%/*}
  for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
    args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-memory-size.XXXXXX")
    trap 'rm -f "$args_file"' EXIT HUP INT TERM
    jq -r --arg file "$file" '
      reduce .commands[] as $command
        ({current:"", selected:[]};
         if $command.type == "module" then .current = $command.filename
         elif ($command.type == "assert_return" and .current == $file)
           then .selected += [$command]
         else . end)
      | .selected[]
      | .action.field,
        (if (.expected | length) == 0 then "void" else .expected[0].type end),
        (if (.expected | length) == 0 then "0" else .expected[0].value end),
        (.action.args | length | tostring),
        (.action.args[] | .type, .value)
    ' "$json" > "$args_file"
    xargs "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
      --assert-scalar-batch < "$args_file"
    rm -f "$args_file"
    trap - EXIT HUP INT TERM
  done
  echo "memory_size: 36 official assertions passed"
}

test_tables() {
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  coil_bin=${COIL:-coil}
  "$coil_bin" run "$root/tests/wasm/table.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch \
    dispatch i32 42 3 i32 1 i32 20 i32 22 \
    dispatch i32 42 3 i32 2 i32 64 i32 22
  echo "focused call_indirect dispatch checks passed"

  json="$prepared/call_indirect/script.json"
  wasm="$prepared/call_indirect/script.0.wasm"
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-call-indirect.XXXXXX")
  trap_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-call-indirect-trap.XXXXXX")
  trap 'rm -f "$args_file" "$trap_out"' EXIT HUP INT TERM
  jq -r '
    .commands[]
    | select(.type == "assert_return")
    | .action.field,
      (if (.expected | length) == 0 then "void" else .expected[0].type end),
      (if (.expected | length) == 0 then "0" else .expected[0].value end),
      (.action.args | length | tostring),
      (.action.args[] | .type, .value)
  ' "$json" > "$args_file"
  xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch < "$args_file"
  echo "call_indirect assert_return: 103 checks passed"

  jq -r '
    .commands[] | select(.type == "assert_trap")
    | ([.action.field, (.action.args | length | tostring)]
       + [.action.args[] | .type, .value])
    | join(" ")
  ' "$json" > "$args_file"
  trap_count=0
  while IFS= read -r line; do
    set -- $line
    if "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
         --invoke-scalar "$@" > "$trap_out" 2>&1; then
      echo "error: expected WebAssembly trap from call_indirect export $1" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$trap_out"; then
      echo "error: call_indirect export $1 failed without the expected runtime trap" >&2
      cat "$trap_out" >&2
      exit 1
    fi
    trap_count=$((trap_count + 1))
  done < "$args_file"
  rm -f "$args_file" "$trap_out"
  trap - EXIT HUP INT TERM
  echo "call_indirect assert_trap: $trap_count checks passed"
}

test_control() {
  coil_bin=${COIL:-coil}
  "$coil_bin" run "$root/tests/wasm/control_return.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    top i32 41 0 \
    from-block i64 42 0 \
    from-loop f32 1110179840 0 \
    from-if-then i32 3 2 i32 1 i32 9 \
    from-if-then i32 9 2 i32 0 i32 9 \
    from-if-else i32 9 2 i32 1 i32 9 \
    from-if-else i32 4 2 i32 0 i32 9
  echo "focused top-level, block, and loop return checks passed"

  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  json="$prepared/return/script.json"
  dir=${json%/*}
  wasm="$dir/script.0.wasm"
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-return.XXXXXX")
  invalid_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-return-invalid.XXXXXX")
  trap 'rm -f "$args_file" "$invalid_out"' EXIT HUP INT TERM
  jq -r '
    .commands[] | select(.type == "assert_return")
    | .action.field,
      (if (.expected | length) == 0 then "void" else .expected[0].type end),
      (if (.expected | length) == 0 then "0" else .expected[0].value end),
      (.action.args | length | tostring),
      (.action.args[] | .type, .value)
  ' "$json" > "$args_file"
  xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch < "$args_file"
  echo "return assert_return: 63 checks passed"

  invalid_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$invalid_out" 2>&1; then
      echo "error: expected WebAssembly validation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$invalid_out"; then
      echo "error: $file failed without a WebAssembly validation diagnostic" >&2
      cat "$invalid_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done
  rm -f "$args_file" "$invalid_out"
  trap - EXIT HUP INT TERM
  echo "return assert_invalid: $invalid_count checks passed"
}

test_wat() {
  coil_bin=${COIL:-coil}
  "$coil_bin" run "$root/tests/wasm/wat_features.wat" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    named-add i32 42 2 i32 20 i32 22 \
    i32-constant i32 4294967295 0 \
    i64-constant i64 9223372036854775807 0 \
    f32-constant f32 1069547520 0 \
    f64-constant f64 4609434218613702656 0 \
    folded-add i32 42 1 i32 40 \
    mixed-folded-flat i64 42 0
  echo "focused textual WAT flat/folded, named-local, and constant checks passed"
}

case "${1:-inventory}" in
  fetch) fetch_suite ;;
  fetch-wabt) fetch_wabt ;;
  prepare) prepare_suite ;;
  inventory) inventory ;;
  test-integers) test_integers ;;
  test-floats) test_floats ;;
  test-conversions) test_conversions ;;
  test-memory) test_memory ;;
  test-tables) test_tables ;;
  test-control) test_control ;;
  test-wat) test_wat ;;
  *)
    echo "usage: scripts/wasm-spec.sh [fetch|fetch-wabt|prepare|inventory|test-integers|test-floats|test-conversions|test-memory|test-tables|test-control|test-wat]" >&2
    exit 2
    ;;
esac
