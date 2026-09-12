type StringIndex = {
  readonly [name: string]: number;
};

interface SymbolIndex {
  [token: symbol]: unknown;
}
