import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatDayHeader, formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, GRID, TICK } from "@/lib/chartTheme";
import type { TimePoint } from "@/types";

type Row = { iso: string; date: string; usd: number; total: string };

function AreaTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2 soft-pop">
      <div className="text-xs font-medium text-ink-3">{formatDayHeader(r.iso)}</div>
      <div className="mt-0.5 font-tabular text-sm font-semibold text-ink">{formatUsd(r.total)}</div>
    </div>
  );
}

export default function SpendTimeline({
  data,
  title = "Gasto acumulado",
}: {
  data: TimePoint[];
  title?: string;
}) {
  const rows: Row[] = data.map((p) => ({
    iso: p.date,
    date: p.date.slice(5), // MM-DD
    usd: parseMoney(p.cumulative_usd),
    total: p.cumulative_usd,
  }));
  if (rows.length === 0) return null;

  return (
    <Card className="p-5">
      <Label className="mb-4 block">{title}</Label>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
            <defs>
              <linearGradient id="spendArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={ACCENT} stopOpacity={0.28} />
                <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="date" tick={TICK} tickLine={false} axisLine={false} minTickGap={28} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={44} />
            <Tooltip cursor={{ stroke: GRID, strokeWidth: 1 }} content={<AreaTooltip />} />
            <Area
              type="monotone"
              dataKey="usd"
              stroke={ACCENT}
              strokeWidth={2.5}
              fill="url(#spendArea)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--color-surface)" }}
              animationDuration={650}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
