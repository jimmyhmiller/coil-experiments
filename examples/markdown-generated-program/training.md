# Training-plan calculation

Create the Coil module `experiments.markdown-demo.training`.

Import `experiments.markdown-demo.arithmetic` and use its public API where it
is useful. Export:

- `weekly-total(start i64, increase i64, weeks i64) -> i64`.

For a positive number of weeks, return the sum of an arithmetic training plan:
week zero has `start` miles, week one has `start + increase`, and so on. Clamp
negative `start`, `increase`, or `weeks` values to zero before calculating.
Use an iterative implementation rather than a closed-form formula so the
generated program exercises mutable local state and a loop.

The module does not need a `main` function.
