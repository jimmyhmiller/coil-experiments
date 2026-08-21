# C frontend conformance baseline

This is a reproducible corpus pass rate, not an ISO conformance percentage.

| Suite | Revision | Passed | Applicable | Pass rate | Explicit skips |
| --- | --- | ---: | ---: | ---: | ---: |
| c-testsuite | `5c7275656d751de0e68b2d340a95b5681858ed07` | 205 | 219 | 93.6% | 1 |
| tinycc | `2ba12e83b3599ca8f5d50c179fe5138fe956f0c9` | 96 | 106 | 90.6% | 31 |

## c-testsuite

- c11: 0/2 (0.0%)
- c89: 166/174 (95.4%)
- c99: 39/43 (90.7%)
- outcomes: compile-fail=12, output-mismatch=1, pass=205, run-fail=1
- explicit non-frontend/platform skips: 1

### Failures

| Test | Result | Detail |
| --- | --- | --- |
| `00010.c` | compile-fail | error: in 'main': break to unknown loop label ':goto-next-__c_label_3' |
| `00025.c` | compile-fail | error: C symbol 'strlen' is declared twice with different signatures: 'coil.io.strlen' is i64 (ptr), 'c_program.strlen' is i32 (ptr). One C symbol, one signature: fix the types to match, or use a different symbol |
| `00043.c` | compile-fail | error: in 'main': field access needs a pointer to a struct, got (ptr i8) |
| `00046.c` | compile-fail | error: struct 'c_program.s': duplicate field 'anon' |
| `00050.c` | compile-fail | error: field: missing field name |
| `00051.c` | run-fail | exit 1 |
| `00124.c` | compile-fail | 2 errors |
| `00143.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00149.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00150.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00151.c` | compile-fail | 2 errors |
| `00204.c` | output-mismatch | expected 3005 bytes, got 2929 |
| `00209.c` | compile-fail | error: unknown type 'int__*_' |
| `00213.c` | compile-fail | error: in 'main': break to unknown loop label ':goto-enterexprloop-__c_label_13' |

## tinycc

- outcomes: compile-fail=4, compile-timeout=2, output-mismatch=4, pass=96
- explicit non-frontend/platform skips: 31

### Failures

| Test | Result | Detail |
| --- | --- | --- |
| `101_cleanup.c` | compile-timeout |  |
| `119_random_stuff.c` | compile-timeout |  |
| `129_scopes.c` | output-mismatch | expected 957 bytes, got 3657 |
| `144_tls.c` | compile-fail | 2 errors |
| `22_floating_point.c` | compile-fail | error: in 'main': cast only converts among int, float, and ptr (got (slice u8) to (ptr i8)) |
| `73_arm64.c` | output-mismatch | expected 3053 bytes, got 2986 |
| `87_dead_code.c` | compile-fail | error: in 'main': break to unknown loop label ':goto-enterexprloop-__c_label_13' |
| `90_struct-init.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `95_bitfields.c` | output-mismatch | expected 4817 bytes, got 5597 |
| `95_bitfields_ms.c` | output-mismatch | expected 6051 bytes, got 6017 |

Regenerate with:

```sh
python3 scripts/c-conformance.py --suite all --write-report tests/c/conformance/BASELINE.md
```
