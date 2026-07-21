import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Receipt, Search, SearchX, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listCategories } from "@/api/categories";
import { getStops } from "@/api/cities";
import { deleteMovement, listMovements } from "@/api/movements";
import AddMovementDialog from "@/components/AddMovementDialog";
import MovementFiltersSheet, {
  type CityOption,
  NO_CITY,
  NO_CITY_LABEL,
} from "@/components/MovementFiltersSheet";
import MovementRow from "@/components/MovementRow";
import MovementSheet from "@/components/MovementSheet";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Field";
import Skeleton from "@/components/ui/Skeleton";
import SkeletonReveal from "@/components/ui/SkeletonReveal";
import { useToast } from "@/components/ui/Toast";
import { formatAmount, formatDayHeader, formatShortDate, formatUsd } from "@/lib/format";
import { createdDayKey, dayTotalShare, dayTotalUsd, groupByDay } from "@/lib/groupByDay";
import { involvesMe, myShare } from "@/lib/share";
import { useMe } from "@/lib/useMe";
import type { Category, Movement } from "@/types";

const EMPTY = { onlyMine: false, city: "", categoryId: "", from: "", to: "", q: "" };

/** Pill removible de un filtro activo. */
function FilterPill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="animate-fade-in inline-flex items-center gap-0.5 rounded-full border border-brick-border bg-brick-bg py-1 pl-2.5 pr-1 text-xs font-semibold text-brick">
      {label}
      <button
        type="button"
        aria-label={`Quitar filtro ${label}`}
        onClick={onRemove}
        className="flex h-5 w-5 cursor-pointer items-center justify-center rounded-full transition-colors hover:bg-brick/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
      >
        <X size={12} strokeWidth={2.25} aria-hidden="true" />
      </button>
    </span>
  );
}

