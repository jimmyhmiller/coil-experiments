const metadata = import.meta;
consume(import.meta.url);

function construct() {
  return new.target;
}
