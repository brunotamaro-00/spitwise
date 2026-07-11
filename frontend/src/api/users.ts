import type { Stop, User } from "@/types";
import { api } from "./client";

export const listUsers = async (): Promise<User[]> => (await api.get("/users")).data;
export const getMe = async (): Promise<User> => (await api.get("/auth/me")).data;
export const listStops = async (): Promise<Stop[]> => (await api.get("/stops")).data;
