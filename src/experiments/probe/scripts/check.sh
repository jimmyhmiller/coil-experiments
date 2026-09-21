#!/usr/bin/env bash
# End-to-end check for the probe experiment: builds the demo under each probe file
# and asserts on what comes out. Test tooling only; nothing here is part of probe.
#
#   scripts/check.sh          run everything
set -u
cd "$(dirname "$0")/.."

pass=0
fail=0
P=experiments.probe.demo

expect() {           # expect NAME OUTPUT PATTERN...
  local name=$1 out=$2; shift 2
  for pattern in "$@"; do
    if grep -qE -- "$pattern" <<<"$out"; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      echo "FAIL [$name] missing: $pattern"
      echo "$out" | sed 's/^/    | /' | tail -25
    fi
  done
}

refute() {           # refute NAME OUTPUT PATTERN
  if grep -qE -- "$3" <<<"$2"; then
    fail=$((fail + 1)); echo "FAIL [$1] unexpected: $3"
  else
    pass=$((pass + 1))
  fi
}

run() { coil run "$@" 2>&1; }

echo "== unprobed build is untouched"
out=$(run -- parse)
expect plain "$out" '^parsed: 2000$'
refute plain "$out" 'probe'

echo "== 1. stats for a function"
out=$(run --use $P.stats -- parse)
expect stats "$out" 'call parse-expr +2 sites in 2 functions' '6,000 calls' 'self ' 'p99 ~' '^parsed: 2000$'
out=$(run --use $P.callers -- parse)
expect callers "$out" 'parse-factor +4,000' 'evaluate +2,000' 'parser\.coil:[0-9]+:[0-9]+ +4,000'

echo "== 2. only the slow ones, with arguments"
out=$(run --use $P.slow -- db)
expect slow "$out" 'db\.coil:[0-9]+:[0-9]+ slow [0-9.]+ms: SELECT u\.\*' 'load-report +3 calls'
refute slow "$out" 'slow .*SELECT \* FROM users'

echo "== enter/call"
out=$(run --use $P.trace -- db)
expect trace "$out" '^-> load-user runs: SELECT \* FROM users' '^<- [0-9]+ rows in '

echo "== 3. spans"
out=$(run --use $P.frame -- frames)
expect frame "$out" 'frame · time' '180 calls' 'draw-sprites +180 calls' 'decode-chunk +180 calls' '── probe · [0-9.]+m?s ──'
refute frame "$out" 'draw-text +181 calls'          # load-assets runs outside the span
out=$(run --use $P.request -- server)
expect request "$out" 'request · time' '12 calls' '/users +6 calls' 'request on fd 10 failed with 500' 'load-user +4'
out=$(run --use $P.decode -- frames)
expect decode "$out" 'mark "decode" · time' '180 calls' 'vsync miss on frame 170' 'mark "vsync-miss" · count' '^ +18$'

echo "== 4. all file reads"
out=$(run --use $P.reads -- files)
expect reads "$out" 'files\.coil:[0-9]+:[0-9]+ Coil\.toml [0-9]+b ' 'open lang\.coil from coil\.fs/read-file' \
  'could not read no-such-file\.txt: Errno\(2\)' 'read-file +3'

