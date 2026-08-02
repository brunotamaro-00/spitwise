import { BedDouble, Plane, TrendingUp, UtensilsCrossed } from "lucide-react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { lodgingCoverage, tripCostRead } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import type { FixedBlock, TripCost } from "@/types";

/** Cuánto sale el viaje entero, y de qué está hecho.
 *
 *  Un solo focal: el total. Vivir, dormir y los generales bajan a filas que lo
 *  componen — el que scrollea quiere una respuesta, no tres cifras para restar.
 *  El bloque **no lleva color**: es plata, no juicio. La rampa `--color-heat-*`
 *  es el veredicto contra el plan, y el plan mide solo vivir.
 *
 *  Es el mismo bloque en el Dashboard y al pie de /presupuesto: dos totales del
 *  viaje calculados distinto era la forma garantizada de que la app se
 *  contradiga a sí misma. `children` es la única diferencia — /presupuesto le
 *  cuelga abajo el veredicto de vivir, el Dashboard no. */
export default function TripCostCard({
  cost,
  fixed,
  children,
}: {
  cost: TripCost;
  fixed: FixedBlock;
  children?: React.ReactNode;
}) {
  const read = tripCostRead(cost);
  const rows = [
    {
      icon: UtensilsCrossed,
      label: "Vivir",
      hint:
        cost.basis === "projected"
          ? "proyectado al ritmo de lo que ya cerraron"
          : "lo que llevan gastado hasta hoy",
      usd: cost.living_usd,
    },
    {
      icon: BedDouble,
      label: "Alojamiento",
      hint: lodgingCoverage(fixed, cost),
      usd: cost.lodging_projected_usd,
    },
    { icon: Plane, label: "Generales", hint: "vuelos, pases, seguros", usd: cost.general_usd },
  ];

  return (
    <Card className="p-5">
      <SectionHeader icon={TrendingUp} iconTone="teal" hint="por persona">
        Proyección del viaje
      </SectionHeader>

      <p className="mt-4 text-meta font-semibold uppercase tracking-caps text-ink-3">
        {read.label}
      </p>
      <p className="font-display text-4xl leading-none tracking-display text-ink font-tabular">
        <AnimatedUsd value={read.amountUsd} />
      </p>

      <div className="mt-4 flex flex-col">
        {rows.map(({ icon: Icon, label, hint, usd }) => (
          <div
            key={label}
            className="flex items-center gap-3 border-b border-border py-2.5 last:border-0"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink-3">
              <Icon size={16} strokeWidth={2} aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-ink-2">{label}</span>
              {hint && <span className="block text-meta font-medium text-ink-faint">{hint}</span>}
            </span>
            <span className="shrink-0 font-tabular text-sm font-bold text-ink">
              {formatUsd(usd, "whole")}
            </span>
          </div>
        ))}
      </div>

      {children}
    </Card>
  );
}
