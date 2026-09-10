const andValue = left && right;
const orValue = left || right;
const nullishValue = left ?? right;
const booleanChain = left && middle || right;
const nullishChain = left ?? middle ?? right;
const groupedMixA = (left ?? middle) || right;
const groupedMixB = left && (middle ?? right);
