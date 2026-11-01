import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
// Build tooling only. This never enters the client bundle.
// @ts-expect-error Build helper is a native Node module outside TypeScript source.
import { writeStaticWorker } from "../../scripts/web/static-worker.mjs";

export default defineConfig({
  plugins: [
    react(),
    (() => {
      let outDir = "";
      return {
        name: "arbit-static-worker",
        configResolved(config: { root: string; build: { outDir: string } }) {
          outDir = resolve(config.root, config.build.outDir);
        },
        async closeBundle() {
          await writeStaticWorker(outDir);
        },
      };
    })(),
  ],
  server: {
    strictPort: true,
    proxy: {
      "/auth": { target: "http://127.0.0.1:8000" },
      "/api": { target: "http://127.0.0.1:8000" },
    },
  },
  preview: {
    strictPort: true,
    proxy: {
      "/auth": { target: "http://127.0.0.1:8000" },
      "/api": { target: "http://127.0.0.1:8000" },
    },
  },
  build: { sourcemap: false, target: "es2022" },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
