import axios from "axios";

import { resetSessionCache } from "@/lib/queryClient";

export function authHeader(): Record<string, string> {
  const t = localStorage.getItem("auth_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export const api = axios.create({ baseURL: "/api/v1" });

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
