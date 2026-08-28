#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
demo="$root/examples/markdown-generated-program"
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
      "$demo/$1.md" \
      "$demo/$1.coil" \
      "$2" \
      "$demo/$3" \
      "$agent" \
      "$coil_bin" \
      "$model"
  )
}

materialize arithmetic experiments.markdown-demo.arithmetic -
materialize training experiments.markdown-demo.training -
materialize main experiments.markdown-demo.main -

(
  cd "$demo"
  "$coil_bin" build main.coil -o "$demo/build/training-planner"
)
"$demo/build/training-planner"
