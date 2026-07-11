import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": "/src" } },
  server: { proxy: { "/api": "http://localhost:8000", "/webhooks": "http://localhost:8000" } },
  // Leído por vitest; el tipo de vite 8 (rolldown) no lo declara.
  // @ts-expect-error vitest-only key
  test: { environment: "jsdom", globals: true },
});
