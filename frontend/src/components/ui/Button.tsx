import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "sm";

const base =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-semibold transition-[background-color,transform,box-shadow,color] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<Variant, string> = {
  primary: "bg-brick text-white hover:bg-brick-hover active:bg-brick-press",
  secondary: "border border-border bg-surface text-ink hover:bg-surface-2",
  ghost: "text-ink-3 hover:bg-surface-2 hover:text-ink",
  danger: "border border-danger/30 bg-danger-bg text-danger hover:bg-danger/10",
};

const sizes: Record<Size, string> = {
  md: "min-h-[44px] px-4 text-[15px]",
  sm: "min-h-[36px] px-3 text-sm",
};

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
