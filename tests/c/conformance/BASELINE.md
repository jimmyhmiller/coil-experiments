# C frontend conformance baseline

This is a reproducible corpus pass rate, not an ISO conformance percentage.

| Suite | Revision | Passed | Applicable | Pass rate | Explicit skips |
| --- | --- | ---: | ---: | ---: | ---: |
| c-testsuite | `5c7275656d751de0e68b2d340a95b5681858ed07` | 181 | 219 | 82.6% | 1 |
| tinycc | `2ba12e83b3599ca8f5d50c179fe5138fe956f0c9` | 59 | 111 | 53.2% | 26 |

## c-testsuite

- c11: 0/2 (0.0%)
- c89: 147/174 (84.5%)
- c99: 34/43 (79.1%)
- outcomes: compile-fail=35, output-mismatch=1, pass=181, run-fail=2
- explicit non-frontend/platform skips: 1

### Failures

| Test | Result | Detail |
| --- | --- | --- |
| `00010.c` | compile-fail | error: in 'main': break to unknown loop label ':goto-next-__c_label_3' |
| `00025.c` | compile-fail |       --link-flag on the command line. |
| `00035.c` | compile-fail | error: in 'main': cannot infer type argument 'T' for 'coil.core.!='; provide it explicitly: (coil.core.!= [<types>] ...) |
| `00043.c` | compile-fail | error: struct 'c_program.s' field 'nest': unknown type 's___unnamed_at_{work}/c-testsuite/00043/00043_c_3_5_' |
| `00046.c` | compile-fail | error: struct 'c_program.s' field 'anon': unknown type 's___anonymous_at_{work}/c-testsuite/00046/00046_c_3_2_' |
| `00047.c` | compile-fail | 2 errors |
| `00050.c` | compile-fail | error: struct 'c_program.S2' field 'anon': unknown type 'S2___anonymous_at_{work}/c-testsuite/00050/00050_c_9_2_' |
| `00051.c` | run-fail | exit 1 |
| `00053.c` | compile-fail | error: in 'main': struct 'c_program.T' has no field 'y' |
| `00054.c` | compile-fail | error: in 'main': cannot infer type argument 'T' for 'coil.core.!='; provide it explicitly: (coil.core.!= [<types>] ...) |
| `00055.c` | compile-fail | error: in 'main': cannot infer type argument 'T' for 'coil.core.!='; provide it explicitly: (coil.core.!= [<types>] ...) |
| `00088.c` | compile-fail | error: in 'main': cannot infer type argument 'T' for 'coil.core.!='; provide it explicitly: (coil.core.!= [<types>] ...) |
| `00089.c` | compile-fail | 2 errors |
| `00092.c` | run-fail | exit 2 |
| `00095.c` | compile-fail | error: in 'c_program.c_foo': unbound variable 'main' |
| `00115.c` | compile-fail | error: in 'c_program.__c_global_s': store! value has type (ptr i8) but expected (array i8 4) |
| `00120.c` | compile-fail | error: function 'c_program.__c_global_s' return type: unknown type '_unnamed_at_{work}/c-testsuite/00120/00120_c_1_1_' |
| `00124.c` | compile-fail | 2 errors |
| `00130.c` | compile-fail | error: in 'main': alloc: unknown type 'char__*_' |
| `00143.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00149.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00150.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00151.c` | compile-fail | 2 errors |
| `00189.c` | compile-fail | 3 errors |
| `00197.c` | output-mismatch | expected 40 bytes, got 40 |
| `00199.c` | compile-fail | error: in 'c_program.c_henry': break to unknown loop label ':goto-inner-__c_label_3' |
| `00204.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00207.c` | compile-fail | 2 errors |
| `00208.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00209.c` | compile-fail | error: unknown type 'int__*_' |
| `00210.c` | compile-fail | error: in 'main': unbound variable 'actual_function' |
| `00211.c` | compile-fail |       --link-flag on the command line. |
| `00213.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00214.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00215.c` | compile-fail |       --link-flag on the command line. |
| `00217.c` | compile-fail | error: in 'c_program.__c_global_t': store! value has type (ptr i8) but expected (array i8 10) |
| `00219.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `00220.c` | compile-fail | error: in 'main': alloc: unknown type 'wchar_t' |

## tinycc

- outcomes: compile-fail=41, output-mismatch=11, pass=59
- explicit non-frontend/platform skips: 26

### Failures

| Test | Result | Detail |
| --- | --- | --- |
| `03_struct.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `101_cleanup.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `102_alignas.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `103_implicit_memmove.c` | compile-fail |       --link-flag on the command line. |
| `105_local_extern.c` | compile-fail |       --link-flag on the command line. |
| `106_versym.c` | compile-fail | error: unknown type 'pthread_cond_t' |
| `107_stack_safe.c` | compile-fail |       --link-flag on the command line. |
| `108_constructor.c` | compile-fail |       --link-flag on the command line. |
| `118_switch.c` | output-mismatch | expected 642 bytes, got 620 |
| `119_random_stuff.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `11_precedence.c` | compile-fail |       --link-flag on the command line. |
| `122_vla_reuse.c` | compile-fail | error: in 'main': alloc: unknown type 'int_n___100_+_1_' |
| `123_vla_bug.c` | compile-fail | 2 errors |
| `124_atomic_counter.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `129_scopes.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `130_large_argument.c` | compile-fail | 2 errors |
| `133_old_func.c` | compile-fail | error: in 'main': argument 1 to 'c_program.c_fx' has type f64 but expected f32 |
| `136_atomic_gcc_style.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `137_funcall_struct_args.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `144_tls.c` | compile-fail | error: unknown type 'pthread_t' |
| `18_include.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `22_floating_point.c` | output-mismatch | expected 805 bytes, got 696 |
| `33_ternary_op.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `35_sizeof.c` | compile-fail | error: struct 'c_program.__c_anon_record_0' field 'd': unknown type 'int__' |
| `36_array_initialisers.c` | output-mismatch | expected 186 bytes, got 184 |
| `38_multiple_array_index.c` | output-mismatch | expected 60 bytes, got 66 |
| `39_typedef.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `42_function_pointer.c` | compile-fail | 3 errors |
| `46_grep.c` | output-mismatch | expected 65 bytes, got 147 |
| `51_static.c` | output-mismatch | expected 40 bytes, got 40 |
| `54_goto.c` | compile-fail | error: in 'c_program.c_henry': break to unknown loop label ':goto-inner-__c_label_3' |
| `70_floating_point_literals.c` | output-mismatch | expected 590 bytes, got 436 |
| `71_macro_empty_arg.c` | output-mismatch | expected 3 bytes, got 2 |
| `73_arm64.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `76_dollars_in_identifiers.c` | output-mismatch | expected 131 bytes, got 130 |
| `78_vla_label.c` | compile-fail | 2 errors |
| `79_vla_continue.c` | compile-fail | 5 errors |
| `80_flexarray.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `81_types.c` | compile-fail | 7 errors |
| `82_attribs_position.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `83_utf8_in_identifiers.c` | output-mismatch | expected 28 bytes, got 42 |
| `84_hex-float.c` | compile-fail |       --link-flag on the command line. |
| `87_dead_code.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `88_codeopt.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `89_nocode_wanted.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `90_struct-init.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `91_ptr_longlong_arith32.c` | compile-fail | error: in 'c_program.__c_global_t': store! value has type (ptr i8) but expected (array i8 10) |
| `93_integer_promotion.c` | compile-fail | error: in 'main': cannot infer type argument 'T' for 'coil.core.!='; provide it explicitly: (coil.core.!= [<types>] ...) |
| `94_generic.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `95_bitfields.c` | output-mismatch | expected 4817 bytes, got 5477 |
| `95_bitfields_ms.c` | compile-fail | error: C reader: typed-AST frontend failed |
| `97_utf8_string_literal.c` | compile-fail | error: in 'main': alloc: unknown type 'wchar_t' |

Regenerate with:

```sh
python3 scripts/c-conformance.py --suite all --write-report tests/c/conformance/BASELINE.md
```
