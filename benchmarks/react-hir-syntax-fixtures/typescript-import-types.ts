type Module = import("pkg");
type Member = import("pkg").Foo.Bar;
type Generic = import("pkg").Foo<string, number>;
type WithOptions = import("data.json", { with: { type: "json" } });
