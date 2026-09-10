const matcher = /a(?:b|c)+/giu;
const characterClass = /[/\\]+/g;
const escapedSlash = /foo\/bar/m;
const unicodeSets = /[a-z&&[^q]]/v;
consume(matcher.test(value), value / 2, /\d+/.test(value));
