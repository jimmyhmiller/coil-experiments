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

  empty() {}
}
