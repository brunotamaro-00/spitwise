import { Gauge } from "lucide-react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatUsd, isZeroMoney } from "@/lib/format";
import type { TripPace } from "@/types";

/** "Ritmo del viaje": el $/día que importa según el estado del viaje.
 *  Pre-viaje: lo comprometido repartido en las noches (sin proyección).
 *  En viaje: run-rate real (devengado / noches vividas) + proyección suave.
 *  El alojamiento entra prorrateado por noche y los generales por todo el
 *  viaje, así el número no pica el día que se paga una reserva. */
export default function TripPaceCard({ pace }: { pace: TripPace }) {
  const t = pace.trip;
  const perDay = t.status === "not_started" ? t.avg_per_day_usd : t.run_rate_usd ?? t.avg_per_day_usd;
  const progress = t.total_nights > 0 ? Math.min(t.elapsed_nights / t.total_nights, 1) : 0;
  const showProjection = t.status === "in_progress" && t.elapsed_nights >= 3 && t.projected_total_usd;

  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between">
        <Label>Ritmo del viaje</Label>
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brick-bg text-brick">
          <Gauge size={16} strokeWidth={2} aria-hidden="true" />
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="font-display text-4xl leading-none font-tabular text-ink">
          <AnimatedUsd value={perDay ?? "0"} />
        </span>
        <span className="text-sm font-medium text-ink-3">
          {t.status === "not_started" ? "/día previsto" : "/día"}
        </span>
      </div>

      {t.status === "in_progress" && (
        <div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-brick transition-[width] duration-700"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <p className="mt-1.5 text-xs font-medium text-ink-3">
            Noche {t.elapsed_nights} de {t.total_nights}
          </p>
        </div>
      )}

      <div className="flex flex-col gap-1 text-sm text-ink-2">
        {t.status === "not_started" && (
          <span>
            <span className="font-tabular font-semibold">{formatUsd(t.total_usd)}</span> comprometidos ·{" "}
            {t.total_nights} noches
          </span>
        )}
        {showProjection && (
          <span>
            A este ritmo, el viaje ≈{" "}
            <span className="font-tabular font-semibold">{formatUsd(t.projected_total_usd!)}</span>
          </span>
        )}
        {t.status === "finished" && (
          <span>
            Viaje terminado ·{" "}
            <span className="font-tabular font-semibold">{formatUsd(t.total_usd)}</span> en{" "}
            {t.total_nights} noches
          </span>
        )}
        {!isZeroMoney(t.general_usd) && t.general_per_day_usd && (
          <span className="text-xs text-ink-3">
            Generales (vuelos, pases, seguros):{" "}
            <span className="font-tabular font-semibold">{formatUsd(t.general_usd)}</span> ≈{" "}
            <span className="font-tabular">{formatUsd(t.general_per_day_usd)}</span>/día
          </span>
        )}
      </div>
    </Card>
  );
}
