# Expense report command-line application

Create module `experiments.expense-report.main`.

Import the ledger and report modules plus appropriate standard filesystem,
allocation, string, and I/O facilities. Define native `main(argc, argv) -> i64`.

Behavior:

- Require exactly one argument after the executable name: a CSV path.
- On wrong arity, print `usage: expense-report FILE.csv` to standard error and
  return `64`.
- Read the complete file. On failure, print `expense-report: cannot read FILE`
  to standard error, substituting the supplied path, and return `66`.
- Otherwise summarize the CSV, render the report, write it to standard output,
  and return `0`.
- Free or close owned resources when the standard APIs require it.
