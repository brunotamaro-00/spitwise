import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";
import { formatDayHeader, todayLocal } from "@/lib/format";
import { stopForDate } from "@/lib/stops";
import type { Stop } from "@/types";

const WEEKDAYS = ["L", "M", "M", "J", "V", "S", "D"];
const MONTHS = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];
const POPOVER_W = 320; // ancho objetivo del calendario
const POPOVER_H = 380; // alto estimado para decidir arriba/abajo

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
function iso(y: number, m: number, d: number): string {
  return `${y}-${pad(m + 1)}-${pad(d)}`;
}
type Pos = { left: number; width: number; top?: number; bottom?: number };

/** Campo de fecha con calendario propio (responsive). Se abre al tocar cualquier
 *  parte del campo. El calendario flota como popover (portal al body) anclado al
 *  campo, abriendo hacia arriba o abajo según el espacio, para no cortarse ni
 *  empujar el contenido del modal. Marca sutilmente la bandera del itinerario en
 *  cada día para ubicar rápido a qué ciudad corresponde una fecha. */
export default function DatePicker({
  value,
  onChange,
  stops = [],
}: {
  value: string;
  onChange: (v: string) => void;
  stops?: Stop[];
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const initial = value || todayLocal();
  const [view, setView] = useState(() => {
    const [y, m] = initial.split("-").map(Number);
    return { y, m: (m || 1) - 1 };
  });

  const derived = value ? stopForDate(stops, value) : undefined;

  const place = () => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = Math.min(POPOVER_W, vw - 16);
    const left = Math.max(8, Math.min(r.left, vw - width - 8));
    const spaceBelow = vh - r.bottom;
    if (spaceBelow < POPOVER_H && r.top > spaceBelow) {
      setPos({ left, width, bottom: vh - r.top + 6 });
    } else {
      setPos({ left, width, top: r.bottom + 6 });
    }
  };

  useLayoutEffect(() => {
    if (open) place();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onScrollResize = () => place();
    window.addEventListener("resize", onScrollResize);
    window.addEventListener("scroll", onScrollResize, true);
    return () => {
      window.removeEventListener("resize", onScrollResize);
      window.removeEventListener("scroll", onScrollResize, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const cells = useMemo(() => {
    const first = new Date(view.y, view.m, 1);
    const startDow = (first.getDay() + 6) % 7; // lunes = 0
    const daysInMonth = new Date(view.y, view.m + 1, 0).getDate();
    const out: { date: string; inMonth: boolean; day: number }[] = [];
    const prevDays = new Date(view.y, view.m, 0).getDate();
    for (let i = startDow - 1; i >= 0; i--) {
      const d = prevDays - i;
      const dt = new Date(view.y, view.m - 1, d);
      out.push({ date: iso(dt.getFullYear(), dt.getMonth(), d), inMonth: false, day: d });
    }
    for (let d = 1; d <= daysInMonth; d++) {
      out.push({ date: iso(view.y, view.m, d), inMonth: true, day: d });
    }
    let next = 1;
    while (out.length % 7 !== 0) {
      const dt = new Date(view.y, view.m + 1, next);
      out.push({ date: iso(dt.getFullYear(), dt.getMonth(), next), inMonth: false, day: next });
      next++;
    }
    return out;
  }, [view]);

  function pick(date: string) {
    onChange(date);
    setOpen(false);
  }
  function shiftMonth(delta: number) {
    setView((v) => {
      const dt = new Date(v.y, v.m + delta, 1);
      return { y: dt.getFullYear(), m: dt.getMonth() };
    });
  }

  const today = todayLocal();

  return (
    <div>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex min-h-[44px] w-full items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 text-[15px] font-medium text-ink transition-colors hover:bg-surface-2 focus:border-brick focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/30"
      >
        <span className="flex items-center gap-2">
          {value ? capitalizeDay(formatDayHeader(value)) : "Elegir fecha"}
          {derived && (
            <span className="text-ink-faint" aria-hidden="true">
              · {derived.country_flag} {derived.name}
            </span>
          )}
        </span>
        <CalendarDays size={18} strokeWidth={1.75} className="shrink-0 text-ink-3" aria-hidden="true" />
      </button>

      {open && pos &&
        createPortal(
          <>
            {/* Backdrop transparente: cerrar al tocar afuera (sin cerrar el modal). */}
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <div
              role="dialog"
              aria-label="Elegir fecha"
              className="fixed z-50 animate-fade-in rounded-xl border border-border bg-surface p-3 soft-pop"
              style={{ left: pos.left, width: pos.width, top: pos.top, bottom: pos.bottom }}
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="font-semibold capitalize text-ink">
                  {MONTHS[view.m]} {view.y}
                </span>
                <div className="flex items-center gap-1">
                  <IconBtn label="Mes anterior" onClick={() => shiftMonth(-1)}>
                    <ChevronLeft size={18} strokeWidth={2} aria-hidden="true" />
                  </IconBtn>
                  <IconBtn label="Mes siguiente" onClick={() => shiftMonth(1)}>
                    <ChevronRight size={18} strokeWidth={2} aria-hidden="true" />
                  </IconBtn>
                </div>
              </div>

              <div className="grid grid-cols-7 gap-0.5">
                {WEEKDAYS.map((w, i) => (
                  <div key={i} className="pb-1 text-center text-[11px] font-semibold text-ink-3">
                    {w}
                  </div>
                ))}
                {cells.map((c) => {
                  const stop = stopForDate(stops, c.date);
                  const selected = c.date === value;
                  const isToday = c.date === today;
                  return (
                    <button
                      key={c.date}
                      type="button"
                      onClick={() => pick(c.date)}
                      aria-label={c.date}
                      aria-pressed={selected}
                      className={cn(
                        "relative flex aspect-square flex-col items-center justify-center rounded-lg text-sm font-medium transition-colors",
                        selected
                          ? "bg-brick text-white"
                          : c.inMonth
                            ? "text-ink hover:bg-surface-2"
                            : "text-ink-faint hover:bg-surface-2",
                        !selected && isToday && "ring-1 ring-brick",
                      )}
                    >
                      <span className="font-tabular leading-none">{c.day}</span>
                      {stop?.country_flag && (
                        <span
                          className={cn("mt-0.5 text-[9px] leading-none", selected ? "opacity-90" : "opacity-70")}
                          aria-hidden="true"
                        >
                          {stop.country_flag}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="mt-2 flex items-center justify-between">
                <span className="truncate text-xs text-ink-3">
                  {derived ? (
                    <>Itinerario: <span className="font-semibold text-ink-2">{derived.country_flag} {derived.name}</span></>
                  ) : (
                    "Sin ciudad en el itinerario para esta fecha"
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => pick(today)}
                  className="shrink-0 cursor-pointer rounded-md px-2 py-1 text-xs font-semibold text-brick hover:bg-brick-bg"
                >
                  Hoy
                </button>
              </div>
            </div>
          </>,
          document.body,
        )}
    </div>
  );
}

function IconBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/30"
    >
      {children}
    </button>
  );
}

function capitalizeDay(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
