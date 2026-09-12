type GenericFunction = <const T extends object, U = T>(this: T, value: U, ...rest: U[]) => asserts value is U;
type Constructor = new <T>(value: T) => Box<T>;
type AbstractConstructor = abstract new <T>(value: T) => Box<T>;
