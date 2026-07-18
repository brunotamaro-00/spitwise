import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusCircle } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { listCategories } from "@/api/categories";
import { createMovement, updateMovement } from "@/api/movements";
import { listStops, listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import { Field, Input, Label, Select } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import { categoryIcon } from "@/lib/categoryIcons";
import { capitalize, normalizeAmountInput, sanitizeAmountInput, toInputValue, todayLocal } from "@/lib/format";
import { stopForDate } from "@/lib/stops";
import { useMe } from "@/lib/useMe";
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
        <motion.button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          whileTap={{ scale: 0.96 }}
          className={`min-h-[38px] flex-1 cursor-pointer rounded-md px-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
            value === o.value ? "bg-surface text-ink shadow-sm" : "text-ink-3 hover:text-ink"
          }`}
        >
          {o.label}
        </motion.button>
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
  const toast = useToast();
  const firstRef = useRef<HTMLInputElement>(null);
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: listStops, staleTime: Infinity });
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const { data: me } = useMe();

  const [amount, setAmount] = useState(toInputValue(editing?.amount));
  const [currency, setCurrency] = useState(editing?.currency ?? "USD");
  const currencyTouched = useRef(false);
  const [description, setDescription] = useState(editing?.description ?? "");
  const [categoryId, setCategoryId] = useState<string>(editing?.category_id?.toString() ?? "");
  const [split, setSplit] = useState(editing?.split ?? "shared");
  // Sin ciudad al editar (y sin parada) => se asume gasto general.
  const [stopSlug, setStopSlug] = useState<string>(
    editing?.stop_slug ?? (editing && !editing.city_name ? GENERAL : ""),
  );
  const [paidBy, setPaidBy] = useState<string>(editing?.paid_by?.toString() ?? "");
  const [err, setErr] = useState<string | null>(null);
  // `completing`: partimos de un gasto existente y cargamos SOLO la parte que
  // falta como un movimiento nuevo. El original no se toca.
  const [completing, setCompleting] = useState(false);
  const isExpense = (editing?.type ?? "expense") === "expense";

  // Nuevo movimiento: default de pagador = usuario logueado, cuando llega `me`.
  useEffect(() => {
    if (!editing && me && !paidBy) setPaidBy(String(me.id));
  }, [editing, me, paidBy]);

  // Moneda default = la de la parada activa hoy (como hace el bot), no USD.
  // Solo mientras el usuario no la haya tocado.
  const activeCurrency = stopForDate(stops, todayLocal())?.currency_code ?? "USD";
  useEffect(() => {
    if (!editing && !currencyTouched.current && stops.length > 0) setCurrency(activeCurrency);
  }, [editing, stops, activeCurrency]);
  // La moneda de la parada activa puede no estar en la lista fija (p.ej. RON).
  const currencyOptions = [...new Set([activeCurrency, ...CURRENCIES, currency])];

  useEffect(() => { firstRef.current?.focus(); }, []);

  // Pasa a modo "completar": clona ciudad/categoría/fecha/moneda del gasto y
  // deja el monto vacío + pagador en mí, listo para cargar el resto.
  function enterComplete() {
    setCompleting(true);
    setAmount("");
    setErr(null);
    if (me) setPaidBy(String(me.id));
    requestAnimationFrame(() => firstRef.current?.focus());
  }

  const origPayer = editing && users.find((u) => u.id === editing.paid_by);

  const save = useMutation({
    mutationFn: async () => {
      const stop = stops.find((s) => s.slug === stopSlug);
      const isEdit = Boolean(editing && !completing);
      const body: Partial<Movement> & { general?: boolean } = {
        amount: normalizeAmountInput(amount),
        currency,
        description: description || null,
        category_id: categoryId ? Number(categoryId) : null,
        split,
      };
      if (paidBy) body.paid_by = Number(paidBy);

      // La ciudad la deriva siempre el backend del stop_slug (nunca texto libre).
      if (stopSlug === GENERAL) {
        body.stop_slug = null;
        body.general = true;
      } else if (stop) {
        body.stop_slug = stop.slug;
      } else if (!isEdit) {
        // Create + Auto: null => backend imputa la parada de hoy.
        body.stop_slug = null;
      }
      // Edit + Auto: omitir stop_slug para no tocar la ciudad ya asignada.

      return isEdit ? updateMovement(editing!.id, body) : createMovement(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["balance"] });
      qc.invalidateQueries({ queryKey: ["city"] });
      toast("success", completing ? "Resto cargado" : editing ? "Cambios guardados" : "Gasto guardado");
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

  const title = completing ? "Completar el resto" : editing ? "Editar movimiento" : "Agregar movimiento";

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        {completing && (
          <p className="rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-[13px] leading-snug text-ink-2">
            Se carga un <span className="font-semibold text-ink">movimiento nuevo</span> por la parte que falta.
            {editing && (
              <> El original ({editing.currency} {editing.amount}
                {origPayer ? `, pagó ${capitalize(origPayer.username)}` : ""}) queda intacto.</>
            )}
          </p>
        )}
        {/* El monto manda: input display grande + moneda al lado. */}
        <div className="rounded-xl border border-border bg-surface-2/50 p-3.5">
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
              <Select
                value={currency}
                onChange={(e) => { currencyTouched.current = true; setCurrency(e.target.value); }}
                aria-label="Moneda"
              >
                {currencyOptions.map((c) => <option key={c}>{c}</option>)}
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
          <div className="flex flex-wrap gap-1.5">
            {categories.map((c) => {
              const active = categoryId === String(c.id);
              const Icon = categoryIcon(c.name);
              return (
                <motion.button
                  key={c.id}
                  type="button"
                  onClick={() => setCategoryId(active ? "" : String(c.id))}
                  aria-pressed={active}
                  whileTap={{ scale: 0.94 }}
                  className={`flex min-h-[34px] cursor-pointer items-center gap-1.5 rounded-full border px-2.5 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
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
                </motion.button>
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

        <Field label="Ciudad">
          <Select value={stopSlug} onChange={(e) => setStopSlug(e.target.value)}>
            <option value="">Automática (parada de hoy)</option>
            <option value={GENERAL}>General (sin ciudad)</option>
            {stops.map((s) => (
              <option key={s.slug} value={s.slug}>{s.name}</option>
            ))}
          </Select>
        </Field>

        {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
        <Button type="submit" disabled={save.isPending} className="mt-1">
          {save.isPending ? "Guardando…" : completing ? "Agregar el resto" : "Guardar"}
        </Button>

        {/* Solo en edición de un gasto: atajo para cargar la parte faltante
            sin tocar lo ya cargado. */}
        {editing && isExpense && !completing && (
          <Button type="button" variant="secondary" size="sm" onClick={enterComplete}>
            <PlusCircle size={16} strokeWidth={2} aria-hidden="true" />
            Completar el resto
          </Button>
        )}
      </form>
    </Modal>
  );
}
