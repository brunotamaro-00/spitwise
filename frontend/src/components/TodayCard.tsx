import { ChevronRight, ExternalLink, MapPin } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "@/components/ui/Card";
import { formatUsd, todayLocal } from "@/lib/format";
import { stopForDate } from "@/lib/stops";
import { useAndiamoUrl } from "@/lib/useConfig";
import type { CityDaily, Stop } from "@/types";

/** Lo que más se mira en viaje: cuánto llevo gastado HOY y en qué ciudad estoy.
 *  Toda la card linkea a /movimientos filtrado por hoy. El deep link a Andiamo
 *  va como hermano (nunca <a> anidado dentro del <Link>). */
export default function TodayCard({ daily, stops }: { daily: CityDaily[]; stops: Stop[] }) {
  const today = todayLocal();
  const stop = stopForDate(stops, today);
  const total = daily.find((d) => d.date === today)?.total_usd ?? "0";
  const andiamoUrl = useAndiamoUrl();

  return (
    <div>
      <Link
        to={`/movimientos?from=${today}&to=${today}`}
        aria-label="Ver los movimientos de hoy"
        className="block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
      >
        <Card className="flex items-center gap-3.5 p-5 transition-colors hover:bg-surface-2/50">
          {stop?.country_flag ? (
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-2 text-2xl leading-none" aria-hidden="true">
              {stop.country_flag}
            </span>
          ) : (
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink-3" aria-hidden="true">
              <MapPin size={20} strokeWidth={2} />
            </span>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">
              Hoy{stop ? ` · ${stop.name}` : ""}
            </p>
            <p className="mt-0.5 font-display text-[1.7rem] leading-none text-ink font-tabular">
              {formatUsd(total)}
            </p>
          </div>
          <ChevronRight size={18} strokeWidth={2} className="shrink-0 text-ink-faint" aria-hidden="true" />
        </Card>
      </Link>
      {stop && andiamoUrl && (
        <a
          href={`${andiamoUrl}/stops/${stop.slug}`}
          target="_blank"
          rel="noopener"
          className="mt-1.5 flex min-h-[32px] items-center justify-end gap-1 px-1.5 text-[11px] font-semibold text-ink-3 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 rounded"
        >
          Itinerario de {stop.name} en Andiamo
          <ExternalLink size={11} strokeWidth={2} aria-hidden="true" />
        </a>
      )}
    </div>
  );
}
