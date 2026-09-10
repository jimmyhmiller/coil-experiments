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
