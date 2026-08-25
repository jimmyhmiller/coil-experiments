#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

if rg -n 'python3|popen|coilrs\.py|native\.py|structured\.py' src/dialects/rust-like; then
    echo "rust-like production code must be implemented entirely in Coil" >&2
    exit 1
fi

coil check src/dialects/rust-like/reader.coil
coil check src/dialects/rust-like/converter.coil
coil check src/dialects/rust-like/tree.coil
coil check src/dialects/rust-like/audit.coil
coil check src/dialects/rust-like/audit-lang.coil
coil run tests/rust/structural.coilrs --use experiments.rust-like.lang
coil run tests/rust/structured.coilrs --use experiments.rust-like.lang
coil run tests/rust/surface.coilrs --use experiments.rust-like.lang
coil run tests/rust/advanced.coilrs --use experiments.rust-like.lang
coil run tests/rust/ffi.coilrs --use experiments.rust-like.lang
coil run tests/rust/control.coilrs --use experiments.rust-like.lang
coil run tests/rust/imports.coilrs --use experiments.rust-like.lang
coil run tests/rust/complete.coilrs --use experiments.rust-like.lang
coil run tests/rust/embedded.coil
coil run tests/rust/syntax_assertions.coil

audit=$(mktemp -d /tmp/rust-like-coil-test.XXXXXX)
coil run tests/rust/native_roundtrip.coil --use experiments.rust-like.convert > "$audit/native.coilrs"
coil run experiments.rust-like.lang "$audit/native.coilrs" > "$audit/restored.coil"
coil run "$audit/restored.coil" --use experiments.rust-like.convert > "$audit/reconverted.coilrs"
diff -u "$audit/native.coilrs" "$audit/reconverted.coilrs"
coil dump-read tests/rust/native_roundtrip.coil | sed -E 's/@[0-9]+:[0-9]+:[0-9]+:[0-9]+//g' > "$audit/original.dump"
coil dump-read "$audit/restored.coil" | sed -E 's/@[0-9]+:[0-9]+:[0-9]+:[0-9]+//g' > "$audit/restored.dump"
diff -u "$audit/original.dump" "$audit/restored.dump"

if rg -n 'coil_item|coil_expr|coil \{' "$audit/native.coilrs"; then
    echo "converter emitted a forbidden native-source escape" >&2
    exit 1
fi

if [ "${1-}" = "--compiler-copy" ]; then
    compiler_repo=${2-../coil}
    compiler_source="$audit/compiler-source"
    converted="$audit/compiler-copy"
    candidate="$audit/coil-rust-like"

    mkdir -p "$compiler_source"
    git -C "$compiler_repo" archive HEAD | tar -x -C "$compiler_source"

    failures="$audit/roundtrip-failures"
    exceptions="$audit/data-exceptions"
    : > "$failures"
    rg '^- `tests/.*\.coil`$' RUST_LIKE_DATA_EXCEPTIONS.md \
        | sed -E 's/^- `([^`]*)`$/\1/' > "$exceptions"
    export RUST_LIKE_AUDIT_ROOT="$root"
    export RUST_LIKE_COMPILER_SOURCE="$compiler_source"
    export RUST_LIKE_AUDIT_FAILURES="$failures"
    export RUST_LIKE_DATA_EXCEPTIONS="$exceptions"
    find "$compiler_source/src" "$compiler_source/tests" \
        -type f -name '*.coil' -print0 \
        | xargs -0 -n1 -P4 sh -c '
            file=$1
            relative=${file#"$RUST_LIKE_COMPILER_SOURCE/"}
            if grep -Fqx "$relative" "$RUST_LIKE_DATA_EXCEPTIONS"; then
                exit 0
            fi
            error_file=$(mktemp /tmp/rust-like-audit-error.XXXXXX)
            cd "$RUST_LIKE_AUDIT_ROOT"
            if ! coil check "$file" --use experiments.rust-like.audit \
                    >/dev/null 2>"$error_file"; then
                printf "%s\n" "$relative" >> "$RUST_LIKE_AUDIT_FAILURES"
                sed -n '1,20p' "$error_file" >&2
            fi
            rm "$error_file"
        ' sh
    if [ -s "$failures" ]; then
        echo "exact Rust-like syntax-tree audits failed:" >&2
        cat "$failures" >&2
        exit 1
    fi

    coil run experiments.rust-like.tree -- "$compiler_source" "$converted"
    if rg -n 'coil_item|coil_expr|coil \{' "$converted" -g '*.coilrs'; then
        echo "compiler conversion emitted a forbidden native-source escape" >&2
        exit 1
    fi
    (cd "$converted" && coil build src/compiler/main_a64.coilrs \
        --use experiments.rust-like.lang -o "$candidate")
    (cd "$converted" && "$candidate" --version)
fi

echo "rust-like Coil-native reader/converter tests passed ($audit)"
