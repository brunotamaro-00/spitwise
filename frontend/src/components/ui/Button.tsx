import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "sm";

const base =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-semibold transition-[background-color,transform,box-shadow,color] active:scale-[0.98] focus-ring disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<Variant, string> = {
  primary: "bg-brick text-white hover:bg-brick-hover active:bg-brick-press",
  secondary: "border border-border bg-surface text-ink hover:bg-surface-2",
  ghost: "text-ink-3 hover:bg-surface-2 hover:text-ink",
  danger: "border border-danger/30 bg-danger-bg text-danger hover:bg-danger/10",
};

const sizes: Record<Size, string> = {
  md: "min-h-[44px] px-4 text-entry",
  sm: "min-h-[36px] px-3 text-sm",
};

/** Apariencia de botón para elementos que no son `<button>` (links con rol de
 *  CTA). Evita reimplementar las variantes a mano en el call site. */
export function buttonClasses({
  variant = "primary",
  size = "md",
  className,
}: { variant?: Variant; size?: Size; className?: string } = {}) {
  return cn(base, variants[variant], sizes[size], className);
}

export default function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button className={cn(base, variants[variant], sizes[size], className)} {...rest}>
      {children}
    </button>
  );
}
