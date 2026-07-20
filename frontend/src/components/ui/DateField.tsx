import { Calendar, X } from "lucide-react";

import { cn } from "@/lib/cn";

/** "2026-08-03" → "03/08/2026" (sin pasar por Date: evita el corrimiento de TZ). */
function display(value: string): string {
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

/** Campo de fecha con el picker NATIVO del sistema. El `<input type="date">`
 *  de iOS no muestra placeholder cuando está vacío (queda una caja muda) y
 *  desborda su ancho intrínseco, así que acá lo dibujamos nosotros: una capa
 *  visible con ícono + fecha formateada (o placeholder) y el input real
 *  invisible encima ocupando todo el control — el tap sigue abriendo la rueda
 *  de iOS / el calendario del browser. Con valor aparece una X para volver a
 *  vacío (que cada pantalla interpreta: "cualquiera", "hoy", etc.). */
export default function DateField({
  value, onChange, placeholder = "Elegir fecha", min, max, className, "aria-label": ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  min?: string;
  max?: string;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <div
      className={cn(
        "relative rounded-lg focus-within:ring-2 focus-within:ring-brick/30",
        className,
      )}
    >
      <div
        aria-hidden="true"
        className="flex min-h-[44px] w-full min-w-0 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-base font-medium"
      >
        <Calendar size={15} strokeWidth={2} className="shrink-0 text-ink-faint" />
        {value ? (
          <span className="truncate font-tabular text-ink">{display(value)}</span>
        ) : (
          <span className="truncate text-ink-faint">{placeholder}</span>
        )}
      </div>
      {/* El input real, transparente, cubre todo el control. El indicador de
          picker de WebKit se expande al 100% para que cualquier click (no solo
          el iconito) abra el calendario también en desktop. */}
      <input
        type="date"
        value={value}
        min={min}
        max={max}
        aria-label={ariaLabel}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0 [&::-webkit-calendar-picker-indicator]:absolute [&::-webkit-calendar-picker-indicator]:inset-0 [&::-webkit-calendar-picker-indicator]:h-full [&::-webkit-calendar-picker-indicator]:w-full [&::-webkit-calendar-picker-indicator]:cursor-pointer"
      />
      {value && (
        <button
          type="button"
          aria-label="Borrar fecha"
          onClick={() => onChange("")}
          className="animate-fade-in absolute inset-y-0 right-0 z-10 flex w-11 cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
        >
          <X size={14} strokeWidth={2} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
