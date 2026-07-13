import { useQuery } from "@tanstack/react-query";
import { CalendarDays, MapPin, Receipt, TrendingUp } from "lucide-react";
import { useMemo } from "react";
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
import DailySpendChart from "@/components/DailySpendChart";
import MovementRow from "@/components/MovementRow";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import { formatDayHeader, formatUsd } from "@/lib/format";
import { groupByDay } from "@/lib/groupByDay";
import type { Category } from "@/types";

function fmtRange(a: string | null, b: string | null): string | null {
  if (!a && !b) return null;
  const f = (s: string | null) => (s ? formatDayHeader(s) : "…");
  return `${f(a)} – ${f(b)}`;
}

export default function Cities() {
  const [params, setParams] = useSearchParams();
  const selected = params.getAll("c");
  const selectedSet = new Set(selected);

  const { data: breakdown = [], isLoading: loadingBreak } = useQuery({
    queryKey: ["city", "breakdown"],
    queryFn: getCityBreakdown,
  });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: getStops, staleTime: 60_000 });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const key = selected.slice().sort();
  const { data: summary } = useQuery({ queryKey: ["city", "summary", key], queryFn: () => getCitySummary(selected) });
  const { data: byCat = [] } = useQuery({ queryKey: ["city", "cat", key], queryFn: () => getCityByCategory(selected) });
  const { data: daily = [] } = useQuery({ queryKey: ["city", "daily", key], queryFn: () => getCityDaily(selected) });
  const { data: movements = [], isLoading: loadingMovs } = useQuery({
    queryKey: ["city", "movs", key],
    queryFn: () => getCityMovements(selected),
  });

  const catMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c])) as Record<number, Category>,
    [categories],
  );
  const stopMap = useMemo(() => Object.fromEntries(stops.map((s) => [s.slug, s])), [stops]);
  const groups = useMemo(() => groupByDay(movements), [movements]);

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
    <div className="animate-fade-in flex flex-col gap-5">
      <h1 className="text-2xl font-bold text-ink">Ciudades</h1>

      {/* Selector de ciudades */}
      {loadingBreak ? (
        <Skeleton className="h-12" />
      ) : breakdown.length === 0 ? null : (
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <button
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
            aria-pressed={selected.length === 0}
            className={`shrink-0 cursor-pointer rounded-full border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
              selected.length === 0
                ? "border-brick bg-brick text-white"
                : "border-border bg-surface text-ink-2 hover:bg-surface-2"
            }`}
          >
            Todas
          </button>
          {breakdown.map((b) => {
            const slug = b.stop_slug;
            const active = slug != null && selectedSet.has(slug);
            return (
              <button
                key={slug ?? b.city_name}
                onClick={() => toggle(slug)}
                aria-pressed={active}
                className={`flex shrink-0 cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
                  active ? "border-brick bg-brick-bg text-brick" : "border-border bg-surface text-ink-2 hover:bg-surface-2"
                }`}
              >
                {b.country_flag && <span aria-hidden="true">{b.country_flag}</span>}
                <span>{b.city_name ?? "Sin ciudad"}</span>
                <span className="font-tabular text-xs text-ink-faint">{formatUsd(b.total_usd)}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Header / hero de la selección */}
      <Card className="relative overflow-hidden p-5 text-white hero-gradient soft-hero">
        <div className="hero-texture absolute inset-0" aria-hidden="true" />
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
                {formatUsd(summary?.total_usd ?? "0")}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <Kpi icon={Receipt} tint="blue" label="Movimientos" value={String(summary?.movement_count ?? 0)} />
        <Kpi icon={CalendarDays} tint="teal" label="Días" value={String(summary?.days ?? 0)} />
        <Kpi icon={TrendingUp} tint="amber" label="Prom./día" value={formatUsd(summary?.avg_per_day_usd ?? "0")} />
      </div>

      {/* Gráficos */}
      <div className="grid items-start gap-5 lg:grid-cols-2">
        {byCat.length > 0 && <CategoryDonut data={byCat} />}
        {daily.length > 0 && <DailySpendChart data={daily} />}
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
                <h3 className="mb-1 px-1 text-xs font-medium capitalize text-ink-3">{formatDayHeader(g.date)}</h3>
                <Card className="px-4">
                  {g.items.map((m) => (
                    <MovementRow
                      key={m.id}
                      mv={m}
                      myId={me?.id}
                      category={m.category_id != null ? catMap[m.category_id] : undefined}
                      flag={m.stop_slug ? stopMap[m.stop_slug]?.country_flag : undefined}
                      readOnly
                    />
                  ))}
                </Card>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({
  icon: Icon,
  tint,
  label,
  value,
}: {
  icon: typeof Receipt;
  tint: "blue" | "teal" | "amber";
  label: string;
  value: string;
}) {
  const tints = {
    blue: "bg-accent-blue-bg text-accent-blue",
    teal: "bg-accent-teal-bg text-accent-teal",
    amber: "bg-accent-amber-bg text-accent-amber",
  } as const;
  return (
    <Card className="flex flex-col gap-2 p-4">
      <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${tints[tint]}`}>
        <Icon size={16} strokeWidth={2} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="truncate font-display text-lg leading-none tracking-tight text-ink font-tabular">
          {value}
        </p>
        <p className="mt-1 text-xs font-medium text-ink-3">{label}</p>
      </div>
    </Card>
  );
}
