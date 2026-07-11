import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { listCategories } from "@/api/categories";
import { createMovement, updateMovement } from "@/api/movements";
import { getMe, listStops, listUsers } from "@/api/users";
import { capitalize, normalizeAmountInput, toInputValue } from "@/lib/format";
import type { Movement } from "@/types";

const CURRENCIES = ["USD", "EUR", "GBP", "CHF", "CZK", "PLN", "HUF", "ARS"];
const SPLITS = [
  { value: "shared", label: "Compartido" },
  { value: "payer_only", label: "Solo pagador" },
  { value: "other_only", label: "Solo del otro" },
];

const field =
  "min-h-[44px] rounded-[4px] border-2 border-border bg-surface px-3 font-semibold focus:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/40";
const label = "text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3";

/** Alta y edición de movimientos. `editing` presente => PATCH parcial. */
export default function AddMovementDialog({ editing, onClose }: {
  editing?: Movement | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const firstRef = useRef<HTMLInputElement>(null);
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: listStops, staleTime: Infinity });
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: Infinity });

  const [amount, setAmount] = useState(toInputValue(editing?.amount));
  const [currency, setCurrency] = useState(editing?.currency ?? "USD");
  const [description, setDescription] = useState(editing?.description ?? "");
  const [categoryId, setCategoryId] = useState<string>(editing?.category_id?.toString() ?? "");
  const [split, setSplit] = useState(editing?.split ?? "shared");
  const [date, setDate] = useState(editing?.movement_date ?? new Date().toISOString().slice(0, 10));
  const [stopSlug, setStopSlug] = useState<string>(editing?.stop_slug ?? "");
  const [paidBy, setPaidBy] = useState<string>(editing?.paid_by?.toString() ?? "");
  const [err, setErr] = useState<string | null>(null);

  // Nuevo movimiento: default de pagador = usuario logueado, cuando llega `me`.
  useEffect(() => {
    if (!editing && me && !paidBy) setPaidBy(String(me.id));
  }, [editing, me, paidBy]);

  useEffect(() => {
    firstRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = useMutation({
    mutationFn: async () => {
      const stop = stops.find((s) => s.slug === stopSlug);
      const body: Partial<Movement> = {
        amount: normalizeAmountInput(amount),
        currency,
        description: description || null,
        category_id: categoryId ? Number(categoryId) : null,
        split,
        movement_date: date,
        // Ciudad vacía => el backend deriva por fecha.
        stop_slug: stop ? stop.slug : null,
        city_name: stop ? stop.name : null,
      };
      if (paidBy) body.paid_by = Number(paidBy);
      return editing ? updateMovement(editing.id, body) : createMovement(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
      onClose();
    },
    onError: () => setErr("No se pudo guardar. Revisá el monto."),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!amount || Number.isNaN(Number(normalizeAmountInput(amount)))) {
      setErr("Ingresá un monto válido.");
      return;
    }
    save.mutate();
  }

  // Portal al body: un ancestro con transform (animate-fade-in de la página)
  // convierte a `fixed` en relativo a ese ancestro y el dialog se corta.
  return createPortal(
    <div
      className="fixed inset-0 z-20 flex items-end justify-center bg-ink/40 sm:items-center"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={editing ? "Editar movimiento" : "Agregar movimiento"}
        className="max-h-[92dvh] w-full max-w-md animate-fade-in overflow-y-auto rounded-t-[8px] border-2 border-ink bg-canvas p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:max-h-[85dvh] sm:rounded-[4px] sm:hard-shadow-ink"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-2xl uppercase text-ink">
            {editing ? "Editar" : "Agregar"}
          </h2>
          <button
            aria-label="Cerrar"
            className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[4px] text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            onClick={onClose}
          >
            <X size={20} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="grid grid-cols-[1fr_auto] gap-3">
            <label className="flex flex-col gap-1">
              <span className={label}>Monto</span>
              <input ref={firstRef} className={field} inputMode="decimal" placeholder="20,00"
                     value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1">
              <span className={label}>Moneda</span>
              <select className={`${field} cursor-pointer`} value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
          </div>
          <label className="flex flex-col gap-1">
            <span className={label}>Descripción</span>
            <input className={field} placeholder="cena, taxi, museo…"
                   value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className={label}>Categoría</span>
              <select className={`${field} cursor-pointer`} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">—</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className={label}>Ciudad</span>
              <select className={`${field} cursor-pointer`} value={stopSlug} onChange={(e) => setStopSlug(e.target.value)}>
                <option value="">Auto (por fecha)</option>
                {stops.map((s) => (
                  <option key={s.slug} value={s.slug}>{s.country_flag ? `${s.country_flag} ` : ""}{s.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className={label}>División</span>
              <select className={`${field} cursor-pointer`} value={split} onChange={(e) => setSplit(e.target.value)}>
                {SPLITS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className={label}>Pagó</span>
              <select className={`${field} cursor-pointer`} value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{capitalize(u.username)}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="flex flex-col gap-1">
            <span className={label}>Fecha</span>
            <input className={field} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
          <button
            disabled={save.isPending}
            className="mt-1 min-h-[48px] cursor-pointer rounded-[2px] bg-brick font-display text-lg uppercase tracking-wide text-surface hard-shadow-ink transition-transform hover:brightness-105 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:opacity-60"
          >
            {save.isPending ? "Guardando…" : "Guardar"}
          </button>
        </form>
      </div>
    </div>,
    document.body,
  );
}
