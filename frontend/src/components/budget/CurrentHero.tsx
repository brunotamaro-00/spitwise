import BandBadge from "@/components/BandBadge";
import BudgetBandBar from "@/components/BudgetBandBar";
import Flag from "@/components/Flag";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Hero from "@/components/ui/Hero";
import { currentVerdict, stayProgress } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import type { CurrentCityBudget } from "@/types";

import { bandText } from "./bandText";

/** Bloque focal con la ciudad en curso.
 *
 *  El número grande no es "cuánto gastaste" (mirar para atrás) sino **cuánto
 *  queda por día hasta el check-out**: si vinieron ahorrando, sube. Es la
 *  respuesta a "¿salimos a comer hoy?". Debajo, la banda ubica el ritmo real
 *  dentro del plan, que es lo que dice si hace falta ajustar o no. */
export default function CurrentHero({ c }: { c: CurrentCityBudget }) {
  const verdict = currentVerdict(c);
  const plan = bandText(c.target_min_usd, c.target_max_usd);

  return (
    <Hero
      eyebrow={
        <>
          {c.country_flag && <Flag flag={c.country_flag} className="text-sm leading-none" />}
          {c.city_name} · {stayProgress(c.lived_nights, c.total_nights)}
        </>
      }
    >
      {verdict.kind === "no_target" ? (
        <>
          <p className="mt-2 font-display text-5xl leading-none tracking-display font-tabular">
            <AnimatedUsd value={c.living_usd} />
          </p>
          <p className="mt-3 text-sm text-white/85">
            Sin plan para esta parada — cargalo abajo y vas a ver si alcanza.
          </p>
        </>
      ) : (
        <>
          <p className="mt-2 font-display text-6xl leading-none tracking-display font-tabular lg:text-7xl">
            <AnimatedUsd value={verdict.amountUsd} />
          </p>
          <p className="mt-3 text-sm text-white/85">
            {verdict.kind === "margin" ? (
              <>
                por día hasta el check-out ·{" "}
                <span className="font-semibold">
                  {verdict.days} día{verdict.days === 1 ? "" : "s"}
                </span>{" "}
                por delante
              </>
            ) : (
              <>te pasaste del plan de {c.city_name}</>
            )}
          </p>
        </>
      )}

      {plan && c.target_min_usd && c.target_max_usd && (
        <div className="mt-5 border-t border-white/20 pt-4">
          <div className="flex items-baseline justify-between gap-3 text-sm text-white/85">
            <span>
              Llevás{" "}
              <span className="font-tabular font-semibold text-white">
                {formatUsd(c.living_per_day_usd ?? "0", "whole")}
              </span>
              /día
            </span>
            <BandBadge
              position={c.band_position}
              edgeDeltaPct={c.edge_delta_pct}
              min={c.target_min_usd}
              max={c.target_max_usd}
              value={c.living_per_day_usd}
            />
          </div>
          <div className="mt-2.5">
            <BudgetBandBar
              min={c.target_min_usd}
              max={c.target_max_usd}
              value={c.living_per_day_usd}
              size="lg"
              variant="hero"
              label={c.city_name}
            />
          </div>
          <p className="mt-2 text-meta font-medium text-white/70">
            Plan <span className="font-tabular">{plan}</span> por día · la marca es el objetivo
          </p>
        </div>
      )}
    </Hero>
  );
}
