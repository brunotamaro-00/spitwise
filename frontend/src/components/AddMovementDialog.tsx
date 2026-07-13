import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listCategories } from "@/api/categories";
import { createMovement, updateMovement } from "@/api/movements";
import { getMe, listStops, listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import DatePicker from "@/components/ui/DatePicker";
import { Field, Input, Label, Select } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import { categoryIcon } from "@/lib/categoryIcons";
import { capitalize, normalizeAmountInput, sanitizeAmountInput, toInputValue } from "@/lib/format";
import type { Movement } from "@/types";

const GENERAL = "__general__"; // gasto sin ciudad
const CURRENCIES = ["USD", "EUR", "GBP", "CHF", "CZK", "PLN", "HUF", "ARS"];
const SPLITS = [
  { value: "shared", label: "Compartido" },
  { value: "payer_only", label: "Solo pagador" },
  { value: "other_only", label: "Solo del otro" },
];

/** Grupo de botones exclusivos (segmented control). */
function Segmented({ options, value, onChange }: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex rounded-lg border border-border bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`min-h-[38px] flex-1 cursor-pointer rounded-md px-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
            value === o.value ? "bg-surface text-ink shadow-sm" : "text-ink-3 hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Alta y edición de movimientos. `editing` presente => PATCH parcial.
 *  Diseñado para cargar un gasto en segundos: monto grande primero,
 *  categoría como chips con ícono, pagador/división como segmented. */
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
  // Sin ciudad al editar (y sin parada) => se asume gasto general.
  const [stopSlug, setStopSlug] = useState<string>(
    editing?.stop_slug ?? (editing && !editing.city_name ? GENERAL : ""),
  );
  const [paidBy, setPaidBy] = useState<string>(editing?.paid_by?.toString() ?? "");
  const [err, setErr] = useState<string | null>(null);

  // Nuevo movimiento: default de pagador = usuario logueado, cuando llega `me`.
  useEffect(() => {
    if (!editing && me && !paidBy) setPaidBy(String(me.id));
  }, [editing, me, paidBy]);

  useEffect(() => { firstRef.current?.focus(); }, []);

  const save = useMutation({
    mutationFn: async () => {
      const stop = stops.find((s) => s.slug === stopSlug);
      const body: Partial<Movement> & { general?: boolean } = {
        amount: normalizeAmountInput(amount),
        currency,
        description: description || null,
        category_id: categoryId ? Number(categoryId) : null,
        split,
        movement_date: date,
        // Ciudad vacía => el backend deriva por fecha. "General" => sin ciudad.
        stop_slug: stop ? stop.slug : null,
        city_name: stop ? stop.name : null,
        general: stopSlug === GENERAL,
      };
      if (paidBy) body.paid_by = Number(paidBy);
      return editing ? updateMovement(editing.id, body) : createMovement(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
      qc.invalidateQueries({ queryKey: ["city"] });
      onClose();
    },
    onError: () => setErr("No se pudo guardar. Revisá el monto."),
  });

  function submit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    if (!amount || Number.isNaN(Number(normalizeAmountInput(amount)))) {
      setErr("Ingresá un monto válido.");
      return;
    }
    save.mutate();
  }

  return (
    <Modal title={editing ? "Editar movimiento" : "Agregar movimiento"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        {/* El monto manda: input display grande + moneda al lado. */}
        <div className="rounded-xl border border-border bg-surface-2/50 p-4">
          <Label>Monto</Label>
          <div className="mt-1 flex items-center gap-3">
            <input
              ref={firstRef}
              inputMode="decimal"
              placeholder="0,00"
              aria-label="Monto"
              value={amount}
              onChange={(e) => setAmount(sanitizeAmountInput(e.target.value))}
              className="w-full min-w-0 bg-transparent font-display text-4xl leading-none text-ink outline-none font-tabular placeholder:text-ink-faint"
            />
            {/* wrapper de ancho fijo: el Select base trae w-full */}
            <div className="w-24 shrink-0">
              <Select value={currency} onChange={(e) => setCurrency(e.target.value)} aria-label="Moneda">
                {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
              </Select>
            </div>
          </div>
        </div>

        <Field label="Descripción">
          <Input placeholder="cena, taxi, museo…"
                 value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>

        {/* Categoría: chips con ícono, un toque; tocar de nuevo deselecciona. */}
        <div className="flex flex-col gap-1.5">
          <Label>Categoría</Label>
          <div className="flex flex-wrap gap-2">
            {categories.map((c) => {
              const active = categoryId === String(c.id);
              const Icon = categoryIcon(c.name);
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setCategoryId(active ? "" : String(c.id))}
                  aria-pressed={active}
                  className={`flex min-h-[36px] cursor-pointer items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
                    active ? "" : "border-border bg-surface text-ink-2 hover:bg-surface-2"
                  }`}
                  style={active ? {
                    background: categoryBg(c.name),
                    color: categoryColor(c.name),
                    borderColor: categoryColor(c.name),
                  } : undefined}
                >
                  <Icon size={14} strokeWidth={2} aria-hidden="true" />
                  {c.name}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Pagó</Label>
          <Segmented
            options={users.map((u) => ({ value: String(u.id), label: capitalize(u.username) }))}
            value={paidBy}
            onChange={setPaidBy}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>División</Label>
          <Segmented options={SPLITS} value={split} onChange={setSplit} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Ciudad">
            <Select value={stopSlug} onChange={(e) => setStopSlug(e.target.value)}>
              <option value="">Auto (por fecha)</option>
              <option value={GENERAL}>General (sin ciudad)</option>
              {stops.map((s) => (
                <option key={s.slug} value={s.slug}>{s.country_flag ? `${s.country_flag} ` : ""}{s.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Fecha">
            <DatePicker value={date} onChange={setDate} stops={stops} />
          </Field>
        </div>

        {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
        <Button type="submit" disabled={save.isPending} className="mt-1">
          {save.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </form>
    </Modal>
  );
}
