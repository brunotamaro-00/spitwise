import { CalendarRange, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { formatShortDate } from "@/lib/format";

const WEEKDAYS = ["lu", "ma", "mi", "ju", "vi", "sá", "do"];
const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

/** Date local → "yyyy-mm-dd" sin pasar por UTC (evita el corrimiento de TZ). */
function iso(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function todayIso(): string {
  const t = new Date();
  return iso(t.getFullYear(), t.getMonth(), t.getDate());
}

/** Rango de fechas en UNA sola box: el trigger muestra el rango elegido (o el
 *  placeholder) y expande un calendario inline. Dos toques arman el rango
 *  (primer toque = inicio, segundo = fin; dos veces el mismo día = un solo
 *  día; un fin anterior al inicio los intercambia). No hay picker nativo de
 *  rango en la web — el `type="date"` del sistema es siempre una fecha suelta,
 *  así que el calendario es propio, con los tokens de la app. */
export default function DateRangeField({ from, to, onChange, placeholder = "Elegir fechas" }: {
  from: string;
  to: string;
  onChange: (r: { from: string; to: string }) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const today = todayIso();
  const anchor = from || today;
  const [view, setView] = useState(() => {
    const [y, m] = anchor.split("-").map(Number);
    return { y, m: m - 1 };
  });

  const label =
    from && to
      ? from === to
        ? formatShortDate(from)
        : `${formatShortDate(from)} – ${formatShortDate(to)}`
      : from
        ? `desde ${formatShortDate(from)}`
        : null;

  function toggle() {
    if (!open) {
      const [y, m] = (from || today).split("-").map(Number);
      setView({ y, m: m - 1 });
    }
    setOpen(!open);
  }

  function pick(day: string) {
    // Sin inicio (o rango ya cerrado): este toque arranca una selección nueva.
    // Y con inicio pendiente, un día ANTERIOR no arma rango hacia atrás: pasa a
    // ser el nuevo día elegido, y el rango se sigue armando hacia adelante.
    if (!from || to || day < from) {
      onChange({ from: day, to: "" });
      return;
    }
    // Mismo día o posterior: cierra el rango (mismo día = un solo día). El
    // popup queda abierto para revisar; se confirma con "Aplicar" o tocando afuera.
    onChange({ from, to: day });
  }

  function shiftMonth(delta: number) {
    setView((v) => {
      const m = v.m + delta;
      return { y: v.y + Math.floor(m / 12), m: ((m % 12) + 12) % 12 };
    });
  }

  // Lunes = primera columna: getDay() es 0=domingo.
  const leading = (new Date(view.y, view.m, 1).getDay() + 6) % 7;
  const daysInMonth = new Date(view.y, view.m + 1, 0).getDate();
  const end = to || from; // con inicio pendiente, el inicio también es "fin"
  const single = !to || from === to;

  return (
    <div className="relative">
      <div className="relative rounded-lg">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className={`flex min-h-[44px] w-full min-w-0 cursor-pointer items-center gap-2 rounded-lg border bg-surface px-3 text-left text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/30 ${
            open ? "border-brick" : "border-border"
          }`}
        >
          <CalendarRange size={15} strokeWidth={2} className="shrink-0 text-ink-faint" aria-hidden="true" />
          {label ? (
            <span className="truncate font-tabular text-ink">{label}</span>
          ) : (
            <span className="truncate text-ink-faint">{placeholder}</span>
          )}
        </button>
        {from && (
          <button
            type="button"
            aria-label="Borrar fechas"
            onClick={() => onChange({ from: "", to: "" })}
            className="animate-fade-in absolute inset-y-0 right-0 z-10 flex w-11 cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
          >
            <X size={14} strokeWidth={2} aria-hidden="true" />
          </button>
        )}
      </div>

      {open && (
        <>
          {/* Capa que cierra el popover tocando afuera. `fixed` acá se ancla al
              panel del sheet (ancestro con transform), que es justo lo que
              queremos cubrir. */}
          <button
            type="button"
            aria-label="Cerrar calendario"
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-10 cursor-default"
          />
          {/* Popover hacia ARRIBA del trigger: absoluto (no ocupa flujo, no
              agrega scroll al sheet) y por encima del contenido. */}
          <div className="animate-rise-in absolute bottom-full left-0 right-0 z-20 mb-2 rounded-xl border border-border bg-surface p-3 soft-pop">
          <div className="flex items-center justify-between">
            <button
              type="button"
              aria-label="Mes anterior"
              onClick={() => shiftMonth(-1)}
              className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            >
              <ChevronLeft size={17} strokeWidth={2} aria-hidden="true" />
            </button>
            <span aria-live="polite" className="text-sm font-bold text-ink">
              {MONTHS[view.m]} {view.y}
            </span>
            <button
              type="button"
              aria-label="Mes siguiente"
              onClick={() => shiftMonth(1)}
              className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            >
              <ChevronRight size={17} strokeWidth={2} aria-hidden="true" />
            </button>
          </div>

          <div className="mt-2 grid grid-cols-7 text-center text-[11px] font-semibold text-ink-faint">
            {WEEKDAYS.map((w) => <span key={w}>{w}</span>)}
          </div>

          <div className="mt-1 grid grid-cols-7 gap-y-0.5">
            {Array.from({ length: leading }, (_, i) => <span key={`b${i}`} />)}
            {Array.from({ length: daysInMonth }, (_, i) => {
              const day = iso(view.y, view.m, i + 1);
              const isStart = day === from;
              const isEnd = day === end;
              const inRange = Boolean(from && to && day > from && day < to);
              let cls = "rounded-lg text-ink-2 hover:bg-surface-2";
              if (isStart || isEnd) {
                cls = `bg-brick font-bold text-white ${single ? "rounded-lg" : isStart ? "rounded-l-lg" : "rounded-r-lg"}`;
              } else if (inRange) {
                cls = "rounded-none bg-brick-bg font-semibold text-brick";
              } else if (day === today) {
                cls = "rounded-lg font-bold text-brick hover:bg-surface-2";
              }
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => pick(day)}
                  aria-label={`${i + 1} de ${MONTHS[view.m].toLowerCase()} de ${view.y}`}
                  aria-pressed={isStart || isEnd || inRange}
                  className={`flex h-10 cursor-pointer items-center justify-center text-sm font-tabular transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brick/40 ${cls}`}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>

          {from && !to && (
            <p className="mt-2 text-center text-xs text-ink-3">
              Tocá el último día · el mismo día para un solo día
            </p>
          )}
          <Button type="button" size="sm" className="mt-2 w-full" onClick={() => setOpen(false)}>
            Aplicar
          </Button>
          </div>
        </>
      )}
    </div>
  );
}
