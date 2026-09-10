type Props = { theme: "light" | "dark" };
const props = {} as Props;
const theme = props as Props["theme"];
const tuple = props satisfies Array<Props["theme"]>;
