import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { errorDetail } from "@/api/client";
import { listCategories } from "@/api/categories";
import { createMovement, updateMovement } from "@/api/movements";
import { listStops, listUsers } from "@/api/users";
import Button from "@/components/ui/Button";
import DateField from "@/components/ui/DateField";
import { Field, Input, Label, Select } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { categoryBg, categoryColor } from "@/lib/chartTheme";
import { categoryIcon } from "@/lib/categoryIcons";
import { capitalize, normalizeAmountInput, sanitizeAmountInput, toInputValue, todayLocal } from "@/lib/format";
import { invalidateLedger } from "@/lib/queryClient";
import { stopForDate } from "@/lib/stops";
import { useMe } from "@/lib/useMe";
import type { Movement, MovementSplit } from "@/types";

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
 *  el pill (left:0 padding-box) compartan origen.
 *
 *  A11y: es opción ÚNICA, así que va como `radiogroup`/`radio` y no con
 *  `aria-pressed` (que describe toggles independientes: un lector anunciaba
 *  "Bruno, pressed / Katia, not pressed" como si se pudieran prender las dos).
 *  Eso obliga al contrato de teclado del patrón: un solo tab-stop (el activo) y
 *  flechas para moverse. */
function Segmented({ options, value, onChange, labelledBy }: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  labelledBy?: string;
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

  // Flechas: mueve la selección al vecino y le lleva el foco (patrón radiogroup).
  function onKeyDown(e: React.KeyboardEvent, i: number) {
    const delta = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1
      : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const next = options[(i + delta + options.length) % options.length];
    onChange(next.value);
    btnRefs.current.get(next.value)?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-labelledby={labelledBy}
      className="relative flex rounded-lg bg-surface-2 p-0.5 ring-1 ring-inset ring-border"
    >
      <span
        ref={pillRef}
        aria-hidden="true"
        className="seg-pill pointer-events-none absolute bottom-0.5 left-0 top-0.5 w-0 rounded-md bg-surface shadow-sm"
      />
      {options.map((o, i) => {
        const active = value === o.value;
        return (
          <button
            key={o.value}
            ref={(el) => { if (el) btnRefs.current.set(o.value, el); }}
            type="button"
            role="radio"
            aria-checked={active}
            // Un solo tab-stop por grupo: Tab entra y sale, las flechas navegan.
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`relative z-10 min-h-[36px] flex-1 cursor-pointer rounded-md px-2 text-note font-semibold transition-colors focus-ring ${
              active ? "text-ink" : "text-ink-3 hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
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
  // Mismo staleTime que el resto de los consumidores de ["stops"]: con Infinity
  // acá, quién montara primero decidía si el itinerario se refrescaba o no.
  const { data: stops = [] } = useQuery({ queryKey: ["stops"], queryFn: listStops, staleTime: 60_000 });
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
  // Cashback: valor + unidad (% por default; tocar el botón lo pasa a monto fijo
  // en la moneda del gasto). Vacío = sin cashback.
  const [cashbackValue, setCashbackValue] = useState(toInputValue(editing?.cashback_value));
  const [cashbackKind, setCashbackKind] = useState<"pct" | "amount">(
    editing?.cashback_kind === "amount" ? "amount" : "pct",
  );
  const [err, setErr] = useState<string | null>(null);
  // Error de validación del monto, aparte del de red: se muestra junto al campo.
  const [amountErr, setAmountErr] = useState<string | null>(null);
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

  const save = useMutation({
    mutationFn: async () => {
      const stop = stops.find((s) => s.slug === stopSlug);
      const isEdit = Boolean(editing);
      // Al editar se manda SOLO lo que cambió: el backend usa `model_fields_set`
      // para decidir si re-precia el FX y si re-deriva el status, así que
      // re-mandar el body entero confirmaba gastos `awaiting` y re-valuaba al TC
      // de hoy (en ARS, el MEP vivo) con solo corregir una descripción.
      const body: Partial<Movement> & { general?: boolean } = {};
      const put = <K extends keyof Movement>(key: K, value: Movement[K]) => {
        if (!isEdit || editing![key] !== value) body[key] = value;
      };

      put("amount", normalizeAmountInput(amount));
      put("currency", currency);
      put("description", description || null);
      if (paidBy) put("paid_by", Number(paidBy));

      if (isExpense) {
        // Fecha de pago: mandarla solo si está seteada; al editar, vaciarla
        // vuelve explícitamente a "día de carga" (null).
        if (paymentDate) put("payment_date", paymentDate);
        else if (isEdit && editing?.payment_date) body.payment_date = null;

        // Categoría y división solo aplican a gastos.
        put("category_id", categoryId ? Number(categoryId) : null);
        put("split", split);

        // Cashback: mandar kind+value si hay un valor > 0; al editar, vaciarlo
        // manda null explícito para SACARLO — pero solo si antes tenía.
        const cbv = normalizeAmountInput(cashbackValue).trim();
        if (cbv && Number(cbv) > 0) {
          put("cashback_kind", cashbackKind);
          put("cashback_value", cbv);
        } else if (isEdit && editing?.cashback_kind) {
          body.cashback_kind = null;
          body.cashback_value = null;
        }

        // La ciudad la deriva siempre el backend del stop_slug (nunca texto libre).
        if (stopSlug === GENERAL) {
          body.stop_slug = null;
          body.general = true;
        } else if (stop) {
          put("stop_slug", stop.slug);
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
      invalidateLedger(qc);
      toast("success", editing ? "Cambios guardados" : "Gasto guardado");
      onClose();
    },
    onError: (e) => setErr(errorDetail(e, "No se pudo guardar. Revisá el monto.")),
  });

  function submit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    setAmountErr(null);
    if (!amount || Number.isNaN(Number(normalizeAmountInput(amount)))) {
      // El mensaje va pegado al campo y el foco vuelve ahí: el sheet puede estar
      // scrolleado y un error al pie no se ve (el Monto está arriba de todo).
      setAmountErr("Ingresá un monto válido.");
      firstRef.current?.focus();
      return;
    }
    save.mutate();
  }

  const title = editing ? "Editar movimiento" : "Agregar movimiento";

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-2">
        {/* El monto manda: input display grande + moneda al lado. */}
        <div className={`rounded-xl border bg-surface-2/50 p-2.5 ${amountErr ? "border-danger" : "border-border"}`}>
          <Label>Monto</Label>
          <div className="mt-1 flex items-center gap-3">
            <input
              ref={firstRef}
              inputMode="decimal"
              placeholder="0,00"
              aria-label="Monto"
              aria-invalid={amountErr ? true : undefined}
              aria-describedby={amountErr ? "amount-error" : undefined}
              value={amount}
              onChange={(e) => { setAmount(sanitizeAmountInput(e.target.value)); setAmountErr(null); }}
              className="w-full min-w-0 bg-transparent font-display text-3xl leading-none tracking-display text-ink outline-none font-tabular placeholder:text-ink-faint"
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
          {amountErr && (
            <p id="amount-error" role="alert" className="mt-1.5 text-note font-semibold text-danger">
              {amountErr}
            </p>
          )}
        </div>

        {/* Cashback opcional: un solo campo con la unidad togglable (% ↔ moneda)
            para no ocupar más espacio. Vacío = sin cashback. */}
        {isExpense && (
          <Field label="Cashback" hint="Opcional · tocá la unidad para monto fijo">
            <div className="flex items-center gap-2">
              <Input
                inputMode="decimal"
                placeholder="0"
                aria-label="Cashback"
                value={cashbackValue}
                onChange={(e) => setCashbackValue(sanitizeAmountInput(e.target.value))}
              />
              <button
                type="button"
                onClick={() => setCashbackKind((k) => (k === "pct" ? "amount" : "pct"))}
                aria-label={`Unidad del cashback: ${cashbackKind === "pct" ? "porcentaje" : currency}`}
                className="flex min-h-[44px] w-16 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-border bg-surface-2 text-base font-semibold text-ink transition-colors hover:bg-surface focus-ring"
              >
                {cashbackKind === "pct" ? "%" : currency}
              </button>
            </div>
          </Field>
        )}

        <Field label="Descripción">
          <Input placeholder="cena, taxi, museo…"
                 value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>

        {/* Categoría: chips con ícono, un toque; tocar de nuevo deselecciona.
            Los saldos no llevan categoría. */}
        {isExpense && (
        <div className="flex flex-col gap-1">
          <Label id="cat-label">Categoría</Label>
          {/* `group` + aria-labelledby: los chips se apagan tocándolos de nuevo,
              así que son toggles (aria-pressed), no radios — pero el grupo
              necesita nombre para que se entienda qué se está eligiendo. */}
          <div role="group" aria-labelledby="cat-label" className="flex flex-wrap gap-1">
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
                  className={`flex min-h-[32px] cursor-pointer items-center gap-1.5 rounded-full border px-2 text-note font-semibold transition-colors focus-ring ${
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
          <Label id="payer-label">{isExpense ? "Pagó" : "Pagó (transferencia)"}</Label>
          <Segmented
            labelledBy="payer-label"
            options={users.map((u) => ({ value: String(u.id), label: capitalize(u.username) }))}
            value={paidBy}
            onChange={setPaidBy}
          />
        </div>

        {/* División y ciudad no aplican a saldos (siempre sin ciudad). */}
        {isExpense && (
          <div className="flex flex-col gap-1">
            <Label id="split-label">División</Label>
            <Segmented
              labelledBy="split-label"
              options={SPLITS}
              value={split}
              onChange={(v) => setSplit(v as MovementSplit)}
            />
          </div>
        )}

        {isExpense && (
          <Field label="Ciudad">
            <Select value={stopSlug} onChange={(e) => setStopSlug(e.target.value)}>
              <option value="">Automática (parada de hoy)</option>
              <option value={GENERAL}>General (sin ciudad)</option>
              {/* /stops no devuelve las archivadas: sin esta opción el <select>
                  de un gasto viejo quedaba en blanco (selectedIndex -1) y el
                  usuario, al tocarlo, le reasignaba la ciudad sin querer. */}
              {editing?.stop_slug && !stops.some((s) => s.slug === editing.stop_slug) && (
                <option value={editing.stop_slug}>
                  {editing.city_name ?? editing.stop_slug} (archivada)
                </option>
              )}
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
            <DateField
              value={paymentDate}
              placeholder="Hoy"
              aria-label="Fecha de pago"
              onChange={setPaymentDate}
            />
          </Field>
        )}

        {err && <p role="alert" className="text-sm font-semibold text-danger">{err}</p>}
        <Button type="submit" disabled={save.isPending} className="mt-1">
          {save.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </form>
    </Modal>
  );
}
