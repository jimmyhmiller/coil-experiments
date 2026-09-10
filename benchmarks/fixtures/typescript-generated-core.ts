"use client"

import "side-effects"
import DefaultValue from "default-module"
import * as Namespace from "namespace-module"
import { runtime as local, type Erased } from "named-module"

type Pair<T> = { left: T; right: T | null };

export function combine<T>(a: number, b: number): number {
  let bits: number = (a & b) ^ (a | b)
  bits <<= 2
  bits %= 97
  return ~bits
}

export function renderPair({ left, right = 0 }: Pair<number>): number {
  return left + right
}

const increment = (value: number): number => value + 1
const destructured = ({ left, right: local = 1, ...rest }, [first, ...tail]) => {
  return left + local
}

const View = ({ value, ...props }) => (
  <section {...props} data-value={value}>
    <span>{value}</span>
    <br />
  </section>
)

export { View as PairView, renderPair }
