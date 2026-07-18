import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./index.css";
import {
  authCacheBuster,
  CACHE_SCHEMA_VERSION,
  PERSIST_MAX_AGE,
  queryClient,
  queryPersister,
} from "./lib/queryClient";

registerSW({ immediate: true });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister: queryPersister,
        maxAge: PERSIST_MAX_AGE,
        // Usuario del JWT + schema: al cambiar cualquiera, se descarta la caché.
        buster: `${authCacheBuster()}:${CACHE_SCHEMA_VERSION}`,
      }}
    >
      {/* reducedMotion="user": toda animación de motion respeta el ajuste del OS. */}
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </MotionConfig>
    </PersistQueryClientProvider>
  </StrictMode>,
);
