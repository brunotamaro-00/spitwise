import type { User } from "@/types";
import { api } from "./client";

export const listUsers = async (): Promise<User[]> => (await api.get("/users")).data;
export const getMe = async (): Promise<User> => (await api.get("/auth/me")).data;
// La queryKey ["stops"] es una sola: el fetcher vive en api/cities.
export { getStops as listStops } from "./cities";
