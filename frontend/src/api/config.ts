import type { AppConfig } from "@/types";
import { api } from "./client";

export const getConfig = async (): Promise<AppConfig> => (await api.get("/config")).data;

/** Igual que `getConfig` pero sin JWT: el banner de demo tiene que renderizar
 *  en /login, antes de que exista un token. */
export const getPublicConfig = async (): Promise<AppConfig> =>
  (await api.get("/public-config")).data;