export default function Movements() {
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<Movement | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [viewing, setViewing] = useState<Movement | null>(null);
  const [toDelete, setToDelete] = useState<Movement | null>(null);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [params, setParams] = useSearchParams();
  // Estado inicial desde la URL, para que los deep-links del bot lleguen filtrados.
  const [f, setF] = useState({
    onlyMine: params.get("mine") === "1",
    city: params.get("city") ?? "",
    categoryId: params.get("cat") ?? "",
    from: params.get("from") ?? "",
    to: params.get("to") ?? "",
    q: params.get("q") ?? "",
  });

  // Sincroniza filtros → URL (para copiar/compartir y para deep-links).
  useEffect(() => {
    const p = new URLSearchParams();
    if (f.onlyMine) p.set("mine", "1");
    if (f.city) p.set("city", f.city);
    if (f.categoryId) p.set("cat", f.categoryId);
    if (f.from) p.set("from", f.from);
    if (f.to) p.set("to", f.to);
    if (f.q) p.set("q", f.q);
    setParams(p, { replace: true });
  }, [f, setParams]);

  const { data = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["movements"],
    queryFn: listMovements,
  });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: getStops, staleTime: 60_000 });
  const { data: me } = useMe();

  const catMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c])) as Record<number, Category>,
    [categories],
  );
  const flagMap = useMemo(
    () => Object.fromEntries(stops.map((s) => [s.slug, s.country_flag])) as Record<string, string | null>,
    [stops],
  );
  // Ciudades con movimientos, con su bandera (vía el stop del primer movimiento).
  // Si hay gastos sin parada, se agrega al final la opción "Sin ciudad" (General).
  const cityOptions = useMemo<CityOption[]>(() => {
    const seen = new Map<string, string | null>();
    let hasNone = false;
    for (const m of data) {
      if (m.city_name) {
        if (!seen.has(m.city_name)) {
          seen.set(m.city_name, m.stop_slug ? flagMap[m.stop_slug] ?? null : null);
        }
      } else {
        hasNone = true;
      }
    }
    const opts: CityOption[] = [...seen].map(([name, flag]) => ({ name, flag }));
    if (hasNone) opts.push({ name: NO_CITY, flag: null });
    return opts;
  }, [data, flagMap]);
  const usedCategoryIds = useMemo(
    () => new Set(data.map((m) => m.category_id).filter((x): x is number => x != null)),
    [data],
  );

  const del = useMutation({
    mutationFn: (m: Movement) => deleteMovement(m.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
      qc.invalidateQueries({ queryKey: ["city"] });
      setToDelete(null);
      setDeleteErr(null);
      toast("success", "Movimiento borrado");
    },
    onError: () => setDeleteErr("No se pudo borrar. Probá de nuevo."),
  });

  const filtered = useMemo(() => {
    const q = f.q.trim().toLowerCase();
    return data.filter((m) => {
      if (f.onlyMine && me && !involvesMe(m, me.id)) return false;
      if (f.city && (f.city === NO_CITY ? m.city_name != null : m.city_name !== f.city)) return false;
      if (f.categoryId && String(m.category_id) !== f.categoryId) return false;
      if (f.from && createdDayKey(m) < f.from) return false;
      if (f.to && createdDayKey(m) > f.to) return false;
      if (q && !`${m.description ?? ""} ${m.city_name ?? ""}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [data, f, me]);

  // Agrupar preservando el orden del backend, por día de carga en TZ del browser.
  const groups = useMemo(() => groupByDay(filtered), [filtered]);

  const totals = useMemo(() => {
    let visible = 0;
    let mine = 0;
    for (const m of filtered) {
      if (m.type !== "expense") continue;
      visible += Number(m.amount_usd);
      if (me) mine += myShare(m, me.id);
    }
    return { visible, mine };
  }, [filtered, me]);

  const activeCount =
    (f.onlyMine ? 1 : 0) + (f.city ? 1 : 0) + (f.categoryId ? 1 : 0) +
    (f.from ? 1 : 0) + (f.to ? 1 : 0) + (f.q ? 1 : 0);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <PageTitle>Movimientos</PageTitle>
        <button
          onClick={() => setShowFilters(true)}
          aria-label="Filtros"
          aria-haspopup="dialog"
          className="relative flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-lg border border-border bg-surface text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
        >
          <SlidersHorizontal size={18} strokeWidth={1.75} aria-hidden="true" />
          {activeCount > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brick px-1 text-[10px] font-bold text-white">
              {activeCount}
            </span>
          )}
        </button>
      </div>

      {isError && (
        <div className="mb-3">
          <ErrorState onRetry={() => refetch()} />
        </div>
      )}

      {/* Búsqueda siempre a mano; el resto de los filtros viven en el sheet. */}
      <div className="relative mb-3">
        <Search
          size={16}
          strokeWidth={2}
          aria-hidden="true"
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint"
        />
        <Input
          placeholder="Buscar descripción o ciudad…"
          aria-label="Buscar movimientos"
          value={f.q}
          onChange={(e) => setF({ ...f, q: e.target.value })}
          className="pl-10 pr-11"
        />
        {f.q && (
          <button
            type="button"
            aria-label="Limpiar búsqueda"
            onClick={() => setF({ ...f, q: "" })}
            className="animate-fade-in absolute inset-y-0 right-0 flex w-11 cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
          >
            <X size={16} strokeWidth={2} aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Pills de filtros activos (la búsqueda tiene su propia X). */}
      {(f.onlyMine || f.city || f.categoryId || f.from || f.to) && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {f.onlyMine && (
            <FilterPill label="Solo míos" onRemove={() => setF({ ...f, onlyMine: false })} />
          )}
          {f.categoryId && (
            <FilterPill
              label={catMap[Number(f.categoryId)]?.name ?? "Categoría"}
              onRemove={() => setF({ ...f, categoryId: "" })}
            />
          )}
          {f.city && (
            <FilterPill
              label={f.city === NO_CITY ? NO_CITY_LABEL : f.city}
              onRemove={() => setF({ ...f, city: "" })}
            />
          )}
          {(f.from || f.to) && (
            <FilterPill
              label={
                f.from && f.to
                  ? f.from === f.to
                    ? formatShortDate(f.from)
                    : `${formatShortDate(f.from)} – ${formatShortDate(f.to)}`
                  : f.from
                    ? `desde ${formatShortDate(f.from)}`
                    : `hasta ${formatShortDate(f.to)}`
              }
              onRemove={() => setF({ ...f, from: "", to: "" })}
            />
          )}
          <button
            onClick={() => setF(EMPTY)}
            className="cursor-pointer rounded px-1 text-xs font-medium text-ink-3 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
          >
            Limpiar todo
          </button>
        </div>
      )}

      {!isLoading && data.length > 0 && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-xl border border-border bg-surface-2 px-4 py-2.5">
          <span className="text-xs text-ink-3">
            {filtered.length} de {data.length} · visible{" "}
            <span className="font-tabular text-sm font-semibold text-ink">{formatUsd(String(totals.visible))}</span>
          </span>
          <span className="text-xs text-ink-3">
            tu parte{" "}
            <span className="font-tabular text-sm font-semibold text-brick">{formatUsd(String(totals.mine))}</span>
          </span>
        </div>
      )}

      <SkeletonReveal
        ready={!isLoading}
        skeleton={
          <div className="flex flex-col gap-2">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}
          </div>
        }
      >
        {() => data.length === 0 ? (
        <Card>
          <EmptyState icon={Receipt} title="Sin movimientos todavía"
            description="Tocá el botón + para cargar el primer gasto del viaje." />
        </Card>
        ) : filtered.length === 0 ? (
        <Card>
          <EmptyState icon={SearchX} title="Nada coincide"
            description="Ningún movimiento coincide con los filtros aplicados." />
        </Card>
        ) : (
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <section key={g.date}>
              <h2 className="mb-1.5 flex items-baseline justify-between gap-2 px-1">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                  {formatDayHeader(g.date)}
                </span>
                <span className="font-tabular text-[11px] font-semibold text-ink-faint">
                  {formatUsd(String(
                    f.onlyMine && me ? dayTotalShare(g.items, me.id) : dayTotalUsd(g.items),
                  ))}
                </span>
              </h2>
              <Card className="px-5">
                {g.items.map((m) => (
                  <MovementRow key={m.id} mv={m} myId={me?.id}
                    category={m.category_id != null ? catMap[m.category_id] : undefined}
                    flag={m.stop_slug ? flagMap[m.stop_slug] : undefined}
                    preferShare={f.onlyMine}
                    onOpen={setViewing}
                    onEdit={(mv) => { setEditing(mv); setEditOpen(true); }}
                    onDelete={(mv) => { setDeleteErr(null); setToDelete(mv); }} />
                ))}
              </Card>
            </section>
          ))}
        </div>
        )}
      </SkeletonReveal>

      {viewing && (
        <MovementSheet
          mv={viewing}
          myId={me?.id}
          category={viewing.category_id != null ? catMap[viewing.category_id] : undefined}
          flag={viewing.stop_slug ? flagMap[viewing.stop_slug] : undefined}
          onEdit={(mv) => { setViewing(null); setEditing(mv); setEditOpen(true); }}
          onDelete={(mv) => { setViewing(null); setDeleteErr(null); setToDelete(mv); }}
          onClose={() => setViewing(null)}
        />
      )}
      {showFilters && (
        <MovementFiltersSheet
          filters={f}
          categories={categories.filter((c) => usedCategoryIds.has(c.id))}
          cities={cityOptions}
          activeCount={activeCount}
          onChange={(patch) => setF((prev) => ({ ...prev, ...patch }))}
          onClear={() => setF(EMPTY)}
          onClose={() => setShowFilters(false)}
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
