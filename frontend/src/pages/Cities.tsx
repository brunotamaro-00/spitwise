import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BedDouble, ExternalLink, MapPin, Receipt, TrendingUp, UtensilsCrossed } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { errorDetail } from "@/api/client";
import { listCategories } from "@/api/categories";
import { getCityByCategory, getCityMovements, getCitySummary, getStops } from "@/api/cities";
import { getPace } from "@/api/dashboard";
import { deleteMovement } from "@/api/movements";
import AddMovementDialog from "@/components/AddMovementDialog";
import CategoryDonut from "@/components/CategoryDonut";
import DeltaBadge from "@/components/DeltaBadge";
import Flag from "@/components/Flag";
import MovementRow from "@/components/MovementRow";
import MovementSheet from "@/components/MovementSheet";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import Kpi from "@/components/ui/Kpi";
import Skeleton from "@/components/ui/Skeleton";
import SkeletonReveal from "@/components/ui/SkeletonReveal";
import { useToast } from "@/components/ui/Toast";
import { formatAmount, formatDayHeader, formatShortDate, formatUsd, parseMoney } from "@/lib/format";
import { useAndiamoUrl } from "@/lib/useConfig";
import { dayTotalShare, groupByDay } from "@/lib/groupByDay";
import { invalidateLedger } from "@/lib/queryClient";
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
  // "reservado" aclara que el monto de arriba es lo ya cargado, no un ritmo.
  if (c.status === "future") {
    const noches = `${c.nights} noche${c.nights === 1 ? "" : "s"}`;
    return parseMoney(c.total_usd) > 0 ? `reservado · ${noches}` : `próxima · ${noches}`;
  }
  if (c.status === "current") return `en curso · día ${c.elapsed_nights}/${c.nights}`;
  return shortRange(c.arrival_date, c.departure_date) ?? `${c.movement_count} mov.`;
}

