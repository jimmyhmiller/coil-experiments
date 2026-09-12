namespace Library.Core {
  export type Name = string;
  export const version: number = 1;
}

module Internal {
  export interface Entry {
    value: string;
  }
}

declare module "virtual-package" {
  export interface Options {
    enabled: boolean;
  }
}

declare module "bodyless-package";

declare global {
  interface Window {
    projectName: string;
  }
}
