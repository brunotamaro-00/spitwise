import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatAmount, formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, FALLBACK_SERIES, TICK } from "@/lib/chartTheme";
import DeltaBadge from "@/components/DeltaBadge";
import type { CityPace, TripBlock } from "@/types";

type Row = {
  name: string;
  perDay: number;
  perDayStr: string;
  nights: number;
  status: CityPace["status"];
  delta: number | null;
};

function PaceTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="text-sm font-semibold text-ink">{r.name}</div>
      <div className="mt-0.5 font-tabular text-sm text-ink-2">
        {formatUsd(r.perDayStr)}/día · {r.nights} noche{r.nights === 1 ? "" : "s"}
      </div>
      <div className="mt-1">
        {r.status === "future" ? (
          <span className="text-[11px] font-medium text-ink-3">reservado</span>
        ) : (
          <DeltaBadge pct={r.delta} />
        )}
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
}

/** Tick del eje en <text> plano: el <Text> de Recharts envuelve por palabra
 *  cuando le pasás width, y "Edimburgo (tránsito)" se partía en dos renglones
 *  desalineados del resto. Acá el corte es siempre con "…" y en un renglón. */
function CityTick({
  x,
  y,
  payload,
  fontSize,
}: {
  x?: number;
  y?: number;
  payload?: { value: string };
  fontSize: number;
}) {
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fill={TICK.fill} fontSize={fontSize}>
      {truncate(String(payload?.value ?? ""), 14)}
    </text>
  );
}

/** $/día por ciudad en orden de itinerario, comparable de verdad: alojamiento
 *  prorrateado por noches. Ciudades futuras (solo reservas) van apagadas y sin
 *  delta; la línea punteada es el promedio del viaje. El estado nunca se
 *  codifica solo con color: lo repiten el tooltip ("reservado") y el sufijo
 *  "· hoy" de la parada en curso. */
export default function CityPaceChart({
  cities,
  trip,
  title = "Ritmo por ciudad",
}: {
  cities: CityPace[];
  trip: TripBlock;
  title?: string;
}) {
  const rows: Row[] = cities
    .filter((c) => c.per_day_usd != null && (c.movement_count > 0 || c.status !== "future"))
    .map((c) => ({
      name: c.status === "current" ? `${c.city_name} · hoy` : c.city_name,
      perDay: parseMoney(c.per_day_usd!),
      perDayStr: c.per_day_usd!,
      nights: c.nights,
      status: c.status,
      delta: c.delta_vs_trip_pct,
    }))
    .filter((r) => r.perDay > 0);
  if (rows.length === 0) return null;

  const avg = trip.avg_per_day_usd ? parseMoney(trip.avg_per_day_usd) : 0;
  const showAvg = trip.status !== "not_started" && avg > 0;
  const many = rows.length > 5;
  // Dominio explícito y compartido: con XAxis oculto, Recharts le inventaba a
  // las barras un dominio distinto del que usaba el ReferenceLine (barras
  // diminutas, promedio fuera de escala). Fijarlo alinea barras y línea.
  const domainMax = Math.max(...rows.map((r) => r.perDay), showAvg ? avg : 0) * 1.02;

  return (
    <Card className="flex h-full flex-col p-5">
      <div className="mb-4 flex items-baseline justify-between gap-2">
        <Label>{title} ($/día)</Label>
        {showAvg && (
          <span className="text-[11px] font-medium text-ink-3">
            promedio <span className="font-tabular font-semibold">{formatUsd(trip.avg_per_day_usd!)}</span>
          </span>
        )}
      </div>
      {/* relative + hijo absoluto: el 100% del ResponsiveContainer necesita una
          altura definida; min-height sola no la da y el chart colapsa a 0. */}
      <div
        className="relative flex-1"
        style={{ minHeight: Math.max(rows.length * 30, 200) }}
        role="img"
        aria-label={`${title}: promedio por día por ciudad, en orden de itinerario`}
      >
        <div className="absolute inset-0 flex items-center">
          <div className="h-full w-full" style={{ maxHeight: rows.length * 64 + 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rows}
                layout="vertical"
                margin={{ top: 4, right: 70, bottom: 0, left: 4 }}
                barCategoryGap={rows.length > 8 ? "18%" : "28%"}
              >
                {/* Oculto por estilo, NO con `hide`: con `hide` Recharts no
                    registra el eje y el ReferenceLine cae en otra escala. */}
                <XAxis
                  type="number"
                  domain={[0, domainMax]}
                  axisLine={false}
                  tickLine={false}
                  tick={false}
                  height={0}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={<CityTick fontSize={many ? 11 : 12} />}
                  tickLine={false}
                  axisLine={false}
                  width={96}
                  interval={0}
                />
                <Tooltip cursor={{ fill: "var(--color-surface-2)", opacity: 0.5 }} content={<PaceTooltip />} />
                {showAvg && (
                  <ReferenceLine x={avg} stroke={FALLBACK_SERIES} strokeDasharray="4 4" />
                )}
                <Bar dataKey="perDay" radius={[6, 6, 6, 6]} maxBarSize={26} animationDuration={600}>
                  {rows.map((r) => (
                    <Cell
                      key={r.name}
                      fill={r.status === "future" ? FALLBACK_SERIES : ACCENT}
                      opacity={r.status === "future" ? 0.45 : 1}
                    />
                  ))}
                  <LabelList
                    dataKey="perDayStr"
                    position="right"
                    formatter={(v: unknown) => formatAmount(String(v))}
                    style={{ fill: "var(--color-ink-2)", fontSize: 11, fontWeight: 700 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </Card>
  );
}
