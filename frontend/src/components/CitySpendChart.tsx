import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
    <section className="rounded-[4px] border-2 border-border bg-surface p-4 card-shadow">
      <h2 className="mb-3 text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
        Gasto por ciudad (USD)
      </h2>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="2 4" />
            <XAxis dataKey="name" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }}
                   interval={0} angle={rows.length > 5 ? -30 : 0}
                   textAnchor={rows.length > 5 ? "end" : "middle"} height={rows.length > 5 ? 52 : 24} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: "#EAE2CB", opacity: 0.5 }}
              contentStyle={TOOLTIP_STYLE}
              formatter={(v) => [formatUsd(String(v)), "Gastado"]}
            />
            <Bar dataKey="usd" fill={ACCENT} radius={[4, 4, 0, 0]} maxBarSize={44} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
