interface Source {}
interface Derived<Item extends Source> extends Base<Item>, Namespace.Contract {
  readonly value?: Item;
  map<Result>(input: Item): Result;
}
interface Variance<in Input, out Output extends Source = Source> {
  input: Input;
  output: Output;
}

class ConstGeneric<const Value extends Source = Source>
  implements Variance<Value, Value> {
  input!: Value;
  output!: Value;
}

const checked = {} as Variance<Source, Source>;
const satisfied = {} satisfies Variance<Source, Source>;
