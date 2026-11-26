import { resolve } from "node:path";

import { defineConfig } from "vite";

// Dev-only dataset collector (dev/collector.ts): a self-contained IIFE outside dist/.
export default defineConfig({
  build: {
    outDir: "dist-dev",
    emptyOutDir: true,
    lib: {
      entry: resolve(import.meta.dirname, "dev/collector.ts"),
      formats: ["iife"],
      name: "scamlyCollector",
      fileName: () => "collector.js",
    },
  },
});
