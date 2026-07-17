/** Pill informativa "+40% vs promedio". Ámbar por encima del promedio del
 *  viaje, teal por debajo, neutra en ±10%. Nunca roja: es contexto, no alarma.
 *  Sin delta (ciudades futuras) no renderiza nada. */
export default function DeltaBadge({ pct }: { pct: number | null | undefined }) {
  if (pct == null || Number.isNaN(pct)) return null;
  const rounded = Math.round(pct);
  const tone =
    Math.abs(pct) < 10
      ? "bg-surface-2 text-ink-3"
      : pct > 0
        ? "bg-accent-amber-bg text-accent-amber"
        : "bg-accent-teal-bg text-accent-teal";
  const sign = rounded > 0 ? "+" : "";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 font-tabular text-[11px] font-bold ${tone}`}
    >
      {sign}
      {rounded}% vs promedio
    </span>
  );
}