export default function Cities() {
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [viewing, setViewing] = useState<Movement | null>(null);
  const [editing, setEditing] = useState<Movement | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Movement | null>(null);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const selected = params.getAll("c");
  const selectedSet = new Set(selected);

  const del = useMutation({
    mutationFn: (m: Movement) => deleteMovement(m.id),
    onSuccess: () => {
      invalidateLedger(qc);
      setToDelete(null);
      setDeleteErr(null);
      toast("success", "Movimiento borrado");
    },
    onError: (e) => setDeleteErr(errorDetail(e, "No se pudo borrar. Probá de nuevo.")),
  });

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
      <SkeletonReveal ready={!loadingPace} skeleton={<Skeleton className="h-24" />}>
        {() => cities.length === 0 ? null : (
        <div className="animate-rise-in stagger-1 -mx-4 flex gap-2.5 overflow-x-auto px-4 pb-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:-mx-8 lg:px-8">
          <motion.button
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
            aria-pressed={selected.length === 0}
            whileTap={{ scale: 0.96 }}
            className={`flex w-[9.5rem] shrink-0 cursor-pointer flex-col items-start gap-1 rounded-2xl border p-3 text-left transition-colors ${
              selected.length === 0
                ? "focus-ring-inverse border-brick bg-brick text-white soft-pop"
                : "focus-ring border-border bg-surface text-ink-2 soft-card hover:bg-surface-2"
            }`}
          >
            <span className="text-sm font-bold">Todo el viaje</span>
            <span className={`font-display text-lg leading-none font-tabular ${selected.length === 0 ? "text-white" : "text-ink"}`}>
              {pace?.trip.avg_per_day_usd ? `${formatUsd(pace.trip.avg_per_day_usd, "whole")}/día` : "—"}
            </span>
            <span className={`text-[11px] font-medium ${selected.length === 0 ? "text-white/85" : "text-ink-3"}`}>
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
                className={`flex w-[9.5rem] shrink-0 cursor-pointer flex-col items-start gap-1 rounded-2xl border p-3 text-left transition-colors ${
                  active
                    ? "focus-ring-inverse border-brick bg-brick text-white soft-pop"
                    : c.status === "future"
                      ? "focus-ring border-border bg-surface-2/60 text-ink-3 soft-card hover:bg-surface-2"
                      : "focus-ring border-border bg-surface text-ink-2 soft-card hover:bg-surface-2"
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
                {/* También las futuras muestran $/día: con la reserva cargada
                    ya se puede comparar el ritmo previsto contra el resto del
                    viaje. Que sea una proyección lo dice la línea "reservado". */}
                <span className={`font-display text-lg leading-none font-tabular ${active ? "text-white" : "text-ink"}`}>
                  {c.per_day_usd && parseMoney(c.per_day_usd) > 0 ? `${formatUsd(c.per_day_usd, "whole")}/día` : "—"}
                </span>
                {/* ink-3, no ink-faint: los chips futuros son surface-2, donde
                    ink-faint no llega a 4.5:1. */}
                <span className={`text-[11px] font-medium ${active ? "text-white/85" : "text-ink-3"}`}>
                  {chipStatusLine(c)}
                </span>
              </motion.button>
            );
          })}
        </div>
        )}
      </SkeletonReveal>

      {/* Header / hero de la selección */}
      <Card className="animate-rise-in stagger-1 relative overflow-hidden p-5 text-white hero-gradient soft-hero">
        <div className="spit-dots absolute inset-0" aria-hidden="true" />
        <div className="hero-sheen absolute inset-0" aria-hidden="true" />
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
                className="focus-ring-inverse ml-auto flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-full border border-white/40 px-3 text-[11px] font-semibold uppercase tracking-wide text-white/90 transition-colors hover:bg-white/10"
              >
                Andiamo
                <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
              </a>
            )}
          </div>
          <div className="mt-5 flex items-end justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-white/70">Mi gasto</p>
              <p className="font-display text-4xl leading-none tracking-[-0.02em] font-tabular">
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
            value={formatUsd(singlePace.per_day_usd ?? "0", "whole")}
            badge={<DeltaBadge pct={singlePace.delta_vs_trip_pct} compact />}
          />
          <Kpi icon={BedDouble} tint="blue" label="Dormir /noche" value={formatUsd(singlePace.lodging_per_night_usd ?? "0", "whole")} />
          <Kpi icon={UtensilsCrossed} tint="teal" label="Vivir /día" value={formatUsd(singlePace.other_per_day_usd ?? "0", "whole")} />
        </div>
      ) : (
        <div className="animate-rise-in stagger-2 grid grid-cols-3 gap-3">
          <Kpi icon={Receipt} tint="blue" label="Movimientos" value={String(summary?.movement_count ?? 0)} />
          <Kpi icon={BedDouble} tint="teal" label="Noches" value={String(summary?.days ?? 0)} />
          <Kpi icon={TrendingUp} tint="amber" label="Prom./día" value={formatUsd(summary?.avg_per_day_usd ?? "0", "whole")} />
        </div>
      )}

      {/* Donut a ancho completo: desktop con detalle a la derecha; mobile
          apila donut → detalle de categorías → movimientos. */}
      {byCat.length > 0 && (
        <div className="animate-rise-in stagger-3">
          <CategoryDonut data={byCat} sideBySide />
        </div>
      )}

      {/* Detalle de movimientos */}
      <div>
        <h2 className="mb-2 px-1 text-sm font-bold text-ink">Detalle de movimientos</h2>
        <SkeletonReveal
          ready={!loadingMovs}
          skeleton={
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}
            </div>
          }
        >
          {() => movements.length === 0 ? (
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
                  {/* Los headers de día van sobre canvas, afuera del Card: ink-3. */}
                  <span className="font-tabular text-[11px] font-semibold text-ink-3">
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
                      preferShare
                      onOpen={setViewing}
                      onEdit={(mv) => { setEditing(mv); setEditOpen(true); }}
                      onDelete={(mv) => { setDeleteErr(null); setToDelete(mv); }}
                    />
                  ))}
                </Card>
              </section>
            ))}
          </div>
          )}
        </SkeletonReveal>
      </div>

      {viewing && (
        <MovementSheet
          mv={viewing}
          myId={me?.id}
          category={viewing.category_id != null ? catMap[viewing.category_id] : undefined}
          flag={viewing.stop_slug ? stopMap[viewing.stop_slug]?.country_flag : undefined}
          onEdit={(mv) => { setViewing(null); setEditing(mv); setEditOpen(true); }}
          onDelete={(mv) => { setViewing(null); setDeleteErr(null); setToDelete(mv); }}
          onClose={() => setViewing(null)}
        />
      )}
      {editOpen && <AddMovementDialog editing={editing} onClose={() => setEditOpen(false)} />}
      {toDelete && (
        <ConfirmDialog
          title="Borrar movimiento"
          message={`¿Borrar "${toDelete.description || toDelete.type}" (${toDelete.currency} ${formatAmount(toDelete.amount)})?`}
          busy={del.isPending}
          error={deleteErr}
          onConfirm={() => del.mutate(toDelete)}
          onClose={() => { if (!del.isPending) { setToDelete(null); setDeleteErr(null); } }}
        />
      )}
    </div>
  );
}
