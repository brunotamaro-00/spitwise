import { Gauge } from "lucide-react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatUsd, isZeroMoney } from "@/lib/format";
import type { TripPace } from "@/types";

/** "Ritmo del viaje": el $/día que importa según el estado del viaje.
 *  Pre-viaje: lo comprometido en ciudades repartido en las noches.
 *  En viaje: run-rate real (devengado / noches vividas) + proyección.
 *  El alojamiento entra prorrateado por noche, así el número no pica el día que
 *  se paga una reserva. Los generales quedan fuera del ritmo — no pasan por
 *  ninguna ciudad — y se muestran aparte; solo la proyección los suma. */
export default function TripPaceCard({ pace }: { pace: TripPace }) {
  const t = pace.trip;
  const perDay = t.status === "not_started" ? t.avg_per_day_usd : t.run_rate_usd ?? t.avg_per_day_usd;
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
        <span className="font-display text-4xl leading-none tracking-[-0.02em] font-tabular text-ink">
          <AnimatedUsd value={perDay ?? "0"} />
        </span>
        <span className="text-sm font-medium text-ink-3">
          {t.status === "not_started" ? "/día previsto" : "/día"}
        </span>
      </div>

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
            + Generales aparte:{" "}
            <span className="font-tabular font-semibold">{formatUsd(t.general_usd)}</span> ≈{" "}
            <span className="font-tabular">{formatUsd(t.general_per_day_usd)}</span>/día
          </span>
        )}
      </div>
    </Card>
  );
}
