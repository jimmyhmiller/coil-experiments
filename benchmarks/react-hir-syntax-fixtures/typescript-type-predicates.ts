type Assertion = asserts value;
type AssertionType = asserts value is string;
type ThisAssertion = asserts this is Service;

function isString(value: unknown): value is string {
  return true;
}

function assertsString(value: unknown): asserts value is string {
  return;
}
