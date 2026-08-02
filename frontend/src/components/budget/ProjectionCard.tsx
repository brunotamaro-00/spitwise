import { TrendingUp } from "lucide-react";
import { useMemo } from "react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { coverageLine, projectionRead } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import type { BudgetAnalysis } from "@/types";

import { bandText } from "./bandText";

/** Proyección de "vivir" del viaje entero al ritmo de las ciudades cerradas. */
export default function ProjectionCard({ b }: { b: BudgetAnalysis }) {
  const p = b.projection;
  const names = useMemo(() => {
    const bySlug = new Map(b.cities.map((c) => [c.stop_slug, c.city_name]));
    return p.uncovered_slugs.map((s) => bySlug.get(s) ?? s);
  }, [b.cities, p.uncovered_slugs]);
  const cov = coverageLine(p.covered_nights, p.budget_nights, names);
  const total = bandText(p.living_budget_min_usd, p.living_budget_max_usd);
  const read = projectionRead(p);

  return (
    <Card className="p-5">
      <SectionHeader icon={TrendingUp} iconTone="teal">
        Proyección del viaje
      </SectionHeader>

      {total && p.projected_living_usd ? (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <dt className="text-meta font-semibold uppercase tracking-wide text-ink-3">
                Plan
              </dt>
              <dd className="font-display text-xl leading-none text-ink font-tabular">
                {total}
              </dd>
            </div>
            <div>
              <dt className="text-meta font-semibold uppercase tracking-wide text-ink-3">
                Proyectado
              </dt>
              <dd className="font-display text-xl leading-none text-ink font-tabular">
                {formatUsd(p.projected_living_usd, "whole")}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-sm font-semibold text-ink-2">
            Al ritmo de lo que ya cerraron,{" "}
            {read.kind === "inside" ? (
              <span className="text-accent-teal-ink">terminan dentro del plan.</span>
            ) : read.kind === "none" ? null : (
              <>
                terminan{" "}
                <span
                  className={`font-tabular ${
                    read.kind === "over" ? "text-accent-amber-ink" : "text-accent-teal-ink"
                  }`}
                >
                  {formatUsd(read.amountUsd, "whole")}{" "}
                  {read.kind === "over" ? "arriba del techo" : "abajo del piso"}
                </span>
                .
              </>
            )}
          </p>
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
        className={`mt-3 border-t border-border pt-3 text-meta font-medium ${
          cov.complete ? "text-ink-3" : "text-accent-amber-ink"
        }`}
      >
        {cov.text}
      </p>
    </Card>
  );
}
