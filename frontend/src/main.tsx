import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./index.css";

registerSW({ immediate: true });

// Offline-first: las queries persisten en localStorage y al abrir sin señal
// se muestran los últimos datos conocidos. gcTime >= maxAge para que la
// persistencia no descarte cachés vivos.
const PERSIST_MAX_AGE = 1000 * 60 * 60 * 24 * 7; // 7 días

const qc = new QueryClient({
  defaultOptions: { queries: { gcTime: PERSIST_MAX_AGE } },
});

const persister = createAsyncStoragePersister({
  storage: window.localStorage,
  key: "spitwise-query-cache",
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={qc}
      persistOptions={{ persister, maxAge: PERSIST_MAX_AGE, buster: "v1" }}
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
