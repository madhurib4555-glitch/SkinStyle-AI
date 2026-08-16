import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

/**
 * Config for the visual-render harness only.
 *
 * Run: npx vitest run --config vitest.render.mts
 * Writes /tmp/render.html for screenshotting. Kept separate so the harness
 * never runs as part of `npm test`.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/render-static.tsx"],
  },
});
