# Markdown-authored expense report CLI

This is a multi-module command-line application generated from behavioral
Markdown specifications. It reads an expense CSV, rejects malformed records,
aggregates accepted expenses by category, and prints an audit-friendly report.

Production sources originate in `ledger.md`, `report.md`, and `main.md`. The
generated sibling `.coil` files are persisted build artifacts. Hand-written
contracts exercise module boundaries independently of the generator.

```sh
./generate.sh
./build/expense-report fixtures/expenses.csv
```
