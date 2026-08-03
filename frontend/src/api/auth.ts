import { resetSessionCache } from "@/lib/queryClient";

import { api } from "./client";

/** Última persona con la que se entró en este dispositivo. Es una *pista* para
 *  el login, no una identidad: el JWT lo emite el backend (ver api/auth.py). */
const LAST_PERSON_KEY = "spitwise_last_person";

export function lastPerson(): string {
  try {
    return localStorage.getItem(LAST_PERSON_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberPerson(username: string) {
  try {
    localStorage.setItem(LAST_PERSON_KEY, username);
  } catch {
    /* Safari en modo privado tira al tocar localStorage: sin memoria, el próximo
       login entra con el usuario por defecto. No es motivo para fallar. */
  }
}

async function storeToken(token: string) {
  // Antes de guardar el token nuevo: tirar datos del usuario anterior (me, totales, etc.).
  await resetSessionCache();
  localStorage.setItem("auth_token", token);
}

/** Entrar. La contraseña es la del deploy, compartida — el backend la valida
 *  contra LOGIN_PASSWORDS salvo en la demo pública, que es de entrada libre.
 *  Quién sos NO se elige acá: se manda `lastPerson()` como pista para no
 *  hacerle cambiar de persona a Katia en cada sesión, y adentro está
 *  `switchUser`. En demo el backend ignora la pista y entra siempre igual. */
export async function login(password: string): Promise<string> {
  const form = new URLSearchParams({ username: lastPerson(), password });
  const { data } = await api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  await storeToken(data.access_token);
  return data.access_token;
}

/** Cambiar de persona ya adentro. La identidad viaja en el `sub` del JWT, así
 *  que no alcanza con un estado local: hace falta un token nuevo. */
export async function switchUser(username: string): Promise<string> {
  const { data } = await api.post("/auth/switch", { username });
  await storeToken(data.access_token);
  rememberPerson(username);
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
