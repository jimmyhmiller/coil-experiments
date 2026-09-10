const decimals = [0, 123, 1., .5, 1.25, 1e3, 1E-3, 1_000_000, 12.34_56e7_8];
const radices = [0xff, 0XCAFE, 0b1010_0101, 0B11, 0o755, 0O7_7];
const bigints = [0n, 123n, 1_000n, 0xffffn, 0b101n, 0o77n];
consume(-.5, decimals, radices, bigints);
