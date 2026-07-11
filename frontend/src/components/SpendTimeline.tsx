import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, GRID, TICK, TOOLTIP_STYLE } from "@/lib/chartTheme";
import type { TimePoint } from "@/types";

export default function SpendTimeline({ data }: { data: TimePoint[] }) {
  const rows = data.map((p) => ({
    date: p.date.slice(5), // MM-DD
    usd: parseMoney(p.cumulative_usd),
  }));
  if (rows.length === 0) return null;
  return (
    <section className="rounded-[4px] border-2 border-border bg-surface p-4 card-shadow">
      <h2 className="mb-3 text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
        Gasto acumulado (USD)
      </h2>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="2 4" />
            <XAxis dataKey="date" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }}
                   minTickGap={24} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ stroke: GRID, strokeWidth: 1 }}
              contentStyle={TOOLTIP_STYLE}
              formatter={(v) => [formatUsd(String(v)), "Acumulado"]}
            />
            <Line type="monotone" dataKey="usd" stroke={ACCENT} strokeWidth={2}
                  dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "#FFFFFF" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
