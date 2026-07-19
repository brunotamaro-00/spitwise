import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusCircle } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

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

/** Grupo de botones exclusivos (segmented control) con pill deslizante: el
 *  pill blanco se desliza entre opciones (patrón tabs-sliding). JS mide
 *  offsetLeft/offsetWidth del botón activo y los escribe inline; el CSS
 *  (.seg-pill) tweenea. En primer paint y resize se posiciona sin animar
 *  (snap). El borde va como ring-inset para que offsetLeft (border-box) y
 *  el pill (left:0 padding-box) compartan origen. */
function Segmented({ options, value, onChange }: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  const pillRef = useRef<HTMLSpanElement>(null);
  const btnRefs = useRef(new Map<string, HTMLButtonElement>());
  const mounted = useRef(false);

  function place(animate: boolean) {
    const pill = pillRef.current;
    const btn = btnRefs.current.get(value);
    if (!pill || !btn) return;
    const apply = () => {
      pill.style.transform = `translateX(${btn.offsetLeft}px)`;
      pill.style.width = `${btn.offsetWidth}px`;
    };
    if (animate) {
      apply();
    } else {
      const prev = pill.style.transition;
      pill.style.transition = "none";
      apply();
      void pill.offsetWidth; // fuerza reflow para que el próximo cambio anime
      pill.style.transition = prev;
    }
  }

  // Snap al montar; anima en cambios de `value` posteriores (click o externo).
  useLayoutEffect(() => {
    place(mounted.current);
    mounted.current = true;
  }, [value]);

  // Reposicionar sin animar en resize (usa el `value` vigente vía ref indirecto).
  const placeRef = useRef(place);
  placeRef.current = place;
  useEffect(() => {
    const onResize = () => placeRef.current(false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className="relative flex rounded-lg bg-surface-2 p-0.5 ring-1 ring-inset ring-border">
      <span
        ref={pillRef}
        aria-hidden="true"
        className="seg-pill pointer-events-none absolute bottom-0.5 left-0 top-0.5 w-0 rounded-md bg-surface shadow-sm"
      />
      {options.map((o) => (
        <button
          key={o.value}
          ref={(el) => { if (el) btnRefs.current.set(o.value, el); }}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`relative z-10 min-h-[36px] flex-1 cursor-pointer rounded-md px-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
            value === o.value ? "text-ink" : "text-ink-3 hover:text-ink"
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
  const [paymentDate, setPaymentDate] = useState(editing?.payment_date ?? "");
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

  // preventScroll: en iOS el foco abre el teclado pero NO scrollea el sheet,
  // así el monto queda visible arriba en vez de irse fuera de cuadro.
  useEffect(() => { firstRef.current?.focus({ preventScroll: true }); }, []);

  // Pasa a modo "completar": clona ciudad/categoría/fecha/moneda del gasto y
  // deja el monto vacío + pagador en mí, listo para cargar el resto.
  function enterComplete() {
    setCompleting(true);
    setAmount("");
    setErr(null);
    if (me) setPaidBy(String(me.id));
    requestAnimationFrame(() => firstRef.current?.focus({ preventScroll: true }));
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
      };
      if (paidBy) body.paid_by = Number(paidBy);

      if (isExpense) {
        // Fecha de pago: mandarla solo si está seteada; al editar, vaciarla
        // vuelve explícitamente a "día de carga" (null).
        if (paymentDate) body.payment_date = paymentDate;
        else if (isEdit && editing?.payment_date) body.payment_date = null;

        // Categoría y división solo aplican a gastos.
        body.category_id = categoryId ? Number(categoryId) : null;
        body.split = split;

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
      } else {
        // Los saldos son SIEMPRE sin ciudad, sin categoría y sin división.
        body.stop_slug = null;
        body.general = true;
      }

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
      <form onSubmit={submit} className="flex flex-col gap-2">
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
        <div className="rounded-xl border border-border bg-surface-2/50 p-2.5">
          <Label>Monto</Label>
          <div className="mt-1 flex items-center gap-3">
            <input
              ref={firstRef}
              inputMode="decimal"
              placeholder="0,00"
              aria-label="Monto"
              value={amount}
              onChange={(e) => setAmount(sanitizeAmountInput(e.target.value))}
              className="w-full min-w-0 bg-transparent font-display text-3xl leading-none tracking-[-0.02em] text-ink outline-none font-tabular placeholder:text-ink-faint"
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

        {/* Categoría: chips con ícono, un toque; tocar de nuevo deselecciona.
            Los saldos no llevan categoría. */}
        {isExpense && (
        <div className="flex flex-col gap-1">
          <Label>Categoría</Label>
          <div className="flex flex-wrap gap-1">
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
                  className={`flex min-h-[32px] cursor-pointer items-center gap-1.5 rounded-full border px-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 ${
                    active ? "" : "border-border bg-surface text-ink-2 hover:bg-surface-2"
                  }`}
                  style={active ? {
                    background: categoryBg(c.name),
                    color: categoryColor(c.name),
                    borderColor: categoryColor(c.name),
                  } : undefined}
                >
                  <Icon size={13} strokeWidth={2} aria-hidden="true" />
                  {c.name}
                </motion.button>
              );
            })}
          </div>
        </div>
        )}

        <div className="flex flex-col gap-1">
          <Label>{isExpense ? "Pagó" : "Pagó (transferencia)"}</Label>
          <Segmented
            options={users.map((u) => ({ value: String(u.id), label: capitalize(u.username) }))}
            value={paidBy}
            onChange={setPaidBy}
          />
        </div>

        {/* División y ciudad no aplican a saldos (siempre sin ciudad). */}
        {isExpense && (
          <div className="flex flex-col gap-1">
            <Label>División</Label>
            <Segmented options={SPLITS} value={split} onChange={setSplit} />
          </div>
        )}

        {isExpense && (
          <Field label="Ciudad">
            <Select value={stopSlug} onChange={(e) => setStopSlug(e.target.value)}>
              <option value="">Automática (parada de hoy)</option>
              <option value={GENERAL}>General (sin ciudad)</option>
              {stops.map((s) => (
                <option key={s.slug} value={s.slug}>{s.name}</option>
              ))}
            </Select>
          </Field>
        )}

        {/* Fecha de pago opcional: vacía = hoy. Futura => queda pendiente con
            TC provisorio (se ajusta solo al llegar el día); pasada => TC
            histórico de esa fecha. */}
        {isExpense && (
          <Field label="Fecha de pago" hint="Vacía = hoy · futura queda pendiente">
            <Input
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
            />
          </Field>
        )}

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
