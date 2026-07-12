import type {
  CategorySpend,
  CityBreakdown,
  CityDaily,
  CitySummary,
  Movement,
  Stop,
} from "@/types";
import { api } from "./client";

/** Serializa `slugs` como query repetido (slugs=a&slugs=b), como espera FastAPI. */
function slugParams(slugs: string[]): string {
  const p = new URLSearchParams();
  for (const s of slugs) p.append("slugs", s);
  const q = p.toString();
  return q ? `?${q}` : "";
}

export const getStops = async (): Promise<Stop[]> => (await api.get("/stops")).data;

export const getCityBreakdown = async (): Promise<CityBreakdown[]> =>
  (await api.get("/dashboard/city/breakdown")).data;

export const getCitySummary = async (slugs: string[]): Promise<CitySummary> =>
  (await api.get(`/dashboard/city/summary${slugParams(slugs)}`)).data;

export const getCityByCategory = async (slugs: string[]): Promise<CategorySpend[]> =>
  (await api.get(`/dashboard/city/by-category${slugParams(slugs)}`)).data;

export const getCityDaily = async (slugs: string[]): Promise<CityDaily[]> =>
  (await api.get(`/dashboard/city/daily${slugParams(slugs)}`)).data;

export const getCityMovements = async (slugs: string[]): Promise<Movement[]> =>
  (await api.get(`/dashboard/city/movements${slugParams(slugs)}`)).data;
