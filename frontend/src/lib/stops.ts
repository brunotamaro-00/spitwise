import type { Stop } from "@/types";

/** Parada del itinerario activa para una fecha ISO local (yyyy-mm-dd).
 *  Réplica de `_stop_in_range` del backend: intervalo semiabierto
 *  [arrival, departure) — el día de partida ya pertenece a la parada siguiente —
 *  y sin departure_date la parada queda vigente desde arrival en adelante. */
export function stopForDate(stops: Stop[], iso: string): Stop | undefined {
  const ordered = [...stops].sort((a, b) => (a.arrival_date ?? "").localeCompare(b.arrival_date ?? ""));
  for (const s of ordered) {
    if (s.arrival_date && s.departure_date && s.arrival_date <= iso && iso < s.departure_date) return s;
    if (s.arrival_date && !s.departure_date && s.arrival_date <= iso) return s;
  }
  return undefined;
}
