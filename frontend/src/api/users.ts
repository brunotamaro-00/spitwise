import type { User } from "@/types";
import { api } from "./client";

export const listUsers = async (): Promise<User[]> => (await api.get("/users")).data;
