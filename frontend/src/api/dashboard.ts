import type { Balance, CategorySpend, Summary, Timeline, TripPace } from "@/types";
import { api } from "./client";

export const getBalance = async (): Promise<Balance> => (await api.get("/balance")).data;
export const getSummary = async (): Promise<Summary> => (await api.get("/dashboard/summary")).data;
export const getByCategory = async (): Promise<CategorySpend[]> => (await api.get("/dashboard/by-category")).data;
export const getPace = async (): Promise<TripPace> => (await api.get("/dashboard/pace")).data;
export const getTimeline = async (): Promise<Timeline> => (await api.get("/dashboard/timeline")).data;
