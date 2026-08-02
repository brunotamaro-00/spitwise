import { useMemo } from "react";

import { coverageLine, projectionRead, type BandLevel } from "@/lib/budget";
import { formatUsd, parseMoney } from "@/lib/format";
import type { BudgetAnalysis } from "@/types";

import { bandText } from "./bandText";
import ProjectionBar from "./ProjectionBar";
import TripCostCard from "./TripCostCard";

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

/** El costo del viaje (`TripCostCard`) más el único veredicto de la página.
 *
 *  **El color vive solo abajo del divisor.** El plan (`StopBudget`) mide
 *  únicamente vivir: dormir y los generales son plata comprometida, no algo que
 *  se gaste bien o mal, y pintar el total contra una banda que no lo mide sería
 *  un veredicto inventado. El eyebrow "el plan mide solo vivir" existe para que
 *  la barra no se lea como el veredicto del total. */
export default function ProjectionCard({ b }: { b: BudgetAnalysis }) {
  const p = b.projection;
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

  return (
    <TripCostCard cost={b.cost} fixed={b.fixed}>
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
    </TripCostCard>
  );
}
