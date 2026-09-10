const member = object?.property;
const computed = object?.[key];
const called = callback?.(member, computed);
const continued = object?.property.method();
