import { useQuery } from "@tanstack/react-query";
import { Archive, BedDouble, ExternalLink, MapPin, Receipt, TrendingUp, UtensilsCrossed } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listCategories } from "@/api/categories";
import { getCityByCategory, getCityMovements, getCitySummary, getStops } from "@/api/cities";
import { getPace } from "@/api/dashboard";
import CategoryDonut from "@/components/CategoryDonut";
import DeltaBadge from "@/components/DeltaBadge";
import Flag from "@/components/Flag";
import MovementRow from "@/components/MovementRow";
import MovementSheet from "@/components/MovementSheet";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { Label } from "@/components/ui/Field";
import Kpi from "@/components/ui/Kpi";
import Skeleton from "@/components/ui/Skeleton";
import { formatDayHeader, formatShortDate, formatUsd, parseMoney } from "@/lib/format";
import { useAndiamoUrl } from "@/lib/useConfig";
import { dayTotalShare, groupByDay } from "@/lib/groupByDay";
import { useMe } from "@/lib/useMe";
import type { Category, CityPace, Movement } from "@/types";

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

/** Sub-línea de la chip según el estado de la parada. */
function chipStatusLine(c: CityPace): string {
  if (c.is_archived) return "archivada";
  if (c.status === "future") return `próxima · ${c.nights} noche${c.nights === 1 ? "" : "s"}`;
  if (c.status === "current") return `en curso · día ${c.elapsed_nights}/${c.nights}`;
  return shortRange(c.arrival_date, c.departure_date) ?? `${c.movement_count} mov.`;
}

/** Barra apilada dormir vs vivir: proporción del $/día de la ciudad que se va
 *  en alojamiento (prorrateado por noche) vs el resto. Sin Recharts: dos
 *  segmentos son más legibles como divs, con monto y label siempre visibles. */
