import { defineConfig } from "vitest/config";

// Build entries (content scripts, background, panel) are added in phase 6.
export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
  },
});
