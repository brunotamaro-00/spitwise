import axios from "axios";

import { resetSessionCache } from "@/lib/queryClient";

export function authHeader(): Record<string, string> {
  const t = localStorage.getItem("auth_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export const api = axios.create({ baseURL: "/api/v1" });

/** Lo que se dice cuando el request nunca llegó al server. Viajando es el error
 *  MÁS probable de todos, y el `fallback` de cada pantalla asume lo contrario:
 *  sin esta rama, guardar un gasto en un pueblo sin señal respondía "No se pudo
 *  guardar. Revisá el monto." — le echa la culpa al dato justo cuando el dato
 *  está bien. El texto también dice qué hacer, porque no hay cola offline. */
export const OFFLINE_MESSAGE =
  "Sin conexión con el servidor. Los datos siguen acá: probá de nuevo cuando vuelva la señal.";

/** ¿El error es de transporte y no del contenido del request? Cubre las tres
 *  formas que toma: el browser sin red, axios sin `response` (DNS//timeout/
 *  conexión rechazada) y los 5xx de gateway que devuelve un proxy cuando el
 *  backend no contesta. */
function isConnectionError(err: unknown): boolean {
  const e = err as { response?: { status?: number }; code?: string };
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true;
  if (!e?.response) return true;
  const status = e.response.status;
  return status === 502 || status === 503 || status === 504;
}

/** Mensaje accionable de un error de la API, con `fallback` si no hay ninguno.
 *  El backend manda el motivo real en `detail` ("el cashback fijo no puede
 *  superar el monto del gasto", "Parada desconocida: …"); sin esto el usuario
 *  veía siempre el mismo texto genérico y no sabía qué corregir.
 *
 *  Traductor ÚNICO de errores de la app: toda pantalla que muestre el motivo de
 *  una mutación fallida pasa por acá, así que arreglarlo acá lo arregla en
 *  todas (alta, edición, borrado, confirmación, saldo, plan de ciudad). */
export function errorDetail(err: unknown, fallback: string): string {
  if (isConnectionError(err)) return OFFLINE_MESSAGE;
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  // 422 de Pydantic: lista de {loc, msg}. Los `msg` los redacta Pydantic y
  // vienen SIEMPRE en inglés ("Input should be greater than 0"), así que no se
  // muestran: el `fallback` de la pantalla está en castellano y en contexto.
  // Los motivos de negocio del backend viajan como `detail` string, arriba.
  return fallback;
}

api.interceptors.request.use((config) => {
  Object.assign(config.headers, authHeader());
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      void resetSessionCache().finally(() => {
        localStorage.removeItem("auth_token");
        if (location.pathname !== "/login") location.assign("/login");
      });
    }
    return Promise.reject(err);
  },
);
