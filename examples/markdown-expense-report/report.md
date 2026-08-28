# Expense report rendering

Create module `experiments.expense-report.report`.

Import `experiments.expense-report.ledger`. Export:

- `render(summary ledger/Summary, allocator (dyn coil.alloc/Allocator)) -> (slice u8)`

Return newly allocated text formatted exactly like this, including ordering and
the final newline:

```text
Expense report
Accepted: 5
Rejected: 2
Travel: 12500 cents
Meals: 7800 cents
Software: 4999 cents
Other: 1200 cents
Total: 26499 cents
```

Use the values supplied by the ledger accessors; do not recompute or parse CSV.
Use a `coil.str/StrBuf` or the appropriate standard formatting API rather than
fixed-size buffers.
