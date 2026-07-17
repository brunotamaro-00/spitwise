import { resetSessionCache } from "@/lib/queryClient";

import { api } from "./client";

export async function login(username: string, password: string): Promise<string> {
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

export function isAuthenticated() {
  return !!localStorage.getItem("auth_token");
}
