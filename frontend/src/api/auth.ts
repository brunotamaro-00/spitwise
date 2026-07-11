import { api } from "./client";

export async function login(username: string, password: string): Promise<string> {
  const form = new URLSearchParams({ username, password });
  const { data } = await api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  localStorage.setItem("auth_token", data.access_token);
  return data.access_token;
}
export function logout() { localStorage.removeItem("auth_token"); }
export function isAuthenticated() { return !!localStorage.getItem("auth_token"); }
