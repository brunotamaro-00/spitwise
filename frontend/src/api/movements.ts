import type { Movement } from "@/types";
import { api } from "./client";

export async function listMovements(): Promise<Movement[]> {
  return (await api.get("/movements")).data;
}
export async function createMovement(body: Partial<Movement>): Promise<Movement> {
  return (await api.post("/movements", body)).data;
}
export async function updateMovement(id: number, body: Partial<Movement>): Promise<Movement> {
  return (await api.patch(`/movements/${id}`, body)).data;
}
export async function deleteMovement(id: number): Promise<void> {
  await api.delete(`/movements/${id}`);
}
/** Confirma un gasto vencido (pending/awaiting). `paidBy` opcional corrige quién pagó. */
export async function confirmMovement(id: number, paidBy?: number): Promise<Movement> {
  return (await api.post(`/movements/${id}/confirm`, paidBy != null ? { paid_by: paidBy } : {})).data;
}
