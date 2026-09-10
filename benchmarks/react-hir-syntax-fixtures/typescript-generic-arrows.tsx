const identity = <T,>(value: T): T => value;

const select = <
  TSource extends { id: string },
  TResult = TSource,
>(source: TSource, map: (value: TSource) => TResult) => {
  return map(source);
};
