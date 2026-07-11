import type { Balance, CategorySpend, CitySpend, Summary, TimePoint } from "@/types";
import { api } from "./client";

export const getBalance = async (): Promise<Balance> => (await api.get("/balance")).data;
export const getSummary = async (): Promise<Summary> => (await api.get("/dashboard/summary")).data;
export const getByCity = async (): Promise<CitySpend[]> => (await api.get("/dashboard/by-city")).data;
export const getByCategory = async (): Promise<CategorySpend[]> => (await api.get("/dashboard/by-category")).data;
export const getTimeseries = async (): Promise<TimePoint[]> => (await api.get("/dashboard/timeseries")).data;
