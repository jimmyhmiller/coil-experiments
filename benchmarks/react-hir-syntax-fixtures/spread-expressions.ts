const array = [0, ...values, 1];
const sparse = [,,];
const mixed = [first,, ...rest,];
const object = {first: 1, ...source, last: 2};
invoke(...values, tail);
nested([...[1, 2]], {...source});
