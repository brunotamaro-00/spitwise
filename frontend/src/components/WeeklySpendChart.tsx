import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatDayHeader, formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, GRID, TICK, compactUsd } from "@/lib/chartTheme";
import type { CityDaily } from "@/types";

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

/** Barras de gasto por semana (no acumulado). Agrupa los puntos diarios por
 *  semana ISO (lunes) del lado del cliente. */
export default function WeeklySpendChart({
  data,
  title = "Gasto por semana",
}: {
  data: CityDaily[];
  title?: string;
}) {
  const rows = useMemo<Row[]>(() => {
    const byWeek = new Map<string, number>();
    for (const p of data) {
      const wk = mondayOf(p.date);
      byWeek.set(wk, (byWeek.get(wk) ?? 0) + parseMoney(p.total_usd));
    }
    return [...byWeek.entries()]
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([iso, usd]) => ({ iso, label: iso.slice(5), usd, total: usd.toFixed(2) }));
  }, [data]);
  if (rows.length === 0) return null;

  return (
    <Card className="p-5">
      <Label className="mb-4 block">{title}</Label>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tick={TICK} tickLine={false} axisLine={false} minTickGap={8} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={40} tickFormatter={compactUsd} />
            <Tooltip
              cursor={{ fill: "var(--color-surface-2)", opacity: 0.5 }}
              content={<WeekTooltip />}
            />
            <Bar dataKey="usd" fill={ACCENT} radius={[5, 5, 0, 0]} maxBarSize={44} animationDuration={600} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function WeekTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="text-xs font-medium text-ink-3">Semana del {formatDayHeader(r.iso)}</div>
      <div className="mt-0.5 font-tabular text-sm font-semibold text-ink">{formatUsd(r.total)}</div>
    </div>
  );
}
