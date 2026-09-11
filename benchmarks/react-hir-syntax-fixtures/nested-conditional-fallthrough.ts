function select(value: number) {
  if (value > 0) {
    if (value > 10) {
      return "large"
    }
    value = value + 1
  } else {
    if (value < -10) {
      return "small"
    }
    value = value - 1
  }
  return value
}
