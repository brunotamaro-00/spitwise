import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listUsers } from "@/api/users";
import { getBalance, getByCategory, getByCity, getSummary, getTimeseries } from "@/api/dashboard";
import BalanceHero from "@/components/BalanceHero";
import CategoryDonut from "@/components/CategoryDonut";
import CitySpendChart from "@/components/CitySpendChart";
import SettleDialog from "@/components/SettleDialog";
import SpendTimeline from "@/components/SpendTimeline";
import { formatUsd } from "@/lib/format";

export default function Dashboard() {
  const [settle, setSettle] = useState(false);
  const balance = useQuery({ queryKey: ["balance"], queryFn: getBalance });
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getSummary });
  const byCity = useQuery({ queryKey: ["dashboard", "city"], queryFn: getByCity });
  const byCat = useQuery({ queryKey: ["dashboard", "cat"], queryFn: getByCategory });
  const ts = useQuery({ queryKey: ["dashboard", "ts"], queryFn: getTimeseries });
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });

  const names: Record<number, string> = Object.fromEntries(
    (users.data ?? []).map((u) => [u.id, u.username]),
  );

  return (
    <div className="flex animate-fade-in flex-col gap-4">
      {balance.data && (
        <BalanceHero balance={balance.data} names={names} onSettle={() => setSettle(true)} />
      )}
      {summary.data && (
        <section className="rounded-[4px] border-2 border-border bg-surface p-5 card-shadow">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-ink-3">
            Total del viaje
          </p>
          <p className="mt-1 font-display text-4xl uppercase leading-none text-ink font-tabular">
            {formatUsd(summary.data.total_usd)}
          </p>
          <p className="mt-1 text-sm text-ink-2">
            {summary.data.movement_count} movimiento{summary.data.movement_count === 1 ? "" : "s"}
          </p>
        </section>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {byCity.data && <CitySpendChart data={byCity.data} />}
        {byCat.data && <CategoryDonut data={byCat.data} />}
      </div>
      {ts.data && <SpendTimeline data={ts.data} />}
      {settle && <SettleDialog onClose={() => setSettle(false)} />}
    </div>
  );
}
