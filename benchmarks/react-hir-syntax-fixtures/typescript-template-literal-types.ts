type Empty = ``;
type Greeting<T> = `hello ${T}`;
type Path<A, B> = `${A}.${B}`;
type Conditional<T> = `${T extends string ? T : never}`;
type Escaped = `\${notAType}`;
