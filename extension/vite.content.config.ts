import { resolve } from "node:path";

import { defineConfig } from "vite";

// Content script: a single self-contained IIFE (dist/content.js) for chrome.scripting.
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: false,
    lib: {
      entry: resolve(import.meta.dirname, "src/content/index.ts"),
      formats: ["iife"],
      name: "scamlyContent",
      fileName: () => "content.js",
    },
  },
});
