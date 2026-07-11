import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
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
    <Card className="p-4">
      <Label className="mb-3 block">Gasto acumulado (USD)</Label>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="date" tick={TICK} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ stroke: GRID, strokeWidth: 1 }}
              contentStyle={TOOLTIP_STYLE}
              formatter={(v) => [formatUsd(String(v)), "Acumulado"]}
            />
            <Line type="monotone" dataKey="usd" stroke={ACCENT} strokeWidth={2.5}
                  dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "#FFFFFF" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
