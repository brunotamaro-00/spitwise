import type { Movement } from "@/types";

/** Parte del gasto que consumió `userId` (independiente de quién pagó).
 *  shared => mitad; payer_only => del pagador; other_only => del que no pagó. */
export function myShare(mv: Movement, userId: number): number {
  if (mv.type !== "expense") return 0;
  const amt = Number(mv.amount_usd);
  if (mv.split === "payer_only") return mv.paid_by === userId ? amt : 0;
  if (mv.split === "other_only") return mv.paid_by !== userId ? amt : 0;
  return amt / 2;
}

/** ¿El movimiento me involucra? Los settlements siempre (viaje de a dos). */
export function involvesMe(mv: Movement, userId: number): boolean {
  return mv.type === "settlement" || myShare(mv, userId) > 0;
}
