type Named = [first: string, second?: number, ...rest: boolean[]];
type Plain = [string, number?, ...boolean[]];
type LeadingRest = [...string[], number];