function SleepVsLiveCard({ city }: { city: CityPace }) {
  const sleep = city.lodging_per_night_usd ? parseMoney(city.lodging_per_night_usd) : 0;
  const live = city.other_per_day_usd ? parseMoney(city.other_per_day_usd) : 0;
  const total = sleep + live;
  if (total <= 0) return null;
  const sleepPct = Math.round((sleep / total) * 100);
  const rows = [
    { key: "sleep", icon: BedDouble, label: "Dormir", sub: "/noche", value: city.lodging_per_night_usd ?? "0", pct: sleepPct },
    { key: "live", icon: UtensilsCrossed, label: "Vivir", sub: "/día", value: city.other_per_day_usd ?? "0", pct: 100 - sleepPct },
  ];
  return (
    <Card className="flex h-full flex-col gap-4 p-5">
      <Label>Dormir vs vivir</Label>
      <div className="flex h-3 overflow-hidden rounded-full">
        <div className="h-full bg-brick" style={{ width: `${Math.max(sleepPct, 2)}%` }} />
        <div className="h-full bg-accent-teal" style={{ width: `${Math.max(100 - sleepPct, 2)}%` }} />
      </div>
      <ul className="flex flex-col gap-3">
        {rows.map((r) => (
          <li key={r.key} className="flex items-center gap-3 text-sm">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                r.key === "sleep" ? "bg-brick-bg text-brick" : "bg-accent-teal-bg text-accent-teal"
              }`}
            >
              <r.icon size={15} strokeWidth={2} aria-hidden="true" />
            </span>
            <span className="flex-1 font-semibold text-ink">{r.label}</span>
            <span className="font-tabular text-ink-2">
              {formatUsd(r.value)}
              <span className="text-xs text-ink-3">{r.sub}</span>
            </span>
            <span className="w-9 shrink-0 text-right font-tabular text-xs text-ink-3">{r.pct}%</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-3">
        {city.nights} noche{city.nights === 1 ? "" : "s"} · alojamiento prorrateado por noche
      </p>
    </Card>
  );
}

export default function Cities() {
  const [params, setParams] = useSearchParams();
  const [viewing, setViewing] = useState<Movement | null>(null);
  const selected = params.getAll("c");
  const selectedSet = new Set(selected);

  const { data: pace, isLoading: loadingPace, isError: errPace, refetch: refetchPace } = useQuery({
    queryKey: ["dashboard", "pace"],
    queryFn: getPace,
  });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: getStops, staleTime: 60_000 });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: me } = useMe();
  const andiamoUrl = useAndiamoUrl();

  const key = selected.slice().sort();
  const { data: summary, isError: errSummary, refetch: refetchSummary } = useQuery({ queryKey: ["city", "summary", key], queryFn: () => getCitySummary(selected) });
  const { data: byCat = [], isError: errCat, refetch: refetchCat } = useQuery({ queryKey: ["city", "cat", key], queryFn: () => getCityByCategory(selected) });
  const { data: movements = [], isLoading: loadingMovs, isError: errMovs, refetch: refetchMovs } = useQuery({
    queryKey: ["city", "movs", key],
    queryFn: () => getCityMovements(selected),
  });

  const cityError = errPace || errSummary || errCat || errMovs;
  function retryCity() {
    if (errPace) refetchPace();
    if (errSummary) refetchSummary();
    if (errCat) refetchCat();
    if (errMovs) refetchMovs();
  }

  const catMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c])) as Record<number, Category>,
    [categories],
  );
  const stopMap = useMemo(() => Object.fromEntries(stops.map((s) => [s.slug, s])), [stops]);
  const groups = useMemo(() => groupByDay(movements), [movements]);
  const cities = pace?.cities ?? [];
  const paceMap = useMemo(
    () => Object.fromEntries(cities.map((c) => [c.stop_slug, c])) as Record<string, CityPace>,
    [cities],
  );

  function toggle(slug: string) {
    const next = new Set(selected);
    if (next.has(slug)) next.delete(slug);
    else next.add(slug);
    const p = new URLSearchParams();
    for (const s of next) p.append("c", s);
    setParams(p, { replace: true });
  }

  const single = selected.length === 1 ? stopMap[selected[0]] : undefined;
  const singlePace = selected.length === 1 ? paceMap[selected[0]] : undefined;
  const range = single ? fmtRange(single.arrival_date, single.departure_date) : null;
  const heading =
    selected.length === 0
      ? "Todas las ciudades"
      : selected.length === 1
        ? single?.name ?? singlePace?.city_name ?? selected[0]
        : `${selected.length} ciudades`;
  const flag = single?.country_flag ?? singlePace?.country_flag;

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Ciudades</PageTitle>
      </div>

      {cityError && <ErrorState onRetry={retryCity} />}

      {/* Itinerario: una tarjeta por parada, en el orden del viaje, con su
          $/día (alojamiento prorrateado) — comparable entre estadías. */}
      {loadingPace ? (
        <Skeleton className="h-24" />
      ) : cities.length === 0 ? null : (
        <div className="animate-rise-in stagger-1 -mx-4 flex gap-2.5 overflow-x-auto px-4 pb-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:-mx-8 lg:px-8">
          <motion.button
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
            aria-pressed={selected.length === 0}
            whileTap={{ scale: 0.96 }}
            className={`flex w-[9.5rem] shrink-0 cursor-pointer flex-col items-start gap-1 rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
              selected.length === 0
                ? "border-brick bg-brick text-white soft-pop"
                : "border-border bg-surface text-ink-2 soft-card hover:bg-surface-2"
            }`}
          >
            <span className="text-sm font-bold">Todo el viaje</span>
            <span className={`font-display text-lg leading-none font-tabular ${selected.length === 0 ? "text-white" : "text-ink"}`}>
              {pace?.trip.avg_per_day_usd ? `${formatUsd(pace.trip.avg_per_day_usd)}/día` : "—"}
            </span>
            <span className={`text-[11px] font-medium ${selected.length === 0 ? "text-white/75" : "text-ink-faint"}`}>
              {pace?.trip.status === "not_started" ? "previsto · " : ""}
              {cities.length} paradas
            </span>
          </motion.button>
          {cities.map((c) => {
            const active = selectedSet.has(c.stop_slug);
            return (
              <motion.button
                key={c.stop_slug}
                onClick={() => toggle(c.stop_slug)}
                aria-pressed={active}
                whileTap={{ scale: 0.96 }}
                className={`flex w-[9.5rem] shrink-0 cursor-pointer flex-col items-start gap-1 rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
                  active
                    ? "border-brick bg-brick text-white soft-pop"
                    : c.status === "future"
                      ? "border-border bg-surface-2/60 text-ink-3 soft-card hover:bg-surface-2"
                      : "border-border bg-surface text-ink-2 soft-card hover:bg-surface-2"
                }`}
              >
                <span className="flex max-w-full items-center gap-1.5 text-sm font-bold">
                  {c.country_flag && <Flag flag={c.country_flag} className="shrink-0 text-sm leading-none" />}
                  {/* min-w-0: sin esto el flex item no baja de su ancho de
                      contenido y `truncate` nunca llega a cortar. */}
                  <span className="min-w-0 truncate">{c.city_name}</span>
                  {c.is_archived && (
                    <Archive
                      size={12}
                      strokeWidth={2}
                      aria-label="Ciudad archivada"
                      className={`shrink-0 ${active ? "text-white/70" : "text-ink-faint"}`}
                    />
                  )}
                </span>
                <span className={`font-display text-lg leading-none font-tabular ${active ? "text-white" : "text-ink"}`}>
                  {c.per_day_usd && parseMoney(c.per_day_usd) > 0 ? `${formatUsd(c.per_day_usd)}/día` : "—"}
                </span>
                <span className={`text-[11px] font-medium ${active ? "text-white/75" : "text-ink-faint"}`}>
                  {chipStatusLine(c)}
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
              <Flag flag={flag} className="text-3xl leading-none" />
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
            {single && andiamoUrl && (
              <a
                href={`${andiamoUrl}/stops/${single.slug}`}
                target="_blank"
                rel="noopener"
                className="ml-auto flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-full border border-white/40 px-3 text-[11px] font-semibold uppercase tracking-wide text-white/90 transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
              >
                Andiamo
                <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
              </a>
            )}
          </div>
          <div className="mt-5 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-white/70">Mi gasto</p>
              <p className="font-display text-4xl leading-none font-tabular">
                <AnimatedUsd value={summary?.total_usd ?? "0"} />
              </p>
              <p className="mt-1.5 text-sm text-white/80">
                {summary?.movement_count ?? 0} movimiento{(summary?.movement_count ?? 0) === 1 ? "" : "s"} ·{" "}
                {summary?.days ?? 0} noche{(summary?.days ?? 0) === 1 ? "" : "s"}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* KPIs: con una ciudad seleccionada, el modelo prorrateado (ritmo,
          dormir/noche, vivir/día); si no, los agregados de la selección. */}
      {singlePace && singlePace.nights > 0 ? (
        <div className="animate-rise-in stagger-2 grid grid-cols-3 gap-3">
          <Kpi
            icon={TrendingUp}
            tint="brick"
            label={singlePace.status === "current" ? "$/día · hoy" : "$/día"}
            value={formatUsd(singlePace.per_day_usd ?? "0")}
            badge={<DeltaBadge pct={singlePace.delta_vs_trip_pct} compact />}
          />
          <Kpi icon={BedDouble} tint="blue" label="Dormir /noche" value={formatUsd(singlePace.lodging_per_night_usd ?? "0")} />
          <Kpi icon={UtensilsCrossed} tint="teal" label="Vivir /día" value={formatUsd(singlePace.other_per_day_usd ?? "0")} />
        </div>
      ) : (
        <div className="animate-rise-in stagger-2 grid grid-cols-3 gap-3">
          <Kpi icon={Receipt} tint="blue" label="Movimientos" value={String(summary?.movement_count ?? 0)} />
          <Kpi icon={BedDouble} tint="teal" label="Noches" value={String(summary?.days ?? 0)} />
          <Kpi icon={TrendingUp} tint="amber" label="Prom./día" value={formatUsd(summary?.avg_per_day_usd ?? "0")} />
        </div>
      )}

      {/* Gráficos: items-stretch para que ninguna card deje hueco al lado
          de la más alta en desktop. */}
      <div className="animate-rise-in stagger-3 grid items-stretch gap-5 lg:grid-cols-2">
        {byCat.length > 0 && <CategoryDonut data={byCat} />}
        {singlePace && singlePace.nights > 0 && <SleepVsLiveCard city={singlePace} />}
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
