declare function convert<T>(input: T): T
declare function convert(input: string): number;
function convert(input: unknown): unknown { return input; }

declare class Declared<T> {
  readonly value: T;
  method<U>(input: U): U;
}

abstract class Base<T> {
  abstract method<U>(input: U): T;
}
