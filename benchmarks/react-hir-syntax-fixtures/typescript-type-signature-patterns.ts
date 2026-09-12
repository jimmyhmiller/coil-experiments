type FunctionPattern = (
  { x, y: alias = 1, ...rest }: { x: number; y?: number },
  [head, , ...tail]: [string, undefined, ...number[]],
) => void;

type ConstructorPattern = new ({ value }: { value: string }) => object;

type MethodPattern = {
  method({ x }: { x: number }): void;
};

type UntypedPattern = ({ value }) => void;
type RestPattern = (...[head, ...tail]: [string, ...number[]]) => void;
