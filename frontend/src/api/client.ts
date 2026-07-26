import axios from "axios";

import { resetSessionCache } from "@/lib/queryClient";

export function authHeader(): Record<string, string> {
  const t = localStorage.getItem("auth_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export const api = axios.create({ baseURL: "/api/v1" });

/** Mensaje accionable de un error de la API, con `fallback` si no hay ninguno.
 *  El backend manda el motivo real en `detail` ("el cashback fijo no puede
 *  superar el monto del gasto", "Parada desconocida: …"); sin esto el usuario
 *  veía siempre el mismo texto genérico y no sabía qué corregir. */
export function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  // 422 de Pydantic: lista de {loc, msg}. Alcanza con el primero.
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
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
