const THEMES = { light: "", dark: ".dark" } as const

export type ChartConfig = {
  [k in string]: string
};

const result = THEMES.light;
