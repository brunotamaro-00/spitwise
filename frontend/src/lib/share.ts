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

/** Día siguiente a una fecha pura YYYY-MM-DD, en la misma escala (sin husos). */
function nextDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + 1));
  return dt.toISOString().slice(0, 10);
}

/** ¿Este gasto necesita confirmación manual (aviso en /movimientos)?
 *  - `awaiting`: llegó la fecha, TC lockeado por el server → siempre.
 *  - `pending`: aviso desde 1 día antes de su fecha de pago.
 *  Sale del aviso al confirmarse (status → confirmed).
 *
 *  `today` es una fecha pura YYYY-MM-DD y debe venir del viaje (`TripPace.as_of`),
 *  no del reloj del dispositivo: el server decide `awaiting` con la tz de la
 *  parada activa, así que un teléfono en otro huso movía el aviso un día entero. */
export function needsConfirmation(mv: Movement, today: string): boolean {
  if (mv.type !== "expense") return false;
  if (mv.status === "awaiting") return true;
  if (mv.status === "pending" && mv.payment_date) {
    return mv.payment_date <= nextDay(today);
  }
  return false;
}
