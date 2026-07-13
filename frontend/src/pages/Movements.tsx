import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Receipt, SearchX, SlidersHorizontal, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listCategories } from "@/api/categories";
import { getStops } from "@/api/cities";
import { deleteMovement, listMovements } from "@/api/movements";
import { getMe } from "@/api/users";
import AddMovementDialog from "@/components/AddMovementDialog";
import MovementRow from "@/components/MovementRow";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import { Field, Input, Select } from "@/components/ui/Field";
import Skeleton from "@/components/ui/Skeleton";
import { formatDayHeader, formatUsd } from "@/lib/format";
import { dayTotalUsd, groupByDay } from "@/lib/groupByDay";
import { involvesMe, myShare } from "@/lib/share";
import type { Category, Movement } from "@/types";

const EMPTY = { onlyMine: false, city: "", categoryId: "", from: "", to: "", q: "" };

export default function Movements() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Movement | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Movement | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [params, setParams] = useSearchParams();
  // Estado inicial desde la URL, para que los deep-links del bot lleguen filtrados.
  const [sort, setSort] = useState<"date" | "created">(
    params.get("sort") === "created" ? "created" : "date",
  );
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
    if (sort !== "date") p.set("sort", sort);
    setParams(p, { replace: true });
  }, [f, sort, setParams]);

  const { data = [], isLoading } = useQuery({
    queryKey: ["movements", sort],
    queryFn: () => listMovements(sort),
  });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: getStops, staleTime: 60_000 });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const catMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c])) as Record<number, Category>,
    [categories],
  );
  const flagMap = useMemo(
    () => Object.fromEntries(stops.map((s) => [s.slug, s.country_flag])) as Record<string, string | null>,
    [stops],
  );
  const cities = useMemo(
    () => [...new Set(data.map((m) => m.city_name).filter(Boolean))] as string[],
    [data],
  );
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
    },
  });

  const filtered = useMemo(() => {
    const q = f.q.trim().toLowerCase();
    return data.filter((m) => {
      if (f.onlyMine && me && !involvesMe(m, me.id)) return false;
      if (f.city && m.city_name !== f.city) return false;
      if (f.categoryId && String(m.category_id) !== f.categoryId) return false;
      if (f.from && m.movement_date < f.from) return false;
      if (f.to && m.movement_date > f.to) return false;
      if (q && !`${m.description ?? ""} ${m.city_name ?? ""}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [data, f, me]);

  // Agrupar preservando el orden del backend, por la fecha del criterio activo:
  // "date" = fecha imputada; "created" = fecha de carga (created_at).
  const groups = useMemo(
    () =>
      groupByDay(filtered, (m) =>
        sort === "created" ? m.created_at.slice(0, 10) : m.movement_date,
      ),
    [filtered, sort],
  );

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
          onClick={() => setShowFilters((v) => !v)}
          aria-expanded={showFilters}
          aria-label="Filtros"
          className={`relative flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-lg border border-border bg-surface transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${showFilters ? "text-brick" : "text-ink-3"}`}
        >
          <SlidersHorizontal size={18} strokeWidth={1.75} aria-hidden="true" />
          {activeCount > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brick px-1 text-[10px] font-bold text-white">
              {activeCount}
            </span>
          )}
        </button>
      </div>

      {showFilters && (
        <Card className="mb-3 animate-fade-in p-5">
          <div className="mb-3">
            <span className="mb-1.5 block text-xs font-semibold text-ink-3">Ordenar por</span>
            <div className="inline-flex rounded-lg border border-border bg-surface-2 p-0.5">
              {([["date", "Fecha imputada"], ["created", "Fecha de carga"]] as const).map(([v, label]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setSort(v)}
                  aria-pressed={sort === v}
                  className={`min-h-[36px] cursor-pointer rounded-md px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
                    sort === v ? "bg-surface text-ink shadow-sm" : "text-ink-3 hover:text-ink"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <label className="mb-3 flex cursor-pointer items-center gap-2.5">
            <input
              type="checkbox"
              className="h-5 w-5 accent-brick"
              checked={f.onlyMine}
              onChange={(e) => setF({ ...f, onlyMine: e.target.checked })}
            />
            <span className="text-sm font-semibold text-ink">Solo movimientos míos</span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Ciudad">
              <Select value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })}>
                <option value="">Todas</option>
                {cities.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            <Field label="Categoría">
              <Select value={f.categoryId} onChange={(e) => setF({ ...f, categoryId: e.target.value })}>
                <option value="">Todas</option>
                {categories.filter((c) => usedCategoryIds.has(c.id)).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Desde">
              <Input type="date" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} />
            </Field>
            <Field label="Hasta">
              <Input type="date" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} />
            </Field>
          </div>
          <div className="mt-3">
            <Field label="Buscar">
              <Input placeholder="descripción o ciudad…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
            </Field>
          </div>
          {activeCount > 0 && (
            <button
              onClick={() => setF(EMPTY)}
              className="mt-3 flex cursor-pointer items-center gap-1 rounded text-xs font-medium text-ink-3 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            >
              <X size={14} strokeWidth={2} aria-hidden="true" /> Limpiar filtros
            </button>
          )}
        </Card>
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

      {isLoading && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}
        </div>
      )}

      {!isLoading && data.length === 0 && (
        <Card>
          <EmptyState icon={Receipt} title="Sin movimientos todavía"
            description="Tocá el botón + para cargar el primer gasto del viaje." />
        </Card>
      )}

      {!isLoading && data.length > 0 && filtered.length === 0 && (
        <Card>
          <EmptyState icon={SearchX} title="Nada coincide"
            description="Ningún movimiento coincide con los filtros aplicados." />
        </Card>
      )}

      {groups.length > 0 && (
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <section key={g.date}>
              <h2 className="mb-1.5 flex items-baseline justify-between gap-2 px-1">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                  {formatDayHeader(g.date)}
                </span>
                <span className="font-tabular text-[11px] font-semibold text-ink-faint">
                  {formatUsd(String(dayTotalUsd(g.items)))}
                </span>
              </h2>
              <Card className="px-5">
                {g.items.map((m) => (
                  <MovementRow key={m.id} mv={m} myId={me?.id}
                    category={m.category_id != null ? catMap[m.category_id] : undefined}
                    flag={m.stop_slug ? flagMap[m.stop_slug] : undefined}
                    onEdit={(mv) => { setEditing(mv); setEditOpen(true); }}
                    onDelete={(mv) => setToDelete(mv)} />
                ))}
              </Card>
            </section>
          ))}
        </div>
      )}

      {editOpen && <AddMovementDialog editing={editing} onClose={() => setEditOpen(false)} />}
      {toDelete && (
        <ConfirmDialog
          title="Borrar movimiento"
          message={`¿Borrar "${toDelete.description || toDelete.type}" (${toDelete.currency} ${toDelete.amount})?`}
          onConfirm={() => del.mutate(toDelete)}
          onClose={() => setToDelete(null)}
        />
      )}
    </div>
  );
}
