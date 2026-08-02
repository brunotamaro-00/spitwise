import Badge from "@/components/ui/Badge";

/** Pill informativa "+40% vs promedio". Ámbar por encima del promedio del
 *  viaje, teal por debajo, neutra en ±10%. Nunca roja: es contexto, no alarma.
 *  Sin delta (ciudades futuras) no renderiza nada.
 *
 *  `compact` deja solo "+40%" (sin "vs promedio") para embeberlo donde el
 *  contexto ya lo da — p.ej. junto al label "$/día" del KPI. */
export default function DeltaBadge({
  pct,
  compact = false,
}: {
  pct: number | null | undefined;
  compact?: boolean;
}) {
  if (pct == null || Number.isNaN(pct)) return null;
  const rounded = Math.round(pct);
  const tone = Math.abs(pct) < 10 ? "neutral" : pct > 0 ? "amber" : "teal";
  const sign = rounded > 0 ? "+" : "";
  return (
    <Badge tone={tone} tabular>
      {sign}
      {rounded}%{compact ? "" : " vs promedio"}
    </Badge>
  );
}
