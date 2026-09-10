type Shape = { x: number };
const asserted = { x: 1 } as Shape;
const literal = "fixed" as const;
const checked = { x: 1 } satisfies Shape;
