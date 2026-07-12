import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatDayHeader, formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, GRID, TICK, compactUsd } from "@/lib/chartTheme";
import type { CityDaily } from "@/types";

type Row = { iso: string; date: string; usd: number; total: string };

function DailyTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="text-xs font-medium text-ink-3">{formatDayHeader(r.iso)}</div>
      <div className="mt-0.5 font-tabular text-sm font-semibold text-ink">{formatUsd(r.total)}</div>
    </div>
  );
}

export default function DailySpendChart({
  data,
  title = "Gasto por día",
}: {
  data: CityDaily[];
  title?: string;
}) {
  const rows: Row[] = data.map((p) => ({
    iso: p.date,
    date: p.date.slice(5),
    usd: parseMoney(p.total_usd),
    total: p.total_usd,
  }));
  if (rows.length === 0) return null;

  return (
    <Card className="p-5">
      <Label className="mb-4 block">{title}</Label>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="date" tick={TICK} tickLine={false} axisLine={false} minTickGap={16} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={40} tickFormatter={compactUsd} />
            <Tooltip cursor={{ fill: "var(--color-surface-2)", opacity: 0.5 }} content={<DailyTooltip />} />
            <Bar dataKey="usd" fill={ACCENT} radius={[5, 5, 0, 0]} maxBarSize={34} animationDuration={600} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
