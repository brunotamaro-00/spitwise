import Flag from "@/components/Flag";
import Hero from "@/components/ui/Hero";
import { coverageLine } from "@/lib/budget";
import { formatShortDate, formatUsd } from "@/lib/format";
import type { TripPlan } from "@/types";

import { bandText } from "./bandText";

/** Antes de arrancar (o terminado el viaje) no hay ciudad en curso: el foco
 *  pasa a ser el plan. Es también el único momento en que revisar las bandas
 *  cargadas sirve de verdad, porque todavía se pueden ajustar. */
export default function PlanHero({ plan, finished }: { plan: TripPlan; finished: boolean }) {
  const cov = coverageLine(plan.covered_nights, plan.budget_nights, []);
  const total = bandText(plan.living_budget_min_usd, plan.living_budget_max_usd);

  return (
    <Hero eyebrow={finished ? "El plan · viaje terminado" : "El plan"}>
      {total ? (
        <>
          <p className="mt-2 font-display text-4xl leading-none tracking-display font-tabular lg:text-5xl">
            {total}
          </p>
          <p className="mt-3 text-sm text-white/85">
            vivir · {plan.budget_nights} noches ·{" "}
            <span className="font-tabular font-semibold text-white">
              {formatUsd(plan.avg_target_daily_usd ?? "0", "whole")}
            </span>
            /día promedio
          </p>
        </>
      ) : (
        <>
          <p className="mt-2 font-display text-4xl leading-none tracking-display">
            Sin plan
          </p>
          <p className="mt-3 text-sm text-white/85">
            Cargá un rango por día en cada ciudad y esta pantalla te dice si van bien.
          </p>
        </>
      )}

      {plan.next_stop && (
        <div className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-white/20 pt-4 text-sm text-white/85">
          <span>Arranca en</span>
          {plan.next_stop.country_flag && (
            <Flag flag={plan.next_stop.country_flag} className="text-sm leading-none" />
          )}
          <span className="font-semibold text-white">{plan.next_stop.city_name}</span>
          {plan.next_stop.arrival_date && (
            <span>· {formatShortDate(plan.next_stop.arrival_date)}</span>
          )}
          {bandText(plan.next_stop.target_min_usd, plan.next_stop.target_max_usd) && (
            <span>
              ·{" "}
              <span className="font-tabular font-semibold text-white">
                {bandText(plan.next_stop.target_min_usd, plan.next_stop.target_max_usd)}
              </span>
              /día
            </span>
          )}
        </div>
      )}

      {!cov.complete && plan.budget_nights > 0 && (
        <p className="mt-3 text-xs text-white/70">{cov.text}</p>
      )}
    </Hero>
  );
}
