# Expense ledger parser and aggregation

Create module `experiments.expense-report.ledger`.

The input format is UTF-8 CSV with exactly four comma-separated fields per data
row:

```text
date,category,description,amount_cents
2026-08-01,travel,Airport parking,2400
```

This deliberately small CSV dialect does not support quoted fields or commas
inside fields. The first non-empty row may be the exact header above and should
then be ignored. Empty rows are ignored. A data row is rejected when it does not
have four fields, its amount is not an integer, its amount is negative, or any
of its first three fields is empty. Parsing continues after rejected rows.

Recognized categories are `travel`, `meals`, and `software`. Syntactically valid
rows with any other category contribute to `other`.

Define a `Summary` struct holding accepted record count, rejected record count,
total cents, and cents for travel, meals, software, and other. Export `Summary`,
the following accessor functions, and `summarize`:

- `summarize(source (slice u8)) -> Summary`
- `accepted-count(summary Summary) -> i64`
- `rejected-count(summary Summary) -> i64`
- `total-cents(summary Summary) -> i64`
- `travel-cents(summary Summary) -> i64`
- `meals-cents(summary Summary) -> i64`
- `software-cents(summary Summary) -> i64`
- `other-cents(summary Summary) -> i64`

Use Coil standard-library string splitting and integer parsing. The returned
summary must own all information it needs; it must not retain views into input.
