type Element<T> = T extends readonly (infer U)[] ? U : never;
type Nested<T> = T extends string ? number : T extends bigint ? boolean : unknown;
type Keys<T> = keyof T;
type Query = typeof runtimeValue;
type Brand = unique symbol;
