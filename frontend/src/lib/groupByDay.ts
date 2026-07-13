import type { Movement } from "@/types";

export type DayGroup = { date: string; items: Movement[] };

/** Total USD de los gastos de un grupo (los settlements no suman gasto). */
export function dayTotalUsd(items: Movement[]): number {
  return items.reduce((acc, m) => acc + (m.type === "expense" ? Number(m.amount_usd) : 0), 0);
}

/** Agrupa movimientos en bloques consecutivos por día, preservando el orden
 *  de entrada. `keyOf` elige qué fecha usar (imputada vs. de carga). */
export function groupByDay(
  movements: Movement[],
  keyOf: (m: Movement) => string = (m) => m.movement_date,
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
