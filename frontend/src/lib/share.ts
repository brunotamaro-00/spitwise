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

/** ¿Este gasto necesita confirmación manual (aviso en /movimientos)?
 *  - `awaiting`: llegó la fecha, TC lockeado por el server → siempre.
 *  - `pending`: aviso desde 1 día antes de su fecha de pago.
 *  Sale del aviso al confirmarse (status → confirmed). */
export function needsConfirmation(mv: Movement, today = new Date()): boolean {
  if (mv.type !== "expense") return false;
  if (mv.status === "awaiting") return true;
  if (mv.status === "pending" && mv.payment_date) {
    const cutoff = new Date(today);
    cutoff.setDate(cutoff.getDate() + 1); // hasta 1 día antes de la fecha
    // payment_date es YYYY-MM-DD (fecha pura). Armar la key con partes locales
    // (no toISOString, que corre a UTC y desfasa un día en husos positivos).
    const cutoffKey = `${cutoff.getFullYear()}-${String(cutoff.getMonth() + 1).padStart(2, "0")}-${String(cutoff.getDate()).padStart(2, "0")}`;
    return mv.payment_date <= cutoffKey;
  }
  return false;
}
