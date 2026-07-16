import type { AppConfig } from "@/types";
import { api } from "./client";

export const getConfig = async (): Promise<AppConfig> => (await api.get("/config")).data;
