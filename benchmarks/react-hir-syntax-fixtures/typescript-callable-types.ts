type GenericFunction = <const T extends object, U = T>(this: T, value: U, ...rest: U[]) => asserts value is U;
type Constructor = new <T>(value: T) => Box<T>;
type AbstractConstructor = abstract new <T>(value: T) => Box<T>;
type PlainFunction = (this: Context, value?: string, ...rest: number[]) => void;
type EmptyFunction = () => void;
type CallableMembers = {
  readonly version?: string;
  <T>(value: T): T;
  new <T>(value: T): Box<T>;
  map?<T>(this: Context, value: T): T;
  readonly [name: string]: number;
  [index: number]: string;
};
