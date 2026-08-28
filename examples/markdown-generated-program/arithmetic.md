# Integer arithmetic helpers

Create the Coil module `experiments.markdown-demo.arithmetic`.

Export these functions:

- `clamp(value i64, minimum i64, maximum i64) -> i64`. Return `minimum` when
  `value` is lower, `maximum` when it is higher, and otherwise `value`.
- `ceil-div(numerator i64, denominator i64) -> i64`. Inputs are non-negative
  and the denominator is positive. Return integer division rounded upward,
  without using floating-point values.

The module does not need a `main` function.
