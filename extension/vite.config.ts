import { copyFileSync, cpSync } from "node:fs";
import { resolve } from "node:path";

import { defineConfig, type Plugin } from "vitest/config";

// Copies manifest.json and icons/ into dist so `extension/dist` can be loaded unpacked in Chrome.
function copyManifest(): Plugin {
  return {
    name: "copy-manifest",
    apply: "build",
    writeBundle() {
      const root = import.meta.dirname;
      copyFileSync(resolve(root, "manifest.json"), resolve(root, "dist/manifest.json"));
      cpSync(resolve(root, "icons"), resolve(root, "dist/icons"), { recursive: true });
    },
  };
}

// Popup build (ES modules). The content script is built separately as one classic script
// (vite.content.config.ts), because chrome.scripting.executeScript cannot load ES imports.
export default defineConfig({
  plugins: [copyManifest()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: { input: { popup: resolve(import.meta.dirname, "popup.html") } },
  },
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "happy-dom",
  },
});
