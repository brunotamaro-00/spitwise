import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, SlidersHorizontal, X } from "lucide-react";
import { useMemo, useState } from "react";

import { listCategories } from "@/api/categories";
import { deleteMovement, listMovements } from "@/api/movements";
import { getMe } from "@/api/users";
import AddMovementDialog from "@/components/AddMovementDialog";
import MovementRow from "@/components/MovementRow";
import { formatUsd } from "@/lib/format";
import { involvesMe, myShare } from "@/lib/share";
import type { Category, Movement } from "@/types";

const field =
  "min-h-[40px] rounded-[4px] border-2 border-border bg-surface px-2 text-sm font-semibold focus:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/40";
const flabel = "text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3";

const EMPTY = { onlyMine: false, city: "", categoryId: "", from: "", to: "", q: "" };

export default function Movements() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Movement | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [f, setF] = useState(EMPTY);

  const { data = [], isLoading } = useQuery({ queryKey: ["movements"], queryFn: listMovements });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const catMap = useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c])) as Record<number, Category>,
    [categories],
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

  function onDelete(m: Movement) {
    if (window.confirm(`¿Borrar "${m.description || m.type}" (${m.currency} ${m.amount})?`)) {
      del.mutate(m);
    }
  }

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
    <div className="animate-fade-in">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h1 className="font-display text-3xl uppercase leading-none text-ink">Movimientos</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters((v) => !v)}
            aria-expanded={showFilters}
            className={`relative flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[4px] border-2 border-border transition-colors hover:bg-surface-2 ${showFilters ? "text-brick" : "text-ink-3"}`}
            aria-label="Filtros"
          >
            <SlidersHorizontal size={18} strokeWidth={1.75} aria-hidden="true" />
            {activeCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brick px-1 text-[10px] font-extrabold text-surface">
                {activeCount}
              </span>
            )}
          </button>
          <button
            onClick={() => { setEditing(null); setOpen(true); }}
            className="flex min-h-[44px] cursor-pointer items-center gap-1 rounded-[2px] bg-brick px-3 font-display uppercase text-surface hard-shadow-ink transition-transform hover:brightness-105 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none"
          >
            <Plus size={16} strokeWidth={2} aria-hidden="true" /> Agregar
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="mb-3 rounded-[4px] border-2 border-border bg-surface p-4 card-shadow">
          <label className="mb-3 flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              className="h-5 w-5 accent-brick"
              checked={f.onlyMine}
              onChange={(e) => setF({ ...f, onlyMine: e.target.checked })}
            />
            <span className="text-sm font-bold text-ink">Solo movimientos míos</span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className={flabel}>Ciudad</span>
              <select className={`${field} cursor-pointer`} value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })}>
                <option value="">Todas</option>
                {cities.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className={flabel}>Categoría</span>
              <select className={`${field} cursor-pointer`} value={f.categoryId} onChange={(e) => setF({ ...f, categoryId: e.target.value })}>
                <option value="">Todas</option>
                {categories.filter((c) => usedCategoryIds.has(c.id)).map((c) => (
                  <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className={flabel}>Desde</span>
              <input type="date" className={field} value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1">
              <span className={flabel}>Hasta</span>
              <input type="date" className={field} value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} />
            </label>
          </div>
          <label className="mt-3 flex flex-col gap-1">
            <span className={flabel}>Buscar</span>
            <input className={field} placeholder="descripción o ciudad…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
          </label>
          {activeCount > 0 && (
            <button
              onClick={() => setF(EMPTY)}
              className="mt-3 flex cursor-pointer items-center gap-1 text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3 hover:text-ink"
            >
              <X size={14} strokeWidth={2} aria-hidden="true" /> Limpiar filtros
            </button>
          )}
        </div>
      )}

      {!isLoading && data.length > 0 && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-[4px] border-2 border-border bg-surface-2 px-4 py-2">
          <span className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {filtered.length} de {data.length} · gasto visible{" "}
            <span className="font-tabular text-ink">{formatUsd(String(totals.visible))}</span>
          </span>
          <span className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
            tu parte <span className="font-tabular text-brick">{formatUsd(String(totals.mine))}</span>
          </span>
        </div>
      )}

      <div className="rounded-[4px] border-2 border-border bg-surface px-4 card-shadow">
        {filtered.map((m) => (
          <MovementRow key={m.id} mv={m} myId={me?.id}
            category={m.category_id != null ? catMap[m.category_id] : undefined}
            onEdit={(mv) => { setEditing(mv); setOpen(true); }}
            onDelete={onDelete} />
        ))}
        {!isLoading && data.length === 0 && (
          <p className="py-10 text-center text-ink-3">Sin movimientos todavía.</p>
        )}
        {!isLoading && data.length > 0 && filtered.length === 0 && (
          <p className="py-10 text-center text-ink-3">Ningún movimiento coincide con los filtros.</p>
        )}
      </div>
      {open && <AddMovementDialog editing={editing} onClose={() => setOpen(false)} />}
    </div>
  );
}