echo "== 5. capture all HTTP calls"
python3 scripts/http_fixture.py 18473 &
fixture=$!
trap 'kill $fixture 2>/dev/null' EXIT
sleep 0.5
rm -f http.jsonl
out=$(run --use $P.capture -- http http://127.0.0.1:18473)
expect capture "$out" 'GET  /hello   -> 200' 'GET  refused  -> -1'
lines=$(cat http.jsonl 2>/dev/null)
expect capture-file "$lines" '"method":"POST","url":"http://127\.0\.0\.1:18473/echo","sent":\[\{"name":"X-Coil-Demo","value":"probe"\}\]' \
  '"status":404' '"body":"hello, probe\\n"' '"status":null,"received":null,"body":null,"error":\{"Transport":\[7,'
expect capture-count "$(wc -l < http.jsonl | tr -d ' ')" '^5$'
out=$(run --use $P.http-errors -- http http://127.0.0.1:18473)
expect http-errors "$out" 'net\.coil:[0-9]+:[0-9]+ GET http://127\.0\.0\.1:18473/boom -> 500' 'Transport\(7, '
refute http-errors "$out" 'bundled http_client'
refute http-errors "$out" '/hello ->'
out=$(run --use $P.chunks -- http http://127.0.0.1:18473)
expect chunks "$out" 'call net/count-chunk +1 site in 1 function' 'chunk of 13 bytes via count-chunk--probe-thunk' '13  \(1 event\)'
out=$(run --use $P.http-hosts -- http http://127.0.0.1:18473)
expect http-hosts "$out" '127\.0\.0\.1:18473 +[0-9]+ calls' '127\.0\.0\.1:1 +[0-9]+ calls'
kill $fixture 2>/dev/null
rm -f http.jsonl

echo "== 6. allocations, and every failure anywhere"
out=$(run --use $P.alloc -- files)
expect alloc "$out" 'sum request\.bytes by caller' 'hist request\.bytes' '[0-9]+ events  min '
out=$(run --use $P.errs -- errors)
expect errs "$out" 'skipped: not a Result' 'validate: BadInput\(quantity\)' 'submit: Timeout\(700\)' 'validate +8' 'submit +7'
refute errs "$out" 'tally'

echo "== JSON output"
json_ok() {          # every probe line on the stream parses, and has the types we expect
  python3 -c '
import json, sys
types = {}
for line in sys.stdin:
    line = line.strip()
    if not line.startswith("{"):
        continue
    obj = json.loads(line)
    types[obj.get("type", "record")] = types.get(obj.get("type", "record"), 0) + 1
    if obj.get("type") == "report":
        for agg in obj["aggregations"]:
            for row in agg["rows"]:
                assert isinstance(row["key"], list) and isinstance(row["count"], int)
print(" ".join("%s=%d" % kv for kv in sorted(types.items())))
'
}
out=$(run --use $P.json -- db | json_ok)
expect json "$out" 'print=15' 'report=[0-9]+'
coil build --use $P.slow -o /tmp/probe-json-demo >/dev/null 2>&1
out=$(PROBE_JSON=1 /tmp/probe-json-demo db 2>&1 | json_ok)
expect json-env "$out" 'print=3' 'report=1'
out=$(/tmp/probe-json-demo db 2>&1)
expect json-env-off "$out" 'slow [0-9.]+ms: SELECT'
refute json-env-off "$out" '"type"'
rm -f /tmp/probe-json-demo

echo "== two probes at once"
out=$(run --use $P.stats --use $P.callers -- parse)
expect both "$out" '6,000 calls' 'parse-factor +4,000' '^parsed: 2000$'

echo "== results arrive while the program is still running"
rm -f frames.txt
coil build --use $P.live -o /tmp/probe-live-demo >/dev/null 2>&1
/tmp/probe-live-demo frames >/dev/null 2>&1 &
demo=$!
sleep 1.2
if kill -0 $demo 2>/dev/null; then
  mid=$(cat frames.txt 2>/dev/null)
  expect live-midrun "$mid" 'frame · time' '[0-9]+ calls' 'draw-sprites'
  refute live-midrun "$mid" 'final'
else
  fail=$((fail + 1)); echo "FAIL [live] the demo finished before it could be observed mid-run"
fi
wait $demo
expect live-final "$(cat frames.txt)" 'final' '180 calls'
rm -f frames.txt /tmp/probe-live-demo

echo "== mistakes are errors, not silence"
out=$(coil check --use experiments.probe.tests.bad-span 2>&1)
expect bad-span "$out" 'a range span must close on `call F`'
out=$(coil check --use experiments.probe.tests.bad-syntax 2>&1)
expect bad-syntax "$out" 'syntax\.probe: line 2: expected an action'
out=$(coil check --use experiments.probe.tests.bad-nothing 2>&1)
expect bad-nothing "$out" 'matches nothing in this program'
out=$(coil check --use experiments.probe.tests.bad-var 2>&1)
expect bad-var "$out" '`sqll` is not available .* Available here: sql'
out=$(coil check --use experiments.probe.tests.bad-result 2>&1)
expect bad-result "$out" 'does not return a Result'
out=$(coil check --use experiments.probe.tests.bad-ambiguous 2>&1)
expect bad-ambiguous "$out" '`query` is ambiguous; name one of:.*demo\.db/query.*demo\.cache/query'

out=$(coil check --use experiments.probe.tests.bad-spanvar 2>&1)
expect bad-spanvar "$out" 'span-scoped variables .* are not implemented'
out=$(coil check --use experiments.probe.tests.bad-regex 2>&1)
expect bad-regex "$out" '`matches` \(regex\) is not implemented'

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
