import { useQuery } from "@tanstack/react-query";
import { CalendarDays, MapPin, Receipt, TrendingUp } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listCategories } from "@/api/categories";
import {
  getCityBreakdown,
  getCityByCategory,
  getCityDaily,
  getCityMovements,
  getCitySummary,
  getStops,
} from "@/api/cities";
import { getMe } from "@/api/users";
import CategoryDonut from "@/components/CategoryDonut";
import SpendBarChart from "@/components/SpendBarChart";
import MovementRow from "@/components/MovementRow";
import MovementSheet from "@/components/MovementSheet";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import Kpi from "@/components/ui/Kpi";
import Skeleton from "@/components/ui/Skeleton";
import { formatDayHeader, formatShortDate, formatUsd, parseMoney } from "@/lib/format";
import { dayTotalShare, groupByDay } from "@/lib/groupByDay";
import type { Category, Movement } from "@/types";

function fmtRange(a: string | null, b: string | null): string | null {
  if (!a && !b) return null;
  const f = (s: string | null) => (s ? formatDayHeader(s) : "…");
  return `${f(a)} – ${f(b)}`;
}

/** Rango corto dd/mm para las tarjetas del itinerario: "04/08 – 11/08". */
function shortRange(a: string | null, b: string | null): string | null {
  if (!a || !b) return null;
  return `${formatShortDate(a)} – ${formatShortDate(b)}`;
}

