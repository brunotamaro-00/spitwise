import { useQuery } from "@tanstack/react-query";

import { getPace } from "@/api/dashboard";
import { todayLocal } from "@/lib/format";

/** "Hoy" en la zona horaria del VIAJE (YYYY-MM-DD), no la del dispositivo.
 *
 *  El backend decide con la tz de la parada activa (`resolve_trip_timezone`):
 *  cuándo un gasto pasa a `awaiting`, a qué parada se imputa, qué TC aplica. Un
 *  teléfono que quedó en otro huso corre todas esas fechas un día entero, así
 *  que la UI toma la del server (`TripPace.as_of`) y solo cae al reloj local
 *  mientras la query no resolvió.
 *
 *  Comparte queryKey con el resto del dashboard: sin fetch extra. */
export function useTripToday(): string {
  const { data } = useQuery({ queryKey: ["dashboard", "pace"], queryFn: getPace });
  return data?.as_of ?? todayLocal();
}
