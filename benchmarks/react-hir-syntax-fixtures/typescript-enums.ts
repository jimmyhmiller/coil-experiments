enum Direction {
  Up,
  Down = 2,
  "quoted" = "value",
  ['computed'] = 4,
  [`template`],
}

export const enum Bit {
  None,
  Read = 1,
  Write = 2,
}

declare enum AmbientCode {
  Unknown,
  Named = "named",
}