export default function Cities() {
  const [params, setParams] = useSearchParams();
  const [viewing, setViewing] = useState<Movement | null>(null);
  const selected = params.getAll("c");
  const selectedSet = new Set(selected);

  const { data: breakdown = [], isLoading: loadingBreak, isError: errBreak, refetch: refetchBreak } = useQuery({
    queryKey: ["city", "breakdown"],
    queryFn: getCityBreakdown,
  });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: getStops, staleTime: 60_000 });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const key = selected.slice().sort();
  const { data: summary, isError: errSummary, refetch: refetchSummary } = useQuery({ queryKey: ["city", "summary", key], queryFn: () => getCitySummary(selected) });
  const { data: byCat = [], isError: errCat, refetch: refetchCat } = useQuery({ queryKey: ["city", "cat", key], queryFn: () => getCityByCategory(selected) });
  const { data: daily = [], isError: errDaily, refetch: refetchDaily } = useQuery({ queryKey: ["city", "daily", key], queryFn: () => getCityDaily(selected) });
  const { data: movements = [], isLoading: loadingMovs, isError: errMovs, refetch: refetchMovs } = useQuery({
    queryKey: ["city", "movs", key],
    queryFn: () => getCityMovements(selected),
  });

  const cityError = errBreak || errSummary || errCat || errDaily || errMovs;
  function retryCity() {
    if (errBreak) refetchBreak();
    if (errSummary) refetchSummary();
    if (errCat) refetchCat();
    if (errDaily) refetchDaily();
    if (errMovs) refetchMovs();
  }

  const catMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c])) as Record<number, Category>,
    [categories],
  );
  const stopMap = useMemo(() => Object.fromEntries(stops.map((s) => [s.slug, s])), [stops]);
  const groups = useMemo(() => groupByDay(movements), [movements]);
  const tripTotal = useMemo(
    () => breakdown.reduce((acc, b) => acc + parseMoney(b.total_usd), 0),
    [breakdown],
  );

  function toggle(slug: string | null) {
    if (!slug) return;
    const next = new Set(selected);
    if (next.has(slug)) next.delete(slug);
    else next.add(slug);
    const p = new URLSearchParams();
    for (const s of next) p.append("c", s);
    setParams(p, { replace: true });
  }

  const single = selected.length === 1 ? stopMap[selected[0]] : undefined;
  const range = single ? fmtRange(single.arrival_date, single.departure_date) : null;
  const heading =
    selected.length === 0
      ? "Todas las ciudades"
      : selected.length === 1
        ? single?.name ?? breakdown.find((b) => b.stop_slug === selected[0])?.city_name ?? selected[0]
        : `${selected.length} ciudades`;
  const flag = single?.country_flag;

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Ciudades</PageTitle>
      </div>

      {cityError && <ErrorState onRetry={retryCity} />}

      {/* Itinerario: una tarjeta por parada, en el orden del viaje. */}
      {loadingBreak ? (
        <Skeleton className="h-24" />
      ) : breakdown.length === 0 ? null : (
        <div className="animate-rise-in stagger-1 -mx-4 flex gap-2.5 overflow-x-auto px-4 pb-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:-mx-8 lg:px-8">
          <motion.button
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
            aria-pressed={selected.length === 0}
            whileTap={{ scale: 0.96 }}
            className={`flex min-w-[7.5rem] shrink-0 cursor-pointer flex-col items-start gap-1 rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
              selected.length === 0
                ? "border-brick bg-brick text-white soft-pop"
                : "border-border bg-surface text-ink-2 soft-card hover:bg-surface-2"
            }`}
          >
            <span className="text-sm font-bold">Todo el viaje</span>
            <span className={`font-display text-lg leading-none font-tabular ${selected.length === 0 ? "text-white" : "text-ink"}`}>
              {formatUsd(tripTotal.toFixed(2))}
            </span>
            <span className={`text-[11px] font-medium ${selected.length === 0 ? "text-white/75" : "text-ink-faint"}`}>
              {breakdown.length} paradas
            </span>
          </motion.button>
          {breakdown.map((b) => {
            const slug = b.stop_slug;
            const active = slug != null && selectedSet.has(slug);
            const stop = slug ? stopMap[slug] : undefined;
            const range = stop ? shortRange(stop.arrival_date, stop.departure_date) : null;
            return (
              <motion.button
                key={slug ?? b.city_name ?? "general"}
                onClick={() => toggle(slug)}
                aria-pressed={active}
                disabled={!slug}
                whileTap={slug ? { scale: 0.96 } : undefined}
                className={`flex min-w-[7.5rem] shrink-0 flex-col items-start gap-1 rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
                  active
                    ? "cursor-pointer border-brick bg-brick text-white soft-pop"
                    : slug
                      ? "cursor-pointer border-border bg-surface text-ink-2 soft-card hover:bg-surface-2"
                      : "border-border bg-surface-2/60 text-ink-3"
                }`}
              >
                <span className="flex max-w-full items-center gap-1.5 text-sm font-bold">
                  {b.country_flag && <span aria-hidden="true">{b.country_flag}</span>}
                  <span className="truncate">{b.city_name ?? "Generales"}</span>
                </span>
                <span className={`font-display text-lg leading-none font-tabular ${active ? "text-white" : "text-ink"}`}>
                  {formatUsd(b.total_usd)}
                </span>
                <span className={`text-[11px] font-medium ${active ? "text-white/75" : "text-ink-faint"}`}>
                  {range ?? (slug ? `${b.movement_count} mov.` : "sin ciudad")}
                </span>
              </motion.button>
            );
          })}
        </div>
      )}

      {/* Header / hero de la selección */}
      <Card className="animate-rise-in stagger-1 relative overflow-hidden p-5 text-white hero-gradient soft-hero">
        <div className="spit-dots absolute inset-0" aria-hidden="true" />
        <div className="relative">
          <div className="flex items-center gap-3">
            {flag ? (
              <span className="text-3xl leading-none" aria-hidden="true">{flag}</span>
            ) : (
              <MapPin size={26} strokeWidth={2} aria-hidden="true" />
            )}
            <div>
              <h2 className="font-display text-2xl leading-none">{heading}</h2>
              {(range || single?.country) && (
                <p className="mt-1 text-sm text-white/80">
                  {single?.country}
                  {single?.country && range ? " · " : ""}
                  {range}
                </p>
              )}
            </div>
          </div>
          <div className="mt-5 flex items-end justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-white/70">Mi gasto</p>
              <p className="font-display text-4xl leading-none font-tabular">
                <AnimatedUsd value={summary?.total_usd ?? "0"} />
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* KPIs */}
      <div className="animate-rise-in stagger-2 grid grid-cols-3 gap-3">
        <Kpi icon={Receipt} tint="blue" label="Movimientos" value={String(summary?.movement_count ?? 0)} />
        <Kpi icon={CalendarDays} tint="teal" label="Días" value={String(summary?.days ?? 0)} />
        <Kpi icon={TrendingUp} tint="amber" label="Prom./día" value={formatUsd(summary?.avg_per_day_usd ?? "0")} />
      </div>

      {/* Gráficos: items-stretch para que ninguna card deje hueco al lado
          de la más alta en desktop. */}
      <div className="animate-rise-in stagger-3 grid items-stretch gap-5 lg:grid-cols-2">
        {byCat.length > 0 && <CategoryDonut data={byCat} />}
        {daily.length > 0 && <SpendBarChart data={daily} granularity="day" />}
      </div>

      {/* Detalle de movimientos */}
      <div>
        <h2 className="mb-2 px-1 text-sm font-bold text-ink">Detalle de movimientos</h2>
        {loadingMovs ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}
          </div>
        ) : movements.length === 0 ? (
          <Card>
            <EmptyState icon={Receipt} title="Sin movimientos" description="No hay gastos para esta selección." />
          </Card>
        ) : (
          <div className="flex flex-col gap-4">
            {groups.map((g) => (
              <section key={g.date}>
                <h3 className="mb-1.5 flex items-baseline justify-between gap-2 px-1">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                    {formatDayHeader(g.date)}
                  </span>
                  <span className="font-tabular text-[11px] font-semibold text-ink-faint">
                    {formatUsd(String(me ? dayTotalShare(g.items, me.id) : 0))}
                  </span>
                </h3>
                <Card className="px-5">
                  {g.items.map((m) => (
                    <MovementRow
                      key={m.id}
                      mv={m}
                      myId={me?.id}
                      category={m.category_id != null ? catMap[m.category_id] : undefined}
                      flag={m.stop_slug ? stopMap[m.stop_slug]?.country_flag : undefined}
                      readOnly
                      preferShare
                      onOpen={setViewing}
                    />
                  ))}
                </Card>
              </section>
            ))}
          </div>
        )}
      </div>

      {viewing && (
        <MovementSheet
          mv={viewing}
          myId={me?.id}
          category={viewing.category_id != null ? catMap[viewing.category_id] : undefined}
          flag={viewing.stop_slug ? stopMap[viewing.stop_slug]?.country_flag : undefined}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  );
}

