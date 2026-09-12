type IdentifierQuery = typeof value;
type QualifiedQuery = typeof Namespace.value;
type GenericQuery = typeof Namespace.factory<Result>;
type ImportedQuery = typeof import("pkg");
