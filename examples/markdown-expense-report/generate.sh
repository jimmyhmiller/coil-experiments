#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
demo="$root/examples/markdown-expense-report"
materializer="$root/src/apps/markdown-agent/main.coil"
coil_bin=${COIL_BIN:-/Users/jimmyhmiller/.cargo/bin/coil}
model=${CODEX_MODEL:-gpt-5.6-luna}
agent=${MARKDOWN_AGENT_BIN:-$demo/build/markdown-agent-runner}

mkdir -p "$demo/build"
if [ ! -x "$agent" ]; then
  (cd "$root/tools/markdown-agent-runner" && "$coil_bin" build main.coil -o "$agent")
fi

materialize() {
  (
    cd "$demo"
    "$coil_bin" run "$materializer" -- \
      "$demo/$1.md" "$demo/$1.coil" "$2" "$demo/$3" \
      "$agent" "$coil_bin" "$model"
  )
}

materialize ledger experiments.expense-report.ledger contracts/ledger_contract.coil
materialize report experiments.expense-report.report contracts/report_contract.coil
materialize main experiments.expense-report.main main.coil

(
  cd "$demo"
  "$coil_bin" build main.coil -o "$demo/build/expense-report"
)
"$demo/build/expense-report" "$demo/fixtures/expenses.csv" > "$demo/build/actual.txt"
cmp "$demo/expected.txt" "$demo/build/actual.txt"
sed -n '1,$p' "$demo/build/actual.txt"
