#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/../../../.." && pwd)
fixture="$root/src/apps/markdown-agent/tests"
output="$fixture/generated.coil"
attempt="$fixture/generated.coil.candidate.attempt"
no_contract="$fixture/no_contract.coil"
no_contract_attempt="$fixture/no_contract.coil.candidate.attempt"
markdown_contract="$fixture/markdown_contract.coil"
markdown_contract_attempt="$fixture/markdown_contract.coil.candidate.attempt"
coil_bin=${COIL_BIN:-/Users/jimmyhmiller/.cargo/bin/coil}

rm -f "$output" "$output.candidate" "$attempt" "$no_contract" "$no_contract.candidate" "$no_contract_attempt" "$markdown_contract" "$markdown_contract.candidate" "$markdown_contract_attempt"
"$coil_bin" run "$root/src/apps/markdown-agent/main.coil" -- \
  "$fixture/spec.md" \
  "$output" \
  experiments.markdown-agent.generated \
  "$fixture/consumer.coil" \
  "$fixture/fake-harness.sh" \
  "$coil_bin" \
  fake-model

test -f "$output"
test ! -f "$output.candidate"
"$coil_bin" check "$output"

# A valid target is authoritative and must not invoke the agent again.
rm -f "$attempt"
"$coil_bin" run "$root/src/apps/markdown-agent/main.coil" -- \
  "$fixture/spec.md" \
  "$output" \
  experiments.markdown-agent.generated \
  "$fixture/consumer.coil" \
  /definitely/not/an/agent \
  "$coil_bin" \
  fake-model
test ! -f "$attempt"

# Contracts are optional. With `-`, compilation is the acceptance gate and the
# generated module is installed without any consumer program.
"$coil_bin" run "$root/src/apps/markdown-agent/main.coil" -- \
  "$fixture/spec.md" \
  "$no_contract" \
  experiments.markdown-agent.no-contract \
  - \
  "$fixture/fake-harness.sh" \
  "$coil_bin" \
  fake-model
test -f "$no_contract"
"$coil_bin" check "$no_contract"

# A contract may originate as Markdown too. Materialize it without a recursive
# contract requirement, then execute the persisted Coil contract normally.
"$coil_bin" run "$root/src/apps/markdown-agent/main.coil" -- \
  "$fixture/contract_spec.md" \
  "$markdown_contract" \
  experiments.markdown-agent.markdown-contract \
  - \
  "$fixture/fake-harness.sh" \
  "$coil_bin" \
  fake-model
"$coil_bin" run "$markdown_contract"

rm -f "$output" "$attempt" "$no_contract" "$no_contract_attempt" "$markdown_contract" "$markdown_contract_attempt"
printf 'markdown-agent end-to-end tests passed\n'
