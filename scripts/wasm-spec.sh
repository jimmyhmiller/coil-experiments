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
  "$coil_bin" run "$root/tests/wasm/control_br.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    branch i32 42 0 \
    outer-branch i32 43 0
  "$coil_bin" run "$root/tests/wasm/control_br_if.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    choose i32 9 1 i32 1 \
    choose i32 13 1 i32 0 \
    outer-choose i32 44 1 i32 1 \
    outer-choose i32 45 1 i32 0
  "$coil_bin" run "$root/tests/wasm/control_br_table.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    branch-table i32 42 1 i32 0 \
    branch-table i32 42 1 i32 10 \
    multi-target i32 43 1 i32 0 \
    multi-target i32 42 1 i32 1 \
    multi-target i32 42 1 i32 10
  "$coil_bin" run "$root/tests/wasm/control_loop.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    count i32 0 1 i32 0 \
    count i32 5 1 i32 5 \
    count i32 20 1 i32 20
  "$coil_bin" run "$root/tests/wasm/control_loop_value.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    unary i32 2 0 \
    binary i32 42 0
  "$coil_bin" run "$root/tests/wasm/control_loop_i64.wasm" \
    --use experiments.wasm.lang -- --assert-scalar-batch \
    before-loop i64 1 1 i64 0 \
    before-loop i64 120 1 i64 5
  echo "focused lexical branch, branch-table, and loop continuation checks passed"

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

test_loops() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  json="$prepared/loop/script.json"
  dir=${json%/*}
  wasm="$dir/script.0.wasm"
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-loop.XXXXXX")
  invalid_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-loop-invalid.XXXXXX")
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
  echo "loop assert_return: 66 checks passed"

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
  echo "loop assert_invalid: $invalid_count checks passed"
}

test_structured_control() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-control.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-control-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  invalid_total=0
  malformed_total=0
  trap_total=0

  for suite in block br br_if br_table if; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    wasm="$dir/script.0.wasm"
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
    count=$(jq -r '[.commands[] | select(.type == "assert_return")] | length' "$json")
    return_total=$((return_total + count))

    for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected WebAssembly validation failure from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WebAssembly validation:' "$failure_out"; then
        echo "error: $suite/$file failed without a WebAssembly validation diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      invalid_total=$((invalid_total + 1))
    done

    for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected malformed WAT rejection from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WAT reader:' "$failure_out"; then
        echo "error: $suite/$file failed without a WAT reader diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      malformed_total=$((malformed_total + 1))
    done

    jq -r '
      .commands[] | select(.type == "assert_trap")
      | ([.action.field, (.action.args | length | tostring)]
         + [.action.args[] | .type, .value])
      | join(" ")
    ' "$json" > "$args_file"
    while IFS= read -r line; do
      set -- $line
      if "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
           --invoke-scalar "$@" > "$failure_out" 2>&1; then
        echo "error: expected WebAssembly trap from $suite export $1" >&2
        exit 1
      fi
      if ! grep -q 'program terminated by signal 6' "$failure_out"; then
        echo "error: $suite export $1 failed without the expected runtime trap" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      trap_total=$((trap_total + 1))
    done < "$args_file"
  done

  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "structured control assert_return: $return_total checks passed"
  echo "structured control assert_invalid: $invalid_total checks passed"
  echo "structured control assert_malformed: $malformed_total checks passed"
  echo "structured control assert_trap: $trap_total checks passed"
}

test_start() {
  coil_bin=${COIL:-coil}
  dir="$prepared/start"
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-start-failure.XXXXXX")
  trap 'rm -f "$failure_out"' EXIT HUP INT TERM

  for file in 0 1 2; do
    if "$coil_bin" run "$dir/script.$file.wasm" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected invalid start module script.$file.wasm" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      echo "error: invalid start module lacked a validation diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
  done

  for file in 3 4; do
    "$coil_bin" run "$dir/script.$file.wasm" --use experiments.wasm.lang -- \
      --assert-scalar-batch \
      get i32 68 0 \
      inc void 0 0 \
      get i32 69 0 \
      inc void 0 0 \
      get i32 70 0
  done

  for file in 5 6 7; do
    "$coil_bin" run "$dir/script.$file.wasm" --use experiments.wasm.lang
  done

  if "$coil_bin" run "$dir/script.8.wasm" --use experiments.wasm.lang \
       > "$failure_out" 2>&1; then
    echo "error: expected trapping start function" >&2
    exit 1
  fi
  if ! grep -q 'program terminated by signal 6' "$failure_out"; then
    echo "error: start function failed without the expected runtime trap" >&2
    cat "$failure_out" >&2
    exit 1
  fi
  rm -f "$failure_out"
  trap - EXIT HUP INT TERM
  echo "start: 6 returns, 3 invalid modules, 1 instantiation trap passed"
  echo "start: imported spectest starts and action ordering passed"
}

test_basic_instructions() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-basic.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-basic-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  invalid_total=0
  trap_total=0

  for suite in nop break-drop switch local_get local_set local_tee call select unreachable; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    wasm="$dir/script.0.wasm"
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
    count=$(jq -r '[.commands[] | select(.type == "assert_return")] | length' "$json")
    return_total=$((return_total + count))

    for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected validation failure from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WebAssembly validation:' "$failure_out"; then
        echo "error: $suite/$file failed without a validation diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      invalid_total=$((invalid_total + 1))
    done

    jq -r '
      .commands[] | select(.type == "assert_trap")
      | ([.action.field, (.action.args | length | tostring)]
         + [.action.args[] | .type, .value])
      | join(" ")
    ' "$json" > "$args_file"
    while IFS= read -r line; do
      set -- $line
      if "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
           --invoke-scalar "$@" > "$failure_out" 2>&1; then
        echo "error: expected WebAssembly trap from $suite export $1" >&2
        exit 1
      fi
      if ! grep -q 'program terminated by signal 6' "$failure_out"; then
        echo "error: $suite export $1 failed without the expected runtime trap" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      trap_total=$((trap_total + 1))
    done < "$args_file"
  done

  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "basic instructions assert_return: $return_total checks passed"
  echo "basic instructions assert_invalid: $invalid_total checks passed"
  echo "basic instructions assert_trap: $trap_total checks passed"
}

test_evaluation_order() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-order.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-order-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  invalid_total=0

  for suite in labels left-to-right; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    wasm="$dir/script.0.wasm"
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
    count=$(jq -r '[.commands[] | select(.type == "assert_return")] | length' "$json")
    return_total=$((return_total + count))

    for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected validation failure from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WebAssembly validation:' "$failure_out"; then
        echo "error: $suite/$file failed without a validation diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      invalid_total=$((invalid_total + 1))
    done
  done

  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "evaluation order assert_return: $return_total checks passed"
  echo "evaluation order assert_invalid: $invalid_total checks passed"
}

test_functions() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-functions.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-functions-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  invalid_total=0
  malformed_total=0
  trap_total=0

  for suite in func forward fac unwind func_ptrs stack; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    for wasm in "$dir"/script.*.wasm; do
      file=${wasm##*/}
      jq -r --arg file "$file" '
        .commands
        | reduce .[] as $command
            ({current: "", selected: []};
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
      if [ -s "$args_file" ]; then
        xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
          --assert-scalar-batch < "$args_file"
      fi
    done
    count=$(jq -r '[.commands[] | select(.type == "assert_return")] | length' "$json")
    return_total=$((return_total + count))

    for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected validation failure from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WebAssembly validation:' "$failure_out"; then
        echo "error: $suite/$file failed without a validation diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      invalid_total=$((invalid_total + 1))
    done

    for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected malformed WAT rejection from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WAT reader:' "$failure_out"; then
        echo "error: $suite/$file failed without a WAT reader diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      malformed_total=$((malformed_total + 1))
    done

    jq -r '
      .commands
      | reduce .[] as $command
          ({current: "", selected: []};
           if $command.type == "module" then .current = $command.filename
           elif $command.type == "assert_trap"
           then .selected += [{file: .current, action: $command.action}]
           else . end)
      | .selected[]
      | ([.file, .action.field, (.action.args | length | tostring)]
         + [.action.args[] | .type, .value])
      | join(" ")
    ' "$json" > "$args_file"
    while IFS= read -r line; do
      set -- $line
      file=$1
      shift
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
           --invoke-scalar "$@" > "$failure_out" 2>&1; then
        echo "error: expected WebAssembly trap from $suite/$file export $1" >&2
        exit 1
      fi
      if ! grep -q 'program terminated by signal 6' "$failure_out"; then
        echo "error: $suite/$file export $1 failed without the expected runtime trap" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      trap_total=$((trap_total + 1))
    done < "$args_file"
  done

  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "functions assert_return: $return_total checks passed"
  echo "functions assert_invalid: $invalid_total checks passed"
  echo "functions assert_malformed: $malformed_total checks passed"
  echo "functions assert_trap: $trap_total checks passed"
}

