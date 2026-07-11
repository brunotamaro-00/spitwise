import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatUsd, parseMoney } from "@/lib/format";
import { ACCENT, GRID, TICK, TOOLTIP_STYLE } from "@/lib/chartTheme";
import type { CitySpend } from "@/types";

export default function CitySpendChart({ data }: { data: CitySpend[] }) {
  const rows = data.map((c) => ({
    name: c.city_name || c.stop_slug || "Sin ciudad",
    usd: parseMoney(c.total_usd),
  }));
  if (rows.length === 0) return null;
  return (
    <Card className="p-4">
      <Label className="mb-3 block">Gasto por ciudad (USD)</Label>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="name" tick={TICK} tickLine={false} axisLine={false}
                   interval={0} angle={rows.length > 5 ? -30 : 0}
                   textAnchor={rows.length > 5 ? "end" : "middle"} height={rows.length > 5 ? 52 : 24} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: "#EEF0F3", opacity: 0.6 }}
              contentStyle={TOOLTIP_STYLE}
              formatter={(v) => [formatUsd(String(v)), "Gastado"]}
            />
            <Bar dataKey="usd" fill={ACCENT} radius={[6, 6, 0, 0]} maxBarSize={40} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
