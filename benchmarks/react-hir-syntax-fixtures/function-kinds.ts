async function loadValue() {
  return await load()
}

function* values() {
  yield first
  yield second
}

async function* streamValues() {
  yield await load()
}