test_globals() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  json="$prepared/globals/script.json"
  dir=${json%/*}
  wasm="$dir/script.0.wasm"
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-globals.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-globals-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM

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

  invalid_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected global validation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      echo "error: $file failed without a validation diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done

  malformed_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected malformed global binary rejection from $file" >&2
      exit 1
    fi
    if ! grep -q '^error:' "$failure_out"; then
      echo "error: $file failed without a decoder diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    malformed_count=$((malformed_count + 1))
  done

  if "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
       --invoke-scalar as-call_indirect-last 0 > "$failure_out" 2>&1; then
    echo "error: expected global-suite indirect-call trap" >&2
    exit 1
  fi
  if ! grep -q 'program terminated by signal 6' "$failure_out"; then
    echo "error: global-suite trap did not produce the expected runtime signal" >&2
    cat "$failure_out" >&2
    exit 1
  fi

  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "globals assert_return: 45 checks passed"
  echo "globals assert_invalid: $invalid_count checks passed"
  echo "globals assert_malformed: $malformed_count checks passed"
  echo "globals assert_trap: 1 check passed"
}

test_memory_instructions() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-memory-instructions.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-memory-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  invalid_total=0
  malformed_total=0
  trap_total=0

  for suite in memory_grow memory_redundancy load store address align memory_trap memory; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    if [ ! -f "$json" ]; then
      echo "error: prepared $suite suite is missing; run scripts/wasm-spec.sh prepare" >&2
      exit 1
    fi

    if [ "$suite" = memory ]; then
      for file in script.0.wasm script.1.wasm script.2.wasm script.3.wasm; do
        "$coil_bin" run "$dir/$file" --use experiments.wasm.lang
      done
    fi

    if [ "$suite" = memory_redundancy ]; then
      jq -r '
        .commands[]
        | if .type == "assert_return" then
            .action.field,
            (if (.expected | length) == 0 then "void" else .expected[0].type end),
            (if (.expected | length) == 0 then "0" else .expected[0].value end),
            (.action.args | length | tostring),
            (.action.args[] | .type, .value)
          elif .type == "action" then
            .action.field, "void", "0",
            (.action.args | length | tostring),
            (.action.args[] | .type, .value)
          else empty end
      ' "$json" > "$args_file"
      xargs "$coil_bin" run "$dir/script.0.wasm" \
        --use experiments.wasm.lang -- --assert-scalar-batch < "$args_file"
    else
      for file in $(jq -r '
        .commands
        | reduce .[] as $command
            ({current: "", files: []};
             if $command.type == "module" then .current = $command.filename
             elif $command.type == "assert_return"
             then .files += [.current]
             else . end)
        | .files | unique[]
      ' "$json"); do
        jq -r --arg file "$file" '
          .commands
          | reduce .[] as $command
              ({current: "", selected: []};
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
      done
    fi
    count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
    return_total=$((return_total + count))

    for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected validation failure from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WebAssembly validation:' "$failure_out"; then
        echo "error: $suite/$file failed without a validation diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      invalid_total=$((invalid_total + 1))
    done

    for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected malformed module rejection from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q '^error:' "$failure_out"; then
        echo "error: $suite/$file failed without a reader diagnostic" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      malformed_total=$((malformed_total + 1))
    done

    jq -r '
      .commands
      | reduce .[] as $command
          ({current: "", selected: []};
           if $command.type == "module" then .current = $command.filename
           elif $command.type == "assert_trap"
           then .selected += [{file: .current, action: $command.action}]
           else . end)
      | .selected[]
      | ([.file, .action.field, (.action.args | length | tostring)]
         + [.action.args[] | .type, .value])
      | join(" ")
    ' "$json" > "$args_file"
    while IFS= read -r line; do
      set -- $line
      file=$1
      shift
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
           --invoke-scalar "$@" > "$failure_out" 2>&1; then
        echo "error: expected WebAssembly trap from $suite/$file export $1" >&2
        exit 1
      fi
      if ! grep -q 'program terminated by signal 6' "$failure_out"; then
        echo "error: $suite/$file export $1 failed without the expected runtime trap" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      trap_total=$((trap_total + 1))
    done < "$args_file"
  done

  assertion_total=$((return_total + invalid_total + malformed_total + trap_total))
  if [ "$return_total" -ne 430 ] || [ "$invalid_total" -ne 157 ] || \
     [ "$malformed_total" -ne 67 ] || [ "$trap_total" -ne 206 ] || \
     [ "$assertion_total" -ne 860 ]; then
    echo "error: memory-instruction assertion inventory changed: returns=$return_total invalid=$invalid_total malformed=$malformed_total traps=$trap_total total=$assertion_total" >&2
    exit 1
  fi

  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "memory instructions assert_return: $return_total checks passed"
  echo "memory instructions assert_invalid: $invalid_total checks passed"
  echo "memory instructions assert_malformed: $malformed_total checks passed"
  echo "memory instructions assert_trap: $trap_total checks passed"
}

test_types() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  json="$prepared/type/script.json"
  dir=${json%/*}
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-type-failure.XXXXXX")
  trap 'rm -f "$failure_out"' EXIT HUP INT TERM

  "$coil_bin" run "$dir/script.0.wasm" --use experiments.wasm.lang

  invalid_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected type validation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      echo "error: $file failed without a validation diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done

  malformed_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected malformed type rejection from $file" >&2
      exit 1
    fi
    if ! grep -q 'WAT reader:' "$failure_out"; then
      echo "error: $file failed without a WAT reader diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    malformed_count=$((malformed_count + 1))
  done

  if [ "$invalid_count" -ne 2 ] || [ "$malformed_count" -ne 2 ]; then
    echo "error: type assertion inventory changed: invalid=$invalid_count malformed=$malformed_count" >&2
    exit 1
  fi
  rm -f "$failure_out"
  trap - EXIT HUP INT TERM
  echo "types assert_invalid: $invalid_count checks passed"
  echo "types assert_malformed: $malformed_count checks passed"
}

test_data_segments() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  json="$prepared/data/script.json"
  dir=${json%/*}
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-data-failure.XXXXXX")
  trap 'rm -f "$failure_out"' EXIT HUP INT TERM

  for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
    "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
      > "$failure_out" 2>&1 || {
        echo "error: valid data module $file failed to instantiate" >&2
        cat "$failure_out" >&2
        exit 1
      }
  done

  unlinkable_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_unlinkable") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected data instantiation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$failure_out"; then
      echo "error: $file failed without the expected instantiation trap" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    unlinkable_count=$((unlinkable_count + 1))
  done

  invalid_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected data validation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      echo "error: $file failed without a validation diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done

  if [ "$unlinkable_count" -ne 14 ] || [ "$invalid_count" -ne 6 ]; then
    echo "error: data assertion inventory changed: unlinkable=$unlinkable_count invalid=$invalid_count" >&2
    exit 1
  fi
  rm -f "$failure_out"
  trap - EXIT HUP INT TERM
  echo "data assert_unlinkable: $unlinkable_count checks passed"
  echo "data assert_invalid: $invalid_count checks passed"
  echo "data valid modules: 25 instantiations passed"
}

test_elements() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  json="$prepared/elem/script.json"
  dir=${json%/*}
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-elem-failure.XXXXXX")
  trap 'rm -f "$failure_out"' EXIT HUP INT TERM

  for n in $(seq 0 17); do
    "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang \
      > "$failure_out" 2>&1 || {
        echo "error: valid element module script.$n.wasm failed" >&2
        cat "$failure_out" >&2
        exit 1
      }
  done

  "$coil_bin" run "$dir/script.7.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch call-7 i32 65 0 call-9 i32 66 0
  "$coil_bin" run "$dir/script.36.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch call-overwritten i32 66 0
  "$coil_bin" run "$dir/script.37.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch call-overwritten-element i32 66 0
  (cd "$root/tests/wasm/table-linking-interop" && "$coil_bin" run)

  if "$coil_bin" run "$dir/script.38.wasm" --use experiments.wasm.lang -- \
       --invoke-scalar call-7 0 > "$failure_out" 2>&1; then
    echo "error: expected uninitialized linked-table element trap" >&2
    exit 1
  fi
  if ! grep -q 'program terminated by signal 6' "$failure_out"; then
    echo "error: linked-table call failed without the expected runtime trap" >&2
    cat "$failure_out" >&2
    exit 1
  fi

  unlinkable_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_unlinkable") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected element instantiation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$failure_out"; then
      echo "error: $file failed without the expected instantiation trap" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    unlinkable_count=$((unlinkable_count + 1))
  done

  invalid_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected element validation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      echo "error: $file failed without a validation diagnostic" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done

  return_count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
  trap_count=$(jq '[.commands[] | select(.type == "assert_trap")] | length' "$json")
  if [ "$return_count" -ne 12 ] || [ "$unlinkable_count" -ne 12 ] || \
     [ "$invalid_count" -ne 6 ] || [ "$trap_count" -ne 1 ]; then
    echo "error: element assertion inventory changed: returns=$return_count unlinkable=$unlinkable_count invalid=$invalid_count traps=$trap_count" >&2
    exit 1
  fi
  rm -f "$failure_out"
  trap - EXIT HUP INT TERM
  echo "elements assert_return: $return_count checks passed"
  echo "elements assert_unlinkable: $unlinkable_count checks passed"
  echo "elements assert_invalid: $invalid_count checks passed"
  echo "elements assert_trap: $trap_count check passed"
}

test_imports() {
  coil_bin=${COIL:-coil}
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-imports-failure.XXXXXX")
  unlinkable_dir=$(mktemp -d "$root/tests/wasm/.imports-unlinkable.XXXXXX")
  trap 'rm -f "$failure_out"; rm -rf "$unlinkable_dir"' EXIT HUP INT TERM
  (cd "$root/tests/wasm/imports-interop" && "$coil_bin" run)
  echo "imports cross-module function assert_return: 2 checks passed"
  dir="$prepared/imports"
  "$coil_bin" run "$dir/script.34.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch \
      get-0 i32 666 0 \
      get-1 i32 666 0 \
      get-x i32 666 0 \
      get-y i32 666 0
  echo "imports host-global assert_return: 4 checks passed"

  for n in 45 46; do
    "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang -- \
      --assert-scalar-batch \
        call i32 11 1 i32 1 \
        call i32 22 1 i32 2
    for at in 0 3 100; do
      if "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang -- \
           --invoke-scalar call 1 i32 "$at" > "$failure_out" 2>&1; then
        echo "error: expected imported-table trap from script.$n.wasm at $at" >&2
        exit 1
      fi
      if ! grep -q 'program terminated by signal 6' "$failure_out"; then
        cat "$failure_out" >&2
        exit 1
      fi
    done
  done
  echo "imports host-table: 4 returns and 6 traps passed"

  for n in 71 72; do
    "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang -- \
      --assert-scalar-batch \
        load i32 0 1 i32 0 \
        load i32 16 1 i32 10 \
        load i32 1048576 1 i32 8
    if "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang -- \
         --invoke-scalar load 1 i32 1000000 > "$failure_out" 2>&1; then
      echo "error: expected imported-memory trap from script.$n.wasm" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$failure_out"; then
      cat "$failure_out" >&2
      exit 1
    fi
  done
  "$coil_bin" run "$dir/script.99.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch \
      grow i32 1 1 i32 0 \
      grow i32 1 1 i32 1 \
      grow i32 2 1 i32 0 \
      grow i32 4294967295 1 i32 1 \
      grow i32 2 1 i32 0
  echo "imports host-memory: 11 returns and 2 traps passed"

  invalid_count=0
  for n in 2 47 48 49 73 74 75; do
    if "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected multiple-resource validation failure from script.$n.wasm" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      cat "$failure_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done
  spectest_unlinkable_count=0
  for n in 11 31 32 33 38 42 43 44 62 66 70 86 89 90 94 95 96 97 98; do
    if "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected spectest import link failure from script.$n.wasm" >&2
      exit 1
    fi
    spectest_unlinkable_count=$((spectest_unlinkable_count + 1))
  done
  cp "$root/tests/wasm/imports-unlinkable/Coil.toml" "$unlinkable_dir/Coil.toml"
  cp "$root/tests/wasm/imports-unlinkable/main.coil" "$unlinkable_dir/main.coil"
  cp "$dir/script.0.wasm" "$unlinkable_dir/test.wasm"
  cp "$dir/script.116.wasm" "$unlinkable_dir/not-wasm.wasm"
  registered_valid_count=0
  for n in 3 4 5 6 7 8 9 35 36 50 51 52 76 77 78; do
    cp "$dir/script.$n.wasm" "$unlinkable_dir/candidate.wasm"
    if ! (cd "$unlinkable_dir" && "$coil_bin" run) > "$failure_out" 2>&1; then
      echo "error: valid registered-module import script.$n.wasm failed" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    registered_valid_count=$((registered_valid_count + 1))
  done
  spectest_valid_count=0
  for n in 53 54 55 56 57 58 59 60 79 80 81 82 83 84; do
    if ! "$coil_bin" run "$dir/script.$n.wasm" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: valid spectest import script.$n.wasm failed" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    spectest_valid_count=$((spectest_valid_count + 1))
  done
  if ! "$coil_bin" run "$dir/script.116.wasm" --use experiments.wasm.lang \
       > "$failure_out" 2>&1; then
    echo "error: valid registered provider script.116.wasm failed" >&2
    cat "$failure_out" >&2
    exit 1
  fi
  registered_unlinkable_count=0
  for n in 10 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 \
           37 39 40 41 61 63 64 65 67 68 69 85 87 88 91 92 93 117; do
    if [ "$n" -eq 117 ]; then
      cp "$dir/script.116.wasm" "$unlinkable_dir/not-wasm.wasm"
    else
      cp "$dir/script.0.wasm" "$unlinkable_dir/test.wasm"
    fi
    cp "$dir/script.$n.wasm" "$unlinkable_dir/candidate.wasm"
    if (cd "$unlinkable_dir" && "$coil_bin" run) > "$failure_out" 2>&1; then
      echo "error: expected registered-module link failure from script.$n.wasm" >&2
      exit 1
    fi
    registered_unlinkable_count=$((registered_unlinkable_count + 1))
  done
  malformed_count=0
  for n in $(seq 100 115); do
    if "$coil_bin" run "$dir/script.$n.wat" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected malformed import ordering failure from script.$n.wat" >&2
      exit 1
    fi
    malformed_count=$((malformed_count + 1))
  done
  rm -f "$failure_out"
  rm -rf "$unlinkable_dir"
  trap - EXIT HUP INT TERM
  echo "imports multiple-resource assert_invalid: $invalid_count checks passed"
  echo "imports spectest assert_unlinkable: $spectest_unlinkable_count checks passed"
  echo "imports registered-module assert_unlinkable: $registered_unlinkable_count checks passed"
  echo "imports valid registration-only modules: $registered_valid_count registered and $spectest_valid_count spectest passed"
  echo "imports assert_malformed: $malformed_count checks passed"
}

test_linking() {
  coil_bin=${COIL:-coil}
  (cd "$root/tests/wasm/linking-functions" && "$coil_bin" run)
  echo "linking cross-module function assert_return: 4 checks passed"
  (cd "$root/tests/wasm/linking-globals" && "$coil_bin" run)
  echo "linking cross-module global assert_return: 16 checks passed"
  (cd "$root/tests/wasm/linking-tables" && "$coil_bin" run)
  echo "linking cross-module table assert_return: 22 checks passed"
  (cd "$root/tests/wasm/linking-memory" && "$coil_bin" run)
  echo "linking cross-module memory assert_return: 18 checks passed"

  trap_exe=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-linking-traps.XXXXXX")
  trap_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-linking-trap-output.XXXXXX")
  failure_dir=$(mktemp -d "$root/tests/wasm/.linking-failures.XXXXXX")
  trap 'rm -f "$trap_exe" "$trap_out"; rm -rf "$failure_dir"' EXIT HUP INT TERM
  (cd "$root/tests/wasm/linking-traps" && "$coil_bin" build -o "$trap_exe")
  trap_count=0
  for mode in $(seq 1 19); do
    set +e
    sh -c '"$1" "$2" >/dev/null 2>&1; exit $?' sh "$trap_exe" "$mode" \
      > "$trap_out" 2>&1
    status=$?
    set -e
    if [ "$status" -ne 134 ]; then
      echo "error: linking trap mode $mode exited $status instead of SIGABRT" >&2
      cat "$trap_out" >&2
      exit 1
    fi
    trap_count=$((trap_count + 1))
  done
  echo "linking assert_trap: $trap_count checks passed"

  cp "$root/tests/wasm/linking-failures/Coil.toml" "$failure_dir/Coil.toml"
  cp "$root/tests/wasm/linking-failures/main.coil" "$failure_dir/main.coil"
  linking_dir="$prepared/linking"
  cp "$linking_dir/script.2.wasm" "$failure_dir/reexport-f.wasm"
  cp "$linking_dir/script.5.wasm" "$failure_dir/mg.wasm"
  cp "$linking_dir/script.9.wasm" "$failure_dir/mt.wasm"
  cp "$linking_dir/script.19.wasm" "$failure_dir/mm.wasm"
  cp "$linking_dir/script.28.wasm" "$failure_dir/ms.wasm"
  unlinkable_count=0
  for n in 3 4 7 8 15 16 17 18 23 25 26 27; do
    cp "$linking_dir/script.$n.wasm" "$failure_dir/candidate.wasm"
    if (cd "$failure_dir" && "$coil_bin" run) > "$trap_out" 2>&1; then
      echo "error: expected linking failure from script.$n.wasm" >&2
      exit 1
    fi
    unlinkable_count=$((unlinkable_count + 1))
  done
  cp "$linking_dir/script.29.wasm" "$failure_dir/candidate.wasm"
  if (cd "$failure_dir" && "$coil_bin" run) > "$trap_out" 2>&1; then
    echo "error: expected trapped-start instantiation failure from script.29.wasm" >&2
    exit 1
  fi
  rm -f "$trap_exe" "$trap_out"
  rm -rf "$failure_dir"
  trap - EXIT HUP INT TERM
  echo "linking assert_unlinkable: $unlinkable_count checks passed"
  echo "linking assert_uninstantiable: 1 check passed"
  (cd "$root/tests/wasm/linking-start-recovery" && "$coil_bin" run)
  echo "linking post-failed-start assert_return: 2 checks passed"
}

test_encoding() {
  coil_bin=${COIL:-coil}
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required to run prepared spec assertions" >&2
    exit 1
  }
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-encoding-failure.XXXXXX")
  trap 'rm -f "$failure_out"' EXIT HUP INT TERM
  malformed_count=0
  module_count=0
  for suite in binary-leb128 binary custom token utf8-custom-section-id \
               utf8-import-field utf8-import-module utf8-invalid-encoding; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected malformed encoding rejection from $suite/$file" >&2
        exit 1
      fi
      malformed_count=$((malformed_count + 1))
    done
  done
  for suite in binary-leb128 binary custom comments inline-module; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
      if ! "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: valid encoded module $suite/$file failed" >&2
        cat "$failure_out" >&2
        exit 1
      fi
      module_count=$((module_count + 1))
    done
  done
  if [ "$malformed_count" -ne 835 ] || [ "$module_count" -ne 49 ]; then
    echo "error: encoding inventory changed: malformed=$malformed_count modules=$module_count" >&2
    exit 1
  fi
  rm -f "$failure_out"
  trap - EXIT HUP INT TERM
  echo "encoding assert_malformed: $malformed_count checks passed"
  echo "encoding valid modules: $module_count instantiations passed"
}

test_exports() {
  coil_bin=${COIL:-coil}
  json="$prepared/exports/script.json"
  dir=${json%/*}
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-exports-failure.XXXXXX")
  trap 'rm -f "$failure_out"' EXIT HUP INT TERM
  "$coil_bin" run "$dir/script.11.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch \
      e i32 43 1 i32 42 \
      e i32 43 1 i32 42 \
      e i32 43 1 i32 42
  "$coil_bin" run "$dir/script.29.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch e i32 42 0 e i32 42 0 e i32 42 0
  invalid_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected export validation failure from $file" >&2
      exit 1
    fi
    if ! grep -q 'WebAssembly validation:' "$failure_out"; then
      cat "$failure_out" >&2
      exit 1
    fi
    invalid_count=$((invalid_count + 1))
  done
  module_count=0
  for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
    if ! "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: valid exports module $file failed" >&2
      cat "$failure_out" >&2
      exit 1
    fi
    module_count=$((module_count + 1))
  done
  if [ "$invalid_count" -ne 22 ] || [ "$module_count" -ne 54 ]; then
    echo "error: exports inventory changed: invalid=$invalid_count modules=$module_count" >&2
    exit 1
  fi
  rm -f "$failure_out"
  trap - EXIT HUP INT TERM
  echo "exports assert_return: 6 checks passed"
  echo "exports assert_invalid: $invalid_count checks passed"
  echo "exports valid modules: $module_count instantiations passed"
}

test_float_extensions() {
  coil_bin=${COIL:-coil}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-extensions.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-extension-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  invalid_total=0
  for suite in f32_bitwise f32_cmp f64_bitwise f64_cmp; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    wasm="$dir/script.0.wasm"
    count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
    offset=0
    while [ "$offset" -lt "$count" ]; do
      jq -r --argjson lo "$offset" --argjson hi "$((offset + 150))" '
        [.commands[] | select(.type == "assert_return")][$lo:$hi][]
        | .action.field,
          .expected[0].type,
          .expected[0].value,
          (.action.args | length | tostring),
          (.action.args[] | .type, .value)
      ' "$json" > "$args_file"
      xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
        --assert-scalar-batch < "$args_file"
      offset=$((offset + 150))
    done
    return_total=$((return_total + count))
    for file in $(jq -r '.commands[] | select(.type == "assert_invalid") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected validation failure from $suite/$file" >&2
        exit 1
      fi
      if ! grep -q 'WebAssembly validation:' "$failure_out"; then
        cat "$failure_out" >&2
        exit 1
      fi
      invalid_total=$((invalid_total + 1))
    done
  done
  if [ "$return_total" -ne 5520 ] || [ "$invalid_total" -ne 18 ]; then
    echo "error: float extension inventory changed: returns=$return_total invalid=$invalid_total" >&2
    exit 1
  fi
  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "float extension assert_return: $return_total checks passed"
  echo "float extension assert_invalid: $invalid_total checks passed"
}

test_integer_expressions() {
  coil_bin=${COIL:-coil}
  json="$prepared/int_exprs/script.json"
  dir=${json%/*}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-int-exprs.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-int-expr-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  for wasm in "$dir"/script.*.wasm; do
    file=${wasm##*/}
    jq -r --arg file "$file" '
      .commands
      | reduce .[] as $command
          ({current: "", selected: []};
           if $command.type == "module" then .current = $command.filename
           elif ($command.type == "assert_return" and .current == $file)
           then .selected += [$command]
           else . end)
      | .selected[]
      | .action.field,
        .expected[0].type,
        .expected[0].value,
        (.action.args | length | tostring),
        (.action.args[] | .type, .value)
    ' "$json" > "$args_file"
    if [ -s "$args_file" ]; then
      xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
        --assert-scalar-batch < "$args_file"
    fi
  done
  trap_count=0
  jq -r '
    .commands
    | reduce .[] as $command
        ({current: "", selected: []};
         if $command.type == "module" then .current = $command.filename
         elif $command.type == "assert_trap"
         then .selected += [{file: .current, action: $command.action}]
         else . end)
    | .selected[]
    | ([.file, .action.field, (.action.args | length | tostring)]
       + [.action.args[] | .type, .value])
    | join(" ")
  ' "$json" > "$args_file"
  while IFS= read -r line; do
    set -- $line
    file=$1
    shift
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
         --invoke-scalar "$@" > "$failure_out" 2>&1; then
      echo "error: expected integer expression trap from $file export $1" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$failure_out"; then
      cat "$failure_out" >&2
      exit 1
    fi
    trap_count=$((trap_count + 1))
  done < "$args_file"
  return_count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
  if [ "$return_count" -ne 75 ] || [ "$trap_count" -ne 14 ]; then
    echo "error: int_exprs inventory changed: returns=$return_count traps=$trap_count" >&2
    exit 1
  fi
  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "integer expressions assert_return: $return_count checks passed"
  echo "integer expressions assert_trap: $trap_count checks passed"
}

