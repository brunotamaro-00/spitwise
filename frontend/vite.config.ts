import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    // Offline: precache del shell (JS/CSS/fonts/brand) para abrir sin señal.
    // Los datos offline los resuelve la persistencia de TanStack Query.
    VitePWA({
      registerType: "autoUpdate",
      manifest: false, // usamos el manifest.webmanifest estático de public/
      workbox: {
        globPatterns: ["**/*.{js,css,html,woff2,png,svg,webmanifest}"],
        navigateFallbackDenylist: [/^\/api\//, /^\/webhooks\//],
      },
    }),
  ],
  resolve: { alias: { "@": "/src" } },
  server: { proxy: { "/api": "http://localhost:8000", "/webhooks": "http://localhost:8000" } },
  // Leído por vitest; el tipo de vite 8 (rolldown) no lo declara.
  // @ts-expect-error vitest-only key
  test: { environment: "jsdom", globals: true },
});
