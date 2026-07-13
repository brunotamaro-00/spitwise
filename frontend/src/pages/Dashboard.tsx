import { useQuery } from "@tanstack/react-query";
import { Receipt, TrendingUp, Wallet } from "lucide-react";
import { useState } from "react";

import { listUsers } from "@/api/users";
import { getBalance, getByCategory, getByCity, getSummary } from "@/api/dashboard";
import { getCityDaily, getCitySummary } from "@/api/cities";
import BalanceHero from "@/components/BalanceHero";
import CategoryDonut from "@/components/CategoryDonut";
import CitySpendChart from "@/components/CitySpendChart";
import SettleDialog from "@/components/SettleDialog";
import SpendBarChart from "@/components/SpendBarChart";
import { PageTitle } from "@/components/ui/Brand";
import ErrorState from "@/components/ui/ErrorState";
import Kpi from "@/components/ui/Kpi";
import Skeleton from "@/components/ui/Skeleton";
import { capitalize, formatUsd } from "@/lib/format";

export default function Dashboard() {
  const [settle, setSettle] = useState(false);
  const balance = useQuery({ queryKey: ["balance"], queryFn: getBalance });
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getSummary });
  const byCity = useQuery({ queryKey: ["dashboard", "city"], queryFn: getByCity });
  const byCat = useQuery({ queryKey: ["dashboard", "cat"], queryFn: getByCategory });
  const daily = useQuery({ queryKey: ["dashboard", "daily"], queryFn: () => getCityDaily([]) });
  // Promedio por día del viaje (base itinerario): dato económico del hero.
  const trip = useQuery({ queryKey: ["city", "summary", []], queryFn: () => getCitySummary([]) });
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });

  const names: Record<number, string> = Object.fromEntries(
    (users.data ?? []).map((u) => [u.id, capitalize(u.username)]),
  );

  // No mostrar el bucket "Sin ciudad" (gastos generales) en el gráfico por ciudad.
  const cityRows = (byCity.data ?? []).filter((c) => c.stop_slug || c.city_name);

  const queries = [balance, summary, byCity, byCat, daily];
  if (queries.some((q) => q.isError)) {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>Dashboard</PageTitle>
        <ErrorState onRetry={() => queries.forEach((q) => q.isError && q.refetch())} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Dashboard</PageTitle>
      </div>

      {/* Hero del viaje: el balance manda; abajo, la foto económica. */}
      <div className="animate-rise-in stagger-1">
        {balance.data ? (
          <BalanceHero balance={balance.data} names={names} onSettle={() => setSettle(true)} />
        ) : (
          <Skeleton className="h-40" />
        )}
      </div>

      <div className="animate-rise-in stagger-2 grid grid-cols-3 gap-3">
        {summary.data ? (
          <>
            <Kpi icon={Wallet} tint="brick" label="Mis gastos" value={formatUsd(summary.data.total_usd)} />
            <Kpi icon={Receipt} tint="blue" label="Movimientos" value={String(summary.data.movement_count)} />
            <Kpi
              icon={TrendingUp}
              tint="amber"
              label="Prom./día"
              value={formatUsd(trip.data?.avg_per_day_usd ?? "0")}
            />
          </>
        ) : (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)
        )}
      </div>

      {/* items-stretch + grid 12: el donut (denso) va angosto, las barras por
          ciudad respiran en la columna ancha; nadie deja huecos. */}
      <div className="animate-rise-in stagger-3 grid grid-cols-1 items-stretch gap-5 lg:grid-cols-12">
        <div className="lg:col-span-5">
          {byCat.data ? (
            <CategoryDonut data={byCat.data} subtitle="Todo el viaje" />
          ) : (
            <Skeleton className="h-64" />
          )}
        </div>
        <div className="lg:col-span-7">
          {byCity.data ? <CitySpendChart data={cityRows} /> : <Skeleton className="h-64" />}
        </div>
      </div>
      <div className="animate-rise-in stagger-4">
        {daily.data ? (
          <SpendBarChart data={daily.data} granularity="week" subtitle="Gastos con ciudad" />
        ) : (
          <Skeleton className="h-60" />
        )}
      </div>

      {settle && <SettleDialog balance={balance.data} onClose={() => setSettle(false)} />}
    </div>
  );
}
