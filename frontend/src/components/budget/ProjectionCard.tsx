import { TrendingUp } from "lucide-react";
import { useMemo } from "react";

import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { coverageLine, projectionRead, type BandLevel } from "@/lib/budget";
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

/** Proyección de "vivir" del viaje entero al ritmo de las ciudades cerradas.
 *
 *  Un solo número manda —dónde termina el viaje— y el plan es su contexto, no
 *  su par: dos columnas de tamaño igual obligaban a restar mentalmente para
 *  saber si eso está bien o mal. La barra hace esa resta. */
export default function ProjectionCard({ b }: { b: BudgetAnalysis }) {
  const p = b.projection;
  const names = useMemo(() => {
    const bySlug = new Map(b.cities.map((c) => [c.stop_slug, c.city_name]));
    return p.uncovered_slugs.map((s) => bySlug.get(s) ?? s);
  }, [b.cities, p.uncovered_slugs]);
  const cov = coverageLine(p.covered_nights, p.budget_nights, names);
  const total = bandText(p.living_budget_min_usd, p.living_budget_max_usd);
  const read = projectionRead(p);
  const level = read.kind === "none" ? null : LEVEL[read.kind];
  // Fuera del rango, contra qué borde y por cuánto. `inside` no tiene monto:
  // adentro de la banda no hay desvío que reportar.
  const off = read.kind === "over" || read.kind === "under" ? read : null;

  return (
    <Card className="p-5">
      <SectionHeader icon={TrendingUp} iconTone="teal">
        Proyección del viaje
      </SectionHeader>

      {total && p.projected_living_usd && level ? (
        <>
          <p className="mt-4 font-display text-4xl leading-none tracking-display text-ink font-tabular">
            <AnimatedUsd value={p.projected_living_usd} />
          </p>
          <p className="mt-2 text-sm font-semibold text-ink-2">
            al ritmo de lo que ya cerraron ·{" "}
            <span className={TEXT[level]}>
              {off == null ? (
                "terminan dentro del plan"
              ) : (
                <>
                  terminan{" "}
                  <span className="font-tabular">
                    {formatUsd(off.amountUsd, "whole")}
                  </span>{" "}
                  {off.kind === "over" ? "arriba del techo" : "abajo del piso"}
                </>
              )}
            </span>
          </p>

          <div className="mt-4">
            <ProjectionBar
              min={parseMoney(p.living_budget_min_usd!)}
              max={parseMoney(p.living_budget_max_usd!)}
              value={parseMoney(p.projected_living_usd)}
              level={level}
            />
            <p className="mt-1.5 text-meta font-medium text-ink-3">
              Plan de vivir del viaje <span className="font-tabular">{total}</span>
            </p>
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm font-medium text-ink-2">
          {total
            ? "Todavía no hay ninguna ciudad cerrada: la proyección aparece cuando terminen la primera parada."
            : "Cargá planes por ciudad para poder proyectar el viaje."}
        </p>
      )}

      {/* La cobertura va SIEMPRE debajo de la varianza: un presupuesto parcial
          comparado contra una proyección de noches completas es mentir. */}
      <p
        className={`mt-4 border-t border-border pt-3 text-meta font-medium ${
          cov.complete ? "text-ink-3" : "text-accent-amber-ink"
        }`}
      >
        {cov.text}
      </p>
    </Card>
  );
}
