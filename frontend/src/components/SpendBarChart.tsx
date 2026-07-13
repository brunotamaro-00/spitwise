import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatDayHeader, formatShortDate, formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, GRID, TICK, compactUsd } from "@/lib/chartTheme";
import type { CityDaily } from "@/types";

type Granularity = "day" | "week";
type Row = { iso: string; label: string; usd: number; total: string };

/** Lunes (ISO) de la semana que contiene la fecha yyyy-mm-dd. */
function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const dow = dt.getDay(); // 0=Dom..6=Sáb
  const delta = dow === 0 ? -6 : 1 - dow;
  dt.setDate(dt.getDate() + delta);
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${dt.getFullYear()}-${mm}-${dd}`;
}

function ChartTooltip({ active, payload, granularity }: {
  active?: boolean;
  payload?: { payload: Row }[];
  granularity: Granularity;
}) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const when = granularity === "week" ? `Semana del ${formatDayHeader(r.iso)}` : formatDayHeader(r.iso);
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="text-xs font-medium capitalize text-ink-3">{when}</div>
      <div className="mt-0.5 font-tabular text-sm font-semibold text-ink">{formatUsd(r.total)}</div>
    </div>
  );
}

/** Barras de gasto (no acumulado) por día o por semana, según granularidad.
 *  La card llena la altura de su celda de grid (flex-1) para no dejar huecos
 *  al lado de cards más altas en desktop. */
export default function SpendBarChart({
  data,
  granularity = "day",
  title,
  subtitle,
}: {
  data: CityDaily[];
  granularity?: Granularity;
  title?: string;
  subtitle?: string;
}) {
  const heading = title ?? (granularity === "week" ? "Gasto por semana" : "Gasto por día");

  const rows = useMemo<Row[]>(() => {
    if (granularity === "day") {
      return data.map((p) => ({
        iso: p.date,
        label: formatShortDate(p.date),
        usd: parseMoney(p.total_usd),
        total: p.total_usd,
      }));
    }
    const byWeek = new Map<string, number>();
    for (const p of data) {
      const wk = mondayOf(p.date);
      byWeek.set(wk, (byWeek.get(wk) ?? 0) + parseMoney(p.total_usd));
    }
    return [...byWeek.entries()]
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([iso, usd]) => ({ iso, label: formatShortDate(iso), usd, total: usd.toFixed(2) }));
  }, [data, granularity]);

  if (rows.length === 0) return null;
  const total = rows.reduce((acc, r) => acc + r.usd, 0);

  return (
    <Card className="flex h-full flex-col p-5">
      <div className="mb-4 flex items-baseline justify-between gap-2">
        <Label className="block">{heading}</Label>
        {subtitle && <span className="text-[11px] text-ink-faint">{subtitle}</span>}
      </div>
      {/* relative + hijo absoluto: el 100% del ResponsiveContainer necesita una
          altura definida; min-height sola no la da y el chart colapsa a 0. */}
      <div
        className="relative min-h-52 flex-1"
        role="img"
        aria-label={`${heading}: total ${formatUsd(total.toFixed(2))} en ${rows.length} ${
          granularity === "week" ? "semanas" : "días"
        }`}
      >
        <div className="absolute inset-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="label"
              tick={TICK}
              tickLine={false}
              axisLine={false}
              minTickGap={granularity === "week" ? 8 : 16}
            />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={40} tickFormatter={compactUsd} />
            <Tooltip
              cursor={{ fill: "var(--color-surface-2)", opacity: 0.5 }}
              content={<ChartTooltip granularity={granularity} />}
            />
            <Bar
              dataKey="usd"
              fill={ACCENT}
              radius={[5, 5, 0, 0]}
              maxBarSize={granularity === "week" ? 44 : 34}
              animationDuration={600}
            />
          </BarChart>
        </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}
