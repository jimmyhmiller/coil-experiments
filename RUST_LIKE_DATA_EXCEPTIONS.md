# Rust-like tree conversion data exceptions

These `.coil` files in the upstream Coil test corpus are intentionally malformed
source text used to test the native reader, diagnostics, or delimiter repair.
They are copied byte-for-byte by the tree converter because they are data, not
valid Coil programs. Every other `.coil` file, including all other files under
`tests/`, must be converted and exact-tree audited.

- `tests/balance/cases/mismatched-bracket.coil`
- `tests/balance/cases/stray-close-column0.coil`
- `tests/balance/cases/stray-close-inline.coil`
- `tests/balance/cases/two-damaged-forms.coil`
- `tests/balance/cases/typecheck-timeout.coil`
- `tests/compiler/features/terminated_hex_escape_c_byte_rejected.coil`
- `tests/compiler/features/terminated_hex_escape_empty_rejected.coil`
- `tests/compiler/features/terminated_hex_escape_missing_terminator_rejected.coil`
- `tests/compiler/features/terminated_hex_escape_range_rejected.coil`
- `tests/compiler/features/terminated_hex_escape_surrogate_rejected.coil`
- `tests/compiler/oracle/diag/inputs/01-parse-unclosed.coil`
- `tests/compiler/oracle/negative/lone-prefix.coil`
- `tests/compiler/oracle/negative/mismatched-delims.coil`
- `tests/compiler/oracle/negative/prefix-edges.coil`
- `tests/compiler/oracle/negative/unclosed-bracket.coil`
- `tests/compiler/oracle/negative/unclosed-paren.coil`
- `tests/compiler/oracle/negative/unexpected-close.coil`
- `tests/compiler/oracle/negative/unterminated-cstr.coil`
- `tests/compiler/oracle/negative/unterminated-escape.coil`
- `tests/compiler/oracle/negative/unterminated-string.coil`
- `tests/repro/paredit-balance-coil/input.coil`
