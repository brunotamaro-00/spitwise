import type { Movement } from "@/types";
import { myShare } from "@/lib/share";

export type DayGroup = { date: string; items: Movement[] };

/** Total USD bruto de los gastos de un grupo (los settlements no suman gasto). */
export function dayTotalUsd(items: Movement[]): number {
  return items.reduce((acc, m) => acc + (m.type === "expense" ? Number(m.amount_usd) : 0), 0);
}

/** Total de la parte del usuario (misma semántica que analytics). */
export function dayTotalShare(items: Movement[], userId: number): number {
  return items.reduce((acc, m) => acc + myShare(m, userId), 0);
}

/** Día local (YYYY-MM-DD) de la fecha de carga: el único eje temporal que queda. */
export function createdDayKey(m: Movement): string {
  const d = new Date(m.created_at);
  const y = d.getFullYear();
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  const da = String(d.getDate()).padStart(2, "0");
  return `${y}-${mo}-${da}`;
}

/** Agrupa movimientos en bloques consecutivos por día de carga, preservando el
 *  orden de entrada. */
export function groupByDay(
  movements: Movement[],
  keyOf: (m: Movement) => string = createdDayKey,
): DayGroup[] {
  const out: DayGroup[] = [];
  for (const m of movements) {
    const key = keyOf(m);
    const last = out[out.length - 1];
    if (last && last.date === key) last.items.push(m);
    else out.push({ date: key, items: [m] });
  }
  return out;
}
