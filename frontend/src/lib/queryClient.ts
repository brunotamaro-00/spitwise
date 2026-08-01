import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { QueryClient } from "@tanstack/react-query";

/** Offline-first: queries en localStorage. gcTime >= maxAge. */
export const PERSIST_MAX_AGE = 1000 * 60 * 60 * 24 * 7; // 7 días
export const QUERY_CACHE_KEY = "spitwise-query-cache";
/** Subir cuando cambia forma/contenido de datos cacheados (ej. rename de categoría).
 *  Forma parte del `buster` de PersistQueryClient: al cambiar, se descarta la
 *  caché restaurada en todos los clientes sin pedir logout. */
export const CACHE_SCHEMA_VERSION = "2";

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

/** Claves derivadas del ledger: todo lo que cambia de valor cuando se crea,
 *  edita, borra, confirma o salda un movimiento.
 *
 *  Vive acá y no en cada `onSuccess` porque el bug que arregla fue exactamente
 *  ese: `["budget"]` se sumó con /presupuesto y ninguna de las cinco mutaciones
 *  se enteró, así que la página seguía diciendo "te sobran USD 105/día" después
 *  de cargar un gasto de USD 200 en esa misma ciudad. Una pantalla derivada
 *  nueva se agrega acá, en un solo lugar, y todas las mutaciones la heredan. */
const LEDGER_KEYS = [
  ["movements"],
  ["balance"],
  ["dashboard"], // cubre summary, cat y pace (prefijo)
  ["city"], // cubre summary, cat y movs por selección (prefijo)
  ["budget"],
] as const;

/** Invalida todo lo que depende del ledger. Llamar desde cualquier mutación que
 *  toque movimientos. NO incluye `["stops"]`, `["categories"]`, `["users"]` ni
 *  `["me"]`: son catálogo, no cambian al cargar un gasto. */
export function invalidateLedger(qc: QueryClient): void {
  for (const queryKey of LEDGER_KEYS) qc.invalidateQueries({ queryKey });
}

/** Limpia memoria + localStorage. Llamar en login, logout y 401. */
export async function resetSessionCache(): Promise<void> {
  await queryClient.cancelQueries();
  queryClient.clear();
  await queryPersister.removeClient();
}
