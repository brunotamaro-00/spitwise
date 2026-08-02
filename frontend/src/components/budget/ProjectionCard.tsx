import { BedDouble, Plane, TrendingUp, UtensilsCrossed } from "lucide-react";
import { useMemo } from "react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import {
  coverageLine,
  lodgingCoverage,
  projectionRead,
  tripCostRead,
  type BandLevel,
} from "@/lib/budget";
import { formatUsd, parseMoney } from "@/lib/format";
import type { BudgetAnalysis } from "@/types";

import { bandText } from "./bandText";
import ProjectionBar from "./ProjectionBar";

/** El paso de la rampa que le toca al veredicto de la proyección. Terminar
 *  abajo del piso es ahorrar, no un error; adentro es el objetivo. */
const LEVEL: Record<"inside" | "over" | "under", BandLevel> = {
  under: "save",
  inside: "plan",
  over: "far",
};

const TEXT: Record<BandLevel, string> = {
  save: "text-accent-teal-ink",
  plan: "text-accent-green-ink",
  edge: "text-accent-amber-ink",
  over: "text-heat-over-ink",
  far: "text-danger-ink",
};

/** Cuánto sale el viaje entero, y recién después si eso está en plan.
 *
 *  Un solo focal: el total. Vivir, dormir y los generales bajan a filas de
 *  composición que suman ese número — el que está scrolleando quiere una
 *  respuesta, no tres cifras para restar.
 *
 *  **El color vive solo abajo del divisor.** El plan (`StopBudget`) mide
 *  únicamente vivir: dormir y los generales son plata comprometida, no algo que
 *  se gaste bien o mal, y pintar el total contra una banda que no lo mide sería
 *  un veredicto inventado. El eyebrow "el plan mide solo vivir" existe para que
 *  la barra de abajo no se lea como el veredicto del total. */
export default function ProjectionCard({ b }: { b: BudgetAnalysis }) {
  const p = b.projection;
  const cost = tripCostRead(b.cost);
  const names = useMemo(() => {
    const bySlug = new Map(b.cities.map((c) => [c.stop_slug, c.city_name]));
    return p.uncovered_slugs.map((s) => bySlug.get(s) ?? s);
  }, [b.cities, p.uncovered_slugs]);
  const cov = coverageLine(p.covered_nights, p.budget_nights, names);
  const plan = bandText(p.living_budget_min_usd, p.living_budget_max_usd);
  const read = projectionRead(p);
  const level = read.kind === "none" ? null : LEVEL[read.kind];
  // Fuera del rango, contra qué borde y por cuánto. `inside` no tiene monto:
  // adentro de la banda no hay desvío que reportar.
  const off = read.kind === "over" || read.kind === "under" ? read : null;

  const rows = [
    {
      icon: UtensilsCrossed,
      label: "Vivir",
      hint:
        b.cost.basis === "projected"
          ? "proyectado al ritmo de lo que ya cerraron"
          : "lo que llevan gastado hasta hoy",
      usd: b.cost.living_usd,
    },
    {
      icon: BedDouble,
      label: "Alojamiento",
      hint: lodgingCoverage(b.fixed, b.cost),
      usd: b.cost.lodging_projected_usd,
    },
    { icon: Plane, label: "Generales", hint: "vuelos, pases, seguros", usd: b.cost.general_usd },
  ];

  return (
    <Card className="p-5">
      <SectionHeader icon={TrendingUp} iconTone="teal" hint="por persona">
        Proyección del viaje
      </SectionHeader>

      <p className="mt-4 text-meta font-semibold uppercase tracking-caps text-ink-3">
        {cost.label}
      </p>
      <p className="font-display text-4xl leading-none tracking-display text-ink font-tabular">
        <AnimatedUsd value={cost.amountUsd} />
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
              {hint && (
                <span className="block text-meta font-medium text-ink-faint">{hint}</span>
              )}
            </span>
            <span className="shrink-0 font-tabular text-sm font-bold text-ink">
              {formatUsd(usd, "whole")}
            </span>
          </div>
        ))}
      </div>

      {/* Acá empieza el único veredicto de la card, y el eyebrow acota contra
          qué: el plan no mide dormir ni los generales. */}
      <div className="mt-4 border-t border-border pt-4">
        <p className="text-fine font-bold uppercase tracking-caps text-ink-3">
          El plan mide solo vivir
        </p>

        {plan && p.projected_living_usd && level ? (
          <>
            <p className={`mt-1.5 text-sm font-semibold ${TEXT[level]}`}>
              {off == null ? (
                "Terminan dentro del plan"
              ) : (
                <>
                  Terminan{" "}
                  <span className="font-tabular">{formatUsd(off.amountUsd, "whole")}</span>{" "}
                  {off.kind === "over" ? "arriba del techo" : "abajo del piso"}
                </>
              )}
            </p>

            <div className="mt-3">
              <ProjectionBar
                min={parseMoney(p.living_budget_min_usd!)}
                max={parseMoney(p.living_budget_max_usd!)}
                value={parseMoney(p.projected_living_usd)}
                level={level}
              />
              <p className="mt-1.5 text-meta font-medium text-ink-3">
                Plan de vivir del viaje <span className="font-tabular">{plan}</span>
              </p>
            </div>
          </>
        ) : (
          <p className="mt-1.5 text-sm font-medium text-ink-2">
            {plan
              ? "Todavía no hay ninguna ciudad cerrada: la proyección aparece cuando terminen la primera parada."
              : "Cargá planes por ciudad para poder proyectar el viaje."}
          </p>
        )}

        {/* La cobertura va SIEMPRE debajo de la varianza: un presupuesto parcial
            comparado contra una proyección de noches completas es mentir. */}
        <p
          className={`mt-3 text-meta font-medium ${
            cov.complete ? "text-ink-3" : "text-accent-amber-ink"
          }`}
        >
          {cov.text}
        </p>
      </div>
    </Card>
  );
}
