import type { Category } from "@/types";
import { api } from "./client";

export const listCategories = async (): Promise<Category[]> => (await api.get("/categories")).data;
