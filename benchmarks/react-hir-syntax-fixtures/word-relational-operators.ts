const contained = key in object;
const matches = value instanceof Constructor;
const combined = key in object && value instanceof Constructor;
const grouped = (key in object) === matches;
