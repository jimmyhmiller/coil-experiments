#!/usr/bin/env bash
# Checks the key-press probes against the scripted window (no display needed).
# Test tooling only.
set -u
cd "$(dirname "$0")"

pass=0
fail=0
expect() {           # expect NAME OUTPUT PATTERN...
  local name=$1 out=$2; shift 2
  for pattern in "$@"; do
    if grep -qE -- "$pattern" <<<"$out"; then pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL [$name] missing: $pattern"; echo "$out" | sed 's/^/    | /' | tail -20
    fi
  done
}

echo "== the unprobed game is untouched"
out=$(coil run 2>&1)
expect plain "$(printf 'x%sx' "$out")" '^xx$'

echo "== key presses, live and counted"
out=$(coil run --use snake.probes.keys 2>&1)
expect keys "$out" '^key down$' '^key left$' '^key quit$' 'down +4' 'right +1' \
  'call game-steer! · count by dx, dy' '0, 1 +4' '-1, 0 +1' 'input-lag · time' '7 calls' 'call render · time'

echo "== the same as JSON"
rm -f keys.jsonl keys-stats.json
coil run --use snake.probes.keys-json >/dev/null 2>&1
out=$(python3 -c '
import json
events = [json.loads(l) for l in open("keys.jsonl")]
print("events=%d" % len(events), "keys=" + ",".join(e["key"] for e in events))
stats = json.load(open("keys-stats.json"))
counts = {r["key"][0]: r["count"] for a in stats["aggregations"] if a["kind"] == "count" for r in a["rows"]}
print("down=%d final=%s" % (counts["down"], stats["final"]))
lag = [a for a in stats["aggregations"] if a["kind"] == "time"][0]
print("lag_unit=%s lag_count=%d" % (lag["unit"], lag["rows"][0]["count"]))
')
expect json "$out" 'events=8 keys=down,right,up,down,left,down,down,quit' 'down=4 final=True' 'lag_unit=ns lag_count=7'
rm -f keys.jsonl keys-stats.json

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
