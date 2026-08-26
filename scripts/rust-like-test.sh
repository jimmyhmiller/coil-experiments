#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

if find src/dialects/rust-like -type f -name '*.py' -print | grep .; then
    echo "Python files are forbidden in the rust-like implementation" >&2
    exit 1
fi

if rg -n 'python|popen|system\(|process/spawn|subprocess' src/dialects/rust-like; then
    echo "rust-like production code must be implemented entirely in Coil" >&2
    exit 1
fi

if [ -e src/dialects/rust ]; then
    echo "obsolete src/dialects/rust must not exist" >&2
    exit 1
fi

if ! rg -qi 'never use python to implement' AGENTS.md; then
    echo "AGENTS.md must record the Python implementation prohibition" >&2
    exit 1
fi

coil check src/dialects/rust-like/rust.coil
coil check src/dialects/rust-like/convert.coil
coil check src/dialects/rust-like/reader.coil
coil check src/dialects/rust-like/converter.coil
coil check src/dialects/rust-like/tree.coil
coil check src/dialects/rust-like/audit.coil
coil check src/dialects/rust-like/audit-lang.coil
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
    checkout_candidate="$converted/build/bin/coil"

    mkdir -p "$compiler_source"
    git -C "$compiler_repo" archive HEAD | tar -x -C "$compiler_source"

    failures="$audit/roundtrip-failures"
    audited="$audit/roundtrip-audited"
    skipped="$audit/roundtrip-skipped"
    exceptions="$audit/data-exceptions"
    : > "$failures"
    : > "$audited"
    : > "$skipped"
    rg '^- `tests/.*\.coil`$' RUST_LIKE_DATA_EXCEPTIONS.md \
        | sed -E 's/^- `([^`]*)`$/\1/' > "$exceptions"
    if [ "$(sort "$exceptions" | uniq | wc -l | tr -d ' ')" -ne \
         "$(wc -l < "$exceptions" | tr -d ' ')" ]; then
        echo "duplicate Rust-like data exception" >&2
        exit 1
    fi
    while IFS= read -r relative; do
        if [ ! -f "$compiler_source/$relative" ]; then
            echo "missing Rust-like data exception: $relative" >&2
            exit 1
        fi
    done < "$exceptions"
    export RUST_LIKE_AUDIT_ROOT="$root"
    export RUST_LIKE_COMPILER_SOURCE="$compiler_source"
    export RUST_LIKE_AUDIT_FAILURES="$failures"
    export RUST_LIKE_AUDITED="$audited"
    export RUST_LIKE_SKIPPED="$skipped"
    export RUST_LIKE_DATA_EXCEPTIONS="$exceptions"
    find "$compiler_source/src" "$compiler_source/tests" \
        -type f -name '*.coil' -print0 \
        | xargs -0 -n1 -P2 sh -c '
            file=$1
            relative=${file#"$RUST_LIKE_COMPILER_SOURCE/"}
            if grep -Fqx "$relative" "$RUST_LIKE_DATA_EXCEPTIONS"; then
                printf "%s\n" "$relative" >> "$RUST_LIKE_SKIPPED"
                exit 0
            fi
            error_file=$(mktemp /tmp/rust-like-audit-error.XXXXXX)
            cd "$RUST_LIKE_AUDIT_ROOT"
            if ! coil check "$file" --use experiments.rust-like.audit \
                    >/dev/null 2>"$error_file"; then
                printf "%s\n" "$relative" >> "$RUST_LIKE_AUDIT_FAILURES"
                sed -n '1,20p' "$error_file" >&2
            else
                printf "%s\n" "$relative" >> "$RUST_LIKE_AUDITED"
            fi
            rm "$error_file"
        ' sh
    if [ -s "$failures" ]; then
        echo "exact Rust-like syntax-tree audits failed:" >&2
        cat "$failures" >&2
        exit 1
    fi
    sort "$skipped" > "$audit/skipped.sorted"
    sort "$exceptions" > "$audit/exceptions.sorted"
    diff -u "$audit/exceptions.sorted" "$audit/skipped.sorted"
    source_count=$(find "$compiler_source/src" "$compiler_source/tests" \
        -type f -name '*.coil' | wc -l | tr -d ' ')
    audited_count=$(wc -l < "$audited" | tr -d ' ')
    skipped_count=$(wc -l < "$skipped" | tr -d ' ')
    if [ $((audited_count + skipped_count)) -ne "$source_count" ]; then
        echo "Rust-like audit did not account for every Coil source" >&2
        exit 1
    fi

    coil run experiments.rust-like.tree -- "$compiler_source" "$converted"
    if rg -n --pcre2 \
        '(^|[^A-Za-z0-9_?!-])(form!|atom!|symbol!|string!|int!|float!|parse-node!)\(' \
        "$converted" -g '*.coilrs'; then
        echo "compiler conversion emitted an AST constructor" >&2
        exit 1
    fi
    if rg -n 'coil_item|coil_expr|coil \{|rust-like-items' \
        "$converted" -g '*.coilrs'; then
        echo "compiler conversion emitted a forbidden native-source escape" >&2
        exit 1
    fi
    while IFS= read -r native; do
        relative=${native#"$compiler_source/"}
        if grep -Fqx "$relative" "$exceptions"; then
            cmp "$native" "$converted/$relative"
            if [ -e "$converted/${relative}rs" ]; then
                echo "data exception was converted: $relative" >&2
                exit 1
            fi
        else
            if [ ! -f "$converted/${relative}rs" ]; then
                echo "converted CoilRS file is missing: $relative" >&2
                exit 1
            fi
            if [ ! -f "$converted/$relative" ]; then
                echo "converted loader stub is missing: $relative" >&2
                exit 1
            fi
        fi
    done <<EOF
$(find "$compiler_source/src" "$compiler_source/tests" -type f -name '*.coil' | sort)
EOF
    (cd "$converted" && coil build src/compiler/main_a64.coilrs \
        --use experiments.rust-like.lang -o "$candidate")
    (cd "$converted" && "$candidate" --version)
    mkdir -p "$converted/build/bin"
    cp "$candidate" "$checkout_candidate"
    checkout_version=$(cd "$converted" && "$checkout_candidate" --version)
    printf '%s\n' "$checkout_version"
    printf '%s\n' "$checkout_version" | grep 'stdlib: checkout: .*/src/stdlib$'
fi

echo "rust-like Coil-native reader/converter tests passed ($audit)"
