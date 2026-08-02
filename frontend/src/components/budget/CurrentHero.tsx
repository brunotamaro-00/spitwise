import BandBadge from "@/components/BandBadge";
import Flag from "@/components/Flag";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import Hero from "@/components/ui/Hero";
import { stayEnvelope, stayProgress } from "@/lib/budget";
import { formatUsd, parseMoney } from "@/lib/format";
import type { CurrentCityBudget } from "@/types";

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
 *  Debajo, la otra lectura del mismo pote: cuánto va gastado del plan de la
 *  ciudad. Las dos cifras salen de **una sola tasa**, así que cierran entre sí.
 *
 *  **Está podada a propósito.** La banda por día (57–83) y el plan devengado
 *  hasta hoy eran precisos y mudos para quien entra de cero — la demo pública
 *  la abre gente que no sabe qué es un pote de presupuesto. Cada dato que
 *  necesitaba su propia leyenda se fue; el veredicto de ritmo viaja en una
 *  palabra en el `BandBadge`, que es lo que se entiende de una. Lo fino sigue
 *  disponible más abajo, por ciudad. */
export default function CurrentHero({ c }: { c: CurrentCityBudget }) {
  const stay = stayEnvelope(c);

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
                {/* El plazo va en la frase del hero: "USD 241" solo no dice
                    nada, "USD 241 para 3 días" se entiende sin saber qué es un
                    presupuesto. Los días de la PARADA, no del viaje. */}
                para{" "}
                {c.remaining_days === 1 ? (
                  <span className="font-semibold text-white">el último día</span>
                ) : (
                  <>
                    los{" "}
                    <span className="font-semibold text-white">
                      {c.remaining_days} días
                    </span>{" "}
                    que quedan
                  </>
                )}{" "}
                acá ·{" "}
                <span className="font-tabular font-semibold text-white">
                  {formatUsd(stay.dailyUsd, "whole")}
                </span>{" "}
                por día
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
                </span>
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
                over={stay.kind === "over"}
              />
            </div>
            {/* El pie nombra el final de la barra. Es la única leyenda que
                queda: el plan como banda (57–83 por día) y el plan devengado
                hasta hoy eran dos conceptos más para alguien que entra de cero,
                y el veredicto ya viaja en una palabra en el badge. */}
            <p className="mt-2 text-meta font-medium text-white/70">
              de los <span className="font-tabular">{formatUsd(stay.envelopeUsd, "whole")}</span>{" "}
              del plan de {c.city_name}
            </p>
          </div>
        </>
      )}

    </Hero>
  );
}
