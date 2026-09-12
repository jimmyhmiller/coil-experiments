const plain = tag`hello ${name}!`;
const generic = namespace.tag<A, B>`value:${value}`;
const chained = factory()<Result>`done:${result}`.length;
const boundary = tag`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa${edge}`;
