import type { BudgetAnalysis, StopBudget } from "@/types";
import { api } from "./client";

export const getBudget = async (): Promise<BudgetAnalysis> => (await api.get("/budget")).data;

export const putStopBudget = async (
  slug: string,
  body: { daily_min_usd: string; daily_max_usd: string; note?: string | null },
): Promise<StopBudget> => (await api.put(`/budget/${slug}`, body)).data;

export const deleteStopBudget = async (slug: string): Promise<void> => {
  await api.delete(`/budget/${slug}`);
};