test_literals() {
  coil_bin=${COIL:-coil}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-literals.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-literal-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  return_total=0
  malformed_total=0
  module_total=0
  for suite in int_literals const; do
    json="$prepared/$suite/script.json"
    dir=${json%/*}
    for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
      jq -r --arg file "$file" '
        .commands
        | reduce .[] as $command
            ({current: "", selected: []};
             if $command.type == "module" then .current = $command.filename
             elif ($command.type == "assert_return" and .current == $file)
             then .selected += [$command]
             else . end)
        | .selected[]
        | .action.field,
          .expected[0].type,
          .expected[0].value,
          (.action.args | length | tostring),
          (.action.args[] | .type, .value)
      ' "$json" > "$args_file"
      if [ -s "$args_file" ]; then
        if ! xargs "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
             --assert-scalar-batch < "$args_file"; then
          echo "error: literal assertions failed in $suite/$file" >&2
          exit 1
        fi
      else
        if ! "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
             > "$failure_out" 2>&1; then
          echo "error: valid literal module $suite/$file failed" >&2
          cat "$failure_out" >&2
          exit 1
        fi
      fi
      module_total=$((module_total + 1))
    done
    return_total=$((return_total + $(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")))
    for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
      if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
           > "$failure_out" 2>&1; then
        echo "error: expected malformed literal rejection from $suite/$file" >&2
        exit 1
      fi
      malformed_total=$((malformed_total + 1))
    done
  done
  if [ "$return_total" -ne 330 ] || [ "$malformed_total" -ne 50 ] || \
     [ "$module_total" -ne 339 ]; then
    echo "error: literal inventory changed: returns=$return_total malformed=$malformed_total modules=$module_total" >&2
    exit 1
  fi
  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "literals assert_return: $return_total checks passed"
  echo "literals assert_malformed: $malformed_total checks passed"
  echo "literals valid modules: $module_total instantiations passed"
}

test_names() {
  coil_bin=${COIL:-coil}
  json="$prepared/names/script.json"
  dir=${json%/*}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-names.XXXXXX")
  assertion_exe=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-name-assertions.XXXXXX")
  trap 'rm -f "$args_file" "$assertion_exe"' EXIT HUP INT TERM
  "$coil_bin" run "$dir/script.0.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch foo i32 0 0
  "$coil_bin" run "$dir/script.1.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch foo i32 1 0
  "$coil_bin" build "$dir/script.2.wasm" -o "$assertion_exe" \
    --use experiments.wasm.lang -- --assert-scalar-batch "" i32 0 0
  "$assertion_exe"
  jq -j '
    .commands[6:481][] | select(.type == "assert_return")
    | .action.field, "\u0000",
      .expected[0].type, "\u0000",
      .expected[0].value, "\u0000",
      (.action.args | length | tostring), "\u0000",
      (.action.args[] | .type, "\u0000", .value, "\u0000")
  ' "$json" > "$args_file"
  xargs -0 "$coil_bin" build "$dir/script.2.wasm" -o "$assertion_exe" \
    --use experiments.wasm.lang -- --assert-scalar-batch < "$args_file"
  "$assertion_exe"
  "$coil_bin" run "$dir/script.3.wasm" --use experiments.wasm.lang -- \
    --assert-scalar-batch print32 void 0 2 i32 42 i32 123
  return_count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
  module_count=$(jq '[.commands[] | select(.type == "module")] | length' "$json")
  if [ "$return_count" -ne 479 ] || [ "$module_count" -ne 4 ]; then
    echo "error: names inventory changed: returns=$return_count modules=$module_count" >&2
    exit 1
  fi
  rm -f "$args_file" "$assertion_exe"
  trap - EXIT HUP INT TERM
  echo "names assert_return: $return_count checks passed"
  echo "names valid modules: $module_count instantiations passed"
}

test_traps_file() {
  coil_bin=${COIL:-coil}
  json="$prepared/traps/script.json"
  dir=${json%/*}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-traps.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-trap-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  jq -r '
    .commands
    | reduce .[] as $command
        ({current: "", selected: []};
         if $command.type == "module" then .current = $command.filename
         elif $command.type == "assert_trap"
         then .selected += [{file: .current, action: $command.action}]
         else . end)
    | .selected[]
    | ([.file, .action.field, (.action.args | length | tostring)]
       + [.action.args[] | .type, .value])
    | join(" ")
  ' "$json" > "$args_file"
  trap_count=0
  while IFS= read -r line; do
    set -- $line
    file=$1
    shift
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
         --invoke-scalar "$@" > "$failure_out" 2>&1; then
      echo "error: expected trap from traps/$file export $1" >&2
      exit 1
    fi
    if ! grep -q 'program terminated by signal 6' "$failure_out"; then
      cat "$failure_out" >&2
      exit 1
    fi
    trap_count=$((trap_count + 1))
  done < "$args_file"
  module_count=$(jq '[.commands[] | select(.type == "module")] | length' "$json")
  if [ "$trap_count" -ne 32 ] || [ "$module_count" -ne 4 ]; then
    echo "error: traps inventory changed: traps=$trap_count modules=$module_count" >&2
    exit 1
  fi
  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "traps assert_trap: $trap_count checks passed"
  echo "traps valid modules: $module_count modules exercised"
}

test_float_misc() {
  coil_bin=${COIL:-coil}
  json="$prepared/float_misc/script.json"
  dir=${json%/*}
  wasm="$dir/script.0.wasm"
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-misc.XXXXXX")
  trap 'rm -f "$args_file"' EXIT HUP INT TERM
  return_count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
  offset=0
  while [ "$offset" -lt "$return_count" ]; do
    jq -r --argjson lo "$offset" --argjson hi "$((offset + 150))" '
      [.commands[] | select(.type == "assert_return")][$lo:$hi][]
      | .action.field,
        .expected[0].type,
        .expected[0].value,
        (.action.args | length | tostring),
        (.action.args[] | .type, .value)
    ' "$json" > "$args_file"
    xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
      --assert-scalar-batch < "$args_file"
    offset=$((offset + 150))
  done
  jq -r '
    .commands[] | select(.type == "assert_return_canonical_nan")
    | .action.field, (.action.args | length | tostring), (.action.args[].value)
  ' "$json" > "$args_file"
  xargs "$coil_bin" run "$wasm" --use experiments.wasm.lang -- \
    --assert-f64-canonical-nan-batch < "$args_file"
  canonical_count=$(jq '[.commands[] | select(.type == "assert_return_canonical_nan")] | length' "$json")
  if [ "$return_count" -ne 439 ] || [ "$canonical_count" -ne 1 ]; then
    echo "error: float_misc inventory changed: returns=$return_count canonical=$canonical_count" >&2
    exit 1
  fi
  rm -f "$args_file"
  trap - EXIT HUP INT TERM
  echo "float_misc assert_return: $return_count checks passed"
  echo "float_misc canonical NaN: $canonical_count check passed"
}

test_float_expressions() {
  coil_bin=${COIL:-coil}
  json="$prepared/float_exprs/script.json"
  dir=${json%/*}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-exprs.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-expr-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  module_count=0
  for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
    jq -r --arg file "$file" '
      .commands
      | reduce .[] as $command
          ({current: "", selected: []};
           if $command.type == "module" then .current = $command.filename
           elif (.current == $file and
                 ($command.type == "action" or $command.type == "assert_return"))
           then .selected += [$command]
           else . end)
      | .selected[]
      | .action.field,
        (if .type == "action" or (.expected | length) == 0
         then "void" else .expected[0].type end),
        (if .type == "action" or (.expected | length) == 0
         then "0" else .expected[0].value end),
        (.action.args | length | tostring),
        (.action.args[] | .type, .value)
    ' "$json" > "$args_file"
    if [ -s "$args_file" ]; then
      xargs "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
        --assert-scalar-batch < "$args_file"
    else
      "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
        > "$failure_out" 2>&1
    fi
    for assertion in assert_return_canonical_nan assert_return_arithmetic_nan; do
      for kind in f32 f64; do
        jq -r --arg file "$file" --arg assertion "$assertion" --arg kind "$kind" '
          .commands
          | reduce .[] as $command
              ({current: "", selected: []};
               if $command.type == "module" then .current = $command.filename
               elif (.current == $file and $command.type == $assertion and
                     $command.expected[0].type == $kind)
               then .selected += [$command]
               else . end)
          | .selected[]
          | .action.field, (.action.args | length | tostring), (.action.args[].value)
        ' "$json" > "$args_file"
        if [ -s "$args_file" ]; then
          if [ "$assertion" = assert_return_canonical_nan ]; then
            mode="--assert-$kind-canonical-nan-batch"
          else
            mode="--assert-$kind-arithmetic-nan-batch"
          fi
          xargs "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
            "$mode" < "$args_file"
        fi
      done
    done
    module_count=$((module_count + 1))
  done
  return_count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
  canonical_count=$(jq '[.commands[] | select(.type == "assert_return_canonical_nan")] | length' "$json")
  arithmetic_count=$(jq '[.commands[] | select(.type == "assert_return_arithmetic_nan")] | length' "$json")
  action_count=$(jq '[.commands[] | select(.type == "action")] | length' "$json")
  if [ "$return_count" -ne 731 ] || [ "$canonical_count" -ne 38 ] || \
     [ "$arithmetic_count" -ne 25 ] || [ "$action_count" -ne 10 ] || \
     [ "$module_count" -ne 96 ]; then
    echo "error: float_exprs inventory changed: returns=$return_count canonical=$canonical_count arithmetic=$arithmetic_count actions=$action_count modules=$module_count" >&2
    exit 1
  fi
  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "float expressions assert_return: $return_count checks passed"
  echo "float expressions canonical NaN: $canonical_count checks passed"
  echo "float expressions arithmetic NaN: $arithmetic_count checks passed"
  echo "float expressions actions: $action_count actions and $module_count modules passed"
}

test_float_literals() {
  coil_bin=${COIL:-coil}
  json="$prepared/float_literals/script.json"
  dir=${json%/*}
  args_file=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-literals.XXXXXX")
  failure_out=$(mktemp "${TMPDIR:-/tmp}/coil-wasm-float-literal-failure.XXXXXX")
  trap 'rm -f "$args_file" "$failure_out"' EXIT HUP INT TERM
  module_count=0
  for file in $(jq -r '.commands[] | select(.type == "module") | .filename' "$json"); do
    jq -r --arg file "$file" '
      .commands
      | reduce .[] as $command
          ({current: "", selected: []};
           if $command.type == "module" then .current = $command.filename
           elif (.current == $file and $command.type == "assert_return")
           then .selected += [$command]
           else . end)
      | .selected[]
      | .action.field,
        .expected[0].type,
        .expected[0].value,
        (.action.args | length | tostring),
        (.action.args[] | .type, .value)
    ' "$json" > "$args_file"
    if [ -s "$args_file" ]; then
      xargs "$coil_bin" run "$dir/$file" --use experiments.wasm.lang -- \
        --assert-scalar-batch < "$args_file"
    else
      "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
        > "$failure_out" 2>&1
    fi
    module_count=$((module_count + 1))
  done
  malformed_count=0
  for file in $(jq -r '.commands[] | select(.type == "assert_malformed") | .filename' "$json"); do
    if "$coil_bin" run "$dir/$file" --use experiments.wasm.lang \
         > "$failure_out" 2>&1; then
      echo "error: expected malformed float literal rejection from $file" >&2
      exit 1
    fi
    malformed_count=$((malformed_count + 1))
  done
  return_count=$(jq '[.commands[] | select(.type == "assert_return")] | length' "$json")
  if [ "$return_count" -ne 83 ] || [ "$malformed_count" -ne 76 ] || \
     [ "$module_count" -ne 2 ]; then
    echo "error: float_literals inventory changed: returns=$return_count malformed=$malformed_count modules=$module_count" >&2
    exit 1
  fi
  rm -f "$args_file" "$failure_out"
  trap - EXIT HUP INT TERM
  echo "float literals assert_return: $return_count checks passed"
  echo "float literals assert_malformed: $malformed_count checks passed"
  echo "float literals valid modules: $module_count instantiations passed"
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
    mixed-folded-flat i64 42 0 \
    set-local i32 42 1 i32 40 \
    tee-local i64 42 0 \
    set-parameter i32 42 1 i32 0
  echo "focused textual WAT expression and mutable-local checks passed"
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
  test-loops) test_loops ;;
  test-structured-control) test_structured_control ;;
  test-start) test_start ;;
  test-basic-instructions) test_basic_instructions ;;
  test-evaluation-order) test_evaluation_order ;;
  test-functions) test_functions ;;
  test-globals) test_globals ;;
  test-memory-instructions) test_memory_instructions ;;
  test-types) test_types ;;
  test-data-segments) test_data_segments ;;
  test-elements) test_elements ;;
  test-imports) test_imports ;;
  test-linking) test_linking ;;
  test-encoding) test_encoding ;;
  test-exports) test_exports ;;
  test-float-extensions) test_float_extensions ;;
  test-integer-expressions) test_integer_expressions ;;
  test-literals) test_literals ;;
  test-names) test_names ;;
  test-traps-file) test_traps_file ;;
  test-float-misc) test_float_misc ;;
  test-float-expressions) test_float_expressions ;;
  test-float-literals) test_float_literals ;;
  test-wat) test_wat ;;
  *)
    echo "usage: scripts/wasm-spec.sh [fetch|fetch-wabt|prepare|inventory|test-integers|test-floats|test-conversions|test-memory|test-tables|test-control|test-loops|test-structured-control|test-start|test-basic-instructions|test-evaluation-order|test-functions|test-globals|test-memory-instructions|test-types|test-data-segments|test-elements|test-imports|test-linking|test-encoding|test-exports|test-float-extensions|test-integer-expressions|test-literals|test-names|test-traps-file|test-float-misc|test-float-expressions|test-float-literals|test-wat]" >&2
    exit 2
    ;;
esac
