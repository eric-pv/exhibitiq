import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// mode "single": one self-contained HTML file (JS/CSS inlined) for private
// preview artifacts that open directly from disk (DEVELOPMENT_PLAN.md §3).
export default defineConfig(({ mode }) => ({
  base: "./",
  plugins: mode === "single" ? [react(), viteSingleFile()] : [react()],
  build: {
    outDir: mode === "single" ? "dist-single" : "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
  },
  test: {
    environment: "jsdom",
    globals: true,
    testTimeout: 20000,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
  },
}));
