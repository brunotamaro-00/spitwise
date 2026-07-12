import type { Movement } from "@/types";

export type DayGroup = { date: string; items: Movement[] };

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
