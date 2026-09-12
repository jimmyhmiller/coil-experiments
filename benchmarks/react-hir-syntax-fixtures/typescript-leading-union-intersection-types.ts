type LeadingUnion =
  | string
  | number;

type SingleUnion = | boolean;

type LeadingIntersection =
  & { left: string }
  & { right: number };

type SingleIntersection = & object;
