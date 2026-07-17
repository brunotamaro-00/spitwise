import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { QueryClient } from "@tanstack/react-query";

/** Offline-first: queries en localStorage. gcTime >= maxAge. */
export const PERSIST_MAX_AGE = 1000 * 60 * 60 * 24 * 7; // 7 días
export const QUERY_CACHE_KEY = "spitwise-query-cache";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { gcTime: PERSIST_MAX_AGE } },
});

export const queryPersister = createAsyncStoragePersister({
  storage: window.localStorage,
  key: QUERY_CACHE_KEY,
});

/** Username del JWT (`sub`). Sirve de buster para descartar caché ajena al restaurar. */
export function authCacheBuster(): string {
  const token = localStorage.getItem("auth_token");
  if (!token) return "anon";
  try {
    const payload = JSON.parse(atob(token.split(".")[1]!)) as { sub?: string };
    return (payload.sub || "anon").toLowerCase();
  } catch {
    return "anon";
  }
}

/** Limpia memoria + localStorage. Llamar en login, logout y 401. */
export async function resetSessionCache(): Promise<void> {
  await queryClient.cancelQueries();
  queryClient.clear();
  await queryPersister.removeClient();
}
