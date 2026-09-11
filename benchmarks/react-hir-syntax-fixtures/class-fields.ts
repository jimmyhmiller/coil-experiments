class Base {}

class Fields extends Base {
  value = 1;
  optional?: string;
  definite!: number;

  constructor(value: number) {
    this.value = value;
  }

  add(amount: number, scale = 1): number {
    return this.value + amount * scale;
  }

  public static readonly version: number = 1;
  protected override reset(): void {}
  accessor current: number = 0;

  get doubled(): number {
    return this.value * 2;
  }

  set doubled(next: number) {
    this.value = next / 2;
  }

  static {
    this.version;
  }

  empty() {}
}

class ContextualMemberNames {
  static() {}
  readonly = 1;
  get = 2;
  set = 3;
}

class PrivateMembers {
  static #count: number = 0;
  #value = 1;

  #read(): number {
    return this.#value;
  }
}

const AnonymousClass = class extends Base {
  value = 1;
};

const NamedClass = class Inner {
  self() {
    return Inner;
  }
};

const computedName = "computed";

class ComputedMembers {
  [computedName] = 1;

  static ["factory"](value: number) {
    return value;
  }
}

interface FirstContract {}
interface SecondContract<T> {}

class ImplementsContracts extends Base
  implements FirstContract, SecondContract<string> {
  "quoted"(): void;
  42(): number;

  "quoted"() {}
  42() {
    return 42;
  }
}

const ImplementsExpression = class implements FirstContract {};
