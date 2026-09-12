export type { Foo, Bar as Baz };
export type { Qux } from "pkg";
export type * from "types";
export * as namespaceObject from "runtime";
export type * as typeNamespace from "types2";
export { type Hidden, value as renamed, "strange-name" as strange } from "mixed";
