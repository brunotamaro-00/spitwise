import BandBadge from "@/components/BandBadge";
import Flag from "@/components/Flag";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Hero from "@/components/ui/Hero";
import { stayEnvelope, stayProgress, todayRead } from "@/lib/budget";
import { formatUsd, parseMoney } from "@/lib/format";
import type { CurrentCityBudget } from "@/types";

import { bandText } from "./bandText";
import StayEnvelopeBar from "./StayEnvelopeBar";

/** Bloque focal con la ciudad en curso: **el pote de la parada**.
 *
 *  El número grande es lo que queda del plan de esta ciudad — plata total, no
 *  una tasa. Antes acá vivía el "USD X por día hasta el check-out": se dividía
 *  por los días que faltaban, así que saltaba con cualquier almuerzo, no se
 *  correspondía con el ritmo real que mostraba la barra de abajo, y competía
 *  con el "podés gastar" del colchón. El pote es estable, se lee como una
 *  billetera y sirve igual al llegar a la parada, cerrando el día y de control.
 *
 *  Debajo, dos lecturas de ese mismo pote: la barra (gastado contra lo que el
 *  plan separó hasta hoy, con el fin del pote a la vista) y la fila de HOY. Las
 *  tres cifras salen de **una sola tasa**, así que cierran entre sí. */
export default function CurrentHero({ c }: { c: CurrentCityBudget }) {
  const stay = stayEnvelope(c);
  const today = todayRead(c);
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
      {stay.kind === "no_target" ? (
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
            <AnimatedUsd value={stay.amountUsd} />
          </p>
          <p className="mt-3 text-sm text-white/85">
            {stay.kind === "left" ? (
              <>
                te quedan del plan de {c.city_name} ·{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(stay.dailyUsd, "whole")}
                </span>{" "}
                por día hasta el check-out
              </>
            ) : (
              <>de más que el plan de {c.city_name}</>
            )}
          </p>

          <div className="mt-5 border-t border-white/20 pt-4">
            <div className="flex items-baseline justify-between gap-3 text-sm text-white/85">
              <span>
                Gastaron{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(stay.spentUsd, "whole")}
                </span>{" "}
                de <span className="font-tabular">{formatUsd(stay.envelopeUsd, "whole")}</span>
              </span>
              {/* El veredicto sigue midiendo el RITMO contra la banda, no el
                  pote: son dos preguntas distintas y mezclarlas haría que una
                  parada cara pero corta se pinte como desastre. */}
              <BandBadge
                position={c.band_position}
                edgeDeltaPct={c.edge_delta_pct}
                min={c.target_min_usd}
                max={c.target_max_usd}
                value={c.living_per_day_usd}
              />
            </div>
            <div className="mt-2.5">
              <StayEnvelopeBar
                spent={parseMoney(stay.spentUsd)}
                envelope={parseMoney(stay.envelopeUsd)}
                max={parseMoney(stay.maxUsd)}
                accrued={stay.accruedUsd == null ? null : parseMoney(stay.accruedUsd)}
                over={stay.kind === "over"}
              />
            </div>
            <p className="mt-2 text-meta font-medium text-white/70">
              El poste es lo que el plan separó hasta hoy
              {plan && (
                <>
                  {" "}
                  · plan <span className="font-tabular">{plan}</span> por día
                </>
              )}
            </p>
          </div>
        </>
      )}

      {today.kind !== "none" && (
        <div className="mt-4 flex items-baseline justify-between gap-3 border-t border-white/20 pt-3">
          <span className="text-meta font-semibold uppercase tracking-caps text-white/70">
            Hoy
          </span>
          <span className="text-sm text-white/85">
            {today.kind === "clean" ? (
              <>
                todavía sin gastos ·{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(today.leftUsd ?? "0", "whole")}
                </span>{" "}
                para el día
              </>
            ) : (
              <>
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(today.spentUsd, "whole")}
                </span>{" "}
                gastados
                {today.leftUsd != null && (
                  <>
                    {" · "}
                    {today.kind === "over" ? (
                      <>
                        <span className="font-tabular">
                          {formatUsd(today.leftUsd, "whole")}
                        </span>{" "}
                        arriba del día
                      </>
                    ) : (
                      <>
                        quedan{" "}
                        <span className="font-tabular font-semibold text-white">
                          {formatUsd(today.leftUsd, "whole")}
                        </span>
                      </>
                    )}
                  </>
                )}
              </>
            )}
          </span>
        </div>
      )}
    </Hero>
  );
}
