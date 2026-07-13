import { useQuery } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import { useState } from "react";

import { listUsers } from "@/api/users";
import { getBalance, getByCategory, getByCity, getSummary } from "@/api/dashboard";
import { getCityDaily } from "@/api/cities";
import BalanceHero from "@/components/BalanceHero";
import CategoryDonut from "@/components/CategoryDonut";
import CitySpendChart from "@/components/CitySpendChart";
import SettleDialog from "@/components/SettleDialog";
import WeeklySpendChart from "@/components/WeeklySpendChart";
import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import Skeleton from "@/components/ui/Skeleton";
import { capitalize, formatUsd } from "@/lib/format";

export default function Dashboard() {
  const [settle, setSettle] = useState(false);
  const balance = useQuery({ queryKey: ["balance"], queryFn: getBalance });
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getSummary });
  const byCity = useQuery({ queryKey: ["dashboard", "city"], queryFn: getByCity });
  const byCat = useQuery({ queryKey: ["dashboard", "cat"], queryFn: getByCategory });
  const daily = useQuery({ queryKey: ["dashboard", "daily"], queryFn: () => getCityDaily([]) });
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });

  const names: Record<number, string> = Object.fromEntries(
    (users.data ?? []).map((u) => [u.id, capitalize(u.username)]),
  );

  // No mostrar el bucket "Sin ciudad" (gastos generales) en el gráfico por ciudad.
  const cityRows = (byCity.data ?? []).filter((c) => c.stop_slug || c.city_name);

  return (
    <div className="flex animate-fade-in flex-col gap-5">
      <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
      <div className="grid gap-5 lg:grid-cols-2">
        {balance.data ? (
          <BalanceHero balance={balance.data} names={names} onSettle={() => setSettle(true)} />
        ) : (
          <Skeleton className="h-32" />
        )}

        {summary.data ? (
          <Card className="flex flex-col justify-center p-5">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brick-bg text-brick">
                <Wallet size={16} strokeWidth={2} aria-hidden="true" />
              </span>
              <Label>Mis gastos</Label>
            </div>
            <p className="mt-2 font-display text-4xl leading-none text-ink font-tabular">
              {formatUsd(summary.data.total_usd)}
            </p>
            <p className="mt-1.5 text-sm text-ink-3">
              {summary.data.movement_count} movimiento{summary.data.movement_count === 1 ? "" : "s"} tuyo
              {summary.data.movement_count === 1 ? "" : "s"}
            </p>
          </Card>
        ) : (
          <Skeleton className="h-32" />
        )}
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
        {byCat.data ? <CategoryDonut data={byCat.data} /> : <Skeleton className="h-64" />}
        {byCity.data ? <CitySpendChart data={cityRows} /> : <Skeleton className="h-64" />}
      </div>
      {daily.data ? <WeeklySpendChart data={daily.data} /> : <Skeleton className="h-60" />}

      {settle && <SettleDialog balance={balance.data} onClose={() => setSettle(false)} />}
    </div>
  );
}
