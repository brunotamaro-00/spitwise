import { forwardRef } from "react";

import { cn } from "@/lib/cn";

/** Micro-label sobrio (sentence case, sin uppercase/tracking). */
export function Label({ className, children, ...rest }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <span className={cn("text-xs font-medium text-ink-3", className)} {...rest}>
      {children}
    </span>
  );
}

// text-base (16px) es deliberado: por debajo de 16px iOS Safari hace zoom
// automático al enfocar el control. min-w-0 evita que los type="date" nativos
// (ancho intrínseco) desborden su columna en un grid.
const control =
  "min-h-[44px] w-full min-w-0 rounded-lg border border-border bg-surface px-3 text-base font-medium text-ink placeholder:text-ink-faint focus:border-brick focus:outline-none focus-visible:ring-2 focus-visible:ring-brick/30";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(control, className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select ref={ref} className={cn(control, "cursor-pointer", className)} {...rest}>
        {children}
      </select>
    );
  },
);

/** Campo etiquetado: <Label> + control en columna. */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </label>
  );
}
