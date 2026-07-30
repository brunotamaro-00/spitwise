import { resetSessionCache } from "@/lib/queryClient";

import { api } from "./client";

/** `username` elige quién sos (preferencia de vista); `password` es la del
 *  deploy, compartida — el backend la valida contra LOGIN_PASSWORDS salvo en la
 *  demo pública, que es de entrada libre. */
export async function loginAs(username: string, password: string): Promise<string> {
  const form = new URLSearchParams({ username, password });
  const { data } = await api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  // Antes de guardar el token nuevo: tirar datos del usuario anterior (me, totales, etc.).
  await resetSessionCache();
  localStorage.setItem("auth_token", data.access_token);
  return data.access_token;
}

export async function logout(): Promise<void> {
  await resetSessionCache();
  localStorage.removeItem("auth_token");
}

/** ¿Hay un token y todavía sirve? Chequear `exp` acá evita renderizar la app
 *  entera con un JWT vencido: sin esto disparaban todas las queries, cada una
 *  volvía 401 y el interceptor terminaba redirigiendo, con un flash de UI vacía
 *  y N requests fallidos en el medio. */
export function isAuthenticated() {
  const token = localStorage.getItem("auth_token");
  if (!token) return false;
  try {
    const { exp } = JSON.parse(atob(token.split(".")[1]!)) as { exp?: number };
    // Sin `exp` se asume válido: que lo resuelva el server.
    return exp === undefined || exp * 1000 > Date.now();
  } catch {
    return false;
  }
}
