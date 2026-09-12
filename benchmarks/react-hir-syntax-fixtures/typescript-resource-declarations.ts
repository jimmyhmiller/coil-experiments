using resource: Disposable = acquire();
using first = openA(), second: Disposable = openB();
await using asyncResource: AsyncDisposable = acquireAsync();

using + 1;
await using + 1;

for (using item of resources) {
  consume(item);
}

for (await using item of asyncResources) {
  consume(item);
}

for (using of resources) {
  consume(using);
}
