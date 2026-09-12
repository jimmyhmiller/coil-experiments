type Accessors = {
  get value(): string;
  set value(next: string);
  get [Symbol.species](): Constructor;
  set "label"(next: string);
};
