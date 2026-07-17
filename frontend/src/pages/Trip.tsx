import { useQuery } from "@tanstack/react-query";
import { Plane } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPace } from "@/api/dashboard";
import DeltaBadge from "@/components/DeltaBadge";
import Flag from "@/components/Flag";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import Skeleton from "@/components/ui/Skeleton";
import { formatShortDate, formatUsd, isZeroMoney } from "@/lib/format";
import type { CityPace } from "@/types";

function Chapter({ city, onOpen }: { city: CityPace; onOpen: () => void }) {
  const future = city.status === "future";
  const current = city.status === "current";
  const hasSpend = city.movement_count > 0 && !isZeroMoney(city.total_usd);

  return (
    <div className="relative pl-6">
      {/* Riel del timeline */}
      <span
        aria-hidden="true"
        className={`absolute left-[5px] top-5 h-3 w-3 rounded-full border-2 ${
          current
            ? "border-brick bg-brick"
            : future
              ? "border-border-strong bg-surface"
              : "border-brick/50 bg-brick/50"
        }`}
      />
      <Card
        className={`p-3.5 transition-colors ${future ? "opacity-70" : ""} ${
          current ? "border-brick/40" : ""
        } ${hasSpend || !future ? "cursor-pointer hover:border-border-strong" : ""}`}
        onClick={hasSpend || !future ? onOpen : undefined}
      >
        <div className="flex items-baseline justify-between gap-3">
          <div className="flex min-w-0 items-baseline gap-2">
            <Flag flag={city.country_flag} className="translate-y-[1px]" />
            <span className="truncate font-display text-lg tracking-wide text-ink">
              {city.city_name}
            </span>
            {current && (
              <span className="rounded-full bg-brick-bg px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-brick">
                hoy
              </span>
            )}
          </div>
          {!future && hasSpend && (
            <span className="shrink-0 font-tabular text-sm font-bold text-ink">
              {formatUsd(city.total_usd)}
            </span>
          )}
          {future && hasSpend && (
            <span className="shrink-0 text-[11px] font-medium text-ink-3">
              reservado <span className="font-tabular font-semibold">{formatUsd(city.total_usd)}</span>
            </span>
          )}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] font-medium text-ink-3">
          {city.arrival_date && city.departure_date && (
            <span>
              {formatShortDate(city.arrival_date)} – {formatShortDate(city.departure_date)}
            </span>
          )}
          {city.nights > 0 && <span>· {city.nights} noche{city.nights === 1 ? "" : "s"}</span>}
          {!future && city.per_day_usd && (
            <span className="font-tabular">· {formatUsd(city.per_day_usd)}/día</span>
          )}
          {!future && <DeltaBadge pct={city.delta_vs_trip_pct} compact />}
        </div>
        {future && !hasSpend && (
          <p className="mt-1 text-[12px] italic text-ink-faint">por escribir…</p>
        )}
      </Card>
    </div>
  );
}

/** El viaje como historia: capítulos por ciudad en orden de itinerario, con su
 *  gasto total y ritmo, y "hoy" marcado. A propósito NO hay cuenta regresiva ni
 *  "día X de Y": los capítulos futuros existen, pero nadie los cuenta. */
export default function Trip() {
  const pace = useQuery({ queryKey: ["dashboard", "pace"], queryFn: getPace });
  const navigate = useNavigate();

  if (pace.isError) {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>Viaje</PageTitle>
        <ErrorState onRetry={() => void pace.refetch()} />
      </div>
    );
  }
  if (!pace.data) {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>Viaje</PageTitle>
        <Skeleton className="h-24" />
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    );
  }

  const { trip, cities } = pace.data;
  const chapters = cities.filter((c) => !c.is_archived).sort((a, b) => a.order - b.order);

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Viaje</PageTitle>
      </div>

      {!isZeroMoney(trip.general_usd) && (
        <div className="animate-rise-in stagger-1">
          <Card className="flex items-center justify-between gap-3 p-4">
            <span className="flex items-center gap-2.5 text-sm font-semibold text-ink-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-2 text-ink-3">
                <Plane size={17} strokeWidth={2} aria-hidden="true" />
              </span>
              Generales del viaje
              <span className="hidden text-[11px] font-medium text-ink-faint sm:inline">
                vuelos, pases, seguros
              </span>
            </span>
            <span className="font-tabular text-sm font-bold text-ink">
              {formatUsd(trip.general_usd)}
            </span>
          </Card>
        </div>
      )}

      {/* Línea vertical detrás de los capítulos */}
      <div className="animate-rise-in stagger-2 relative flex flex-col gap-3">
        <span
          aria-hidden="true"
          className="absolute bottom-5 left-[10px] top-5 w-px bg-border"
        />
        {chapters.map((c) => (
          <Chapter
            key={c.stop_slug}
            city={c}
            onOpen={() => navigate(`/ciudades?c=${c.stop_slug}`)}
          />
        ))}
      </div>
    </div>
  );
}
