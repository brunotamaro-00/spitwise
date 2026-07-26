import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Receipt, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listCategories } from "@/api/categories";
import { getStops } from "@/api/cities";
import { listUsers } from "@/api/users";
import { getBalance, getByCategory, getPace, getSummary } from "@/api/dashboard";
import { listMovements } from "@/api/movements";
import BalanceHero from "@/components/BalanceHero";
import CategoryDonut from "@/components/CategoryDonut";
import CityPaceChart from "@/components/CityPaceChart";
import MovementRow from "@/components/MovementRow";
import MovementSheet from "@/components/MovementSheet";
import SettleDialog from "@/components/SettleDialog";
import TripPaceCard from "@/components/TripPaceCard";
import AnimatedUsd from "@/components/ui/AnimatedUsd";
import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import Skeleton from "@/components/ui/Skeleton";
import SkeletonReveal from "@/components/ui/SkeletonReveal";
import { capitalize, formatUsd } from "@/lib/format";
import { myShare } from "@/lib/share";
import { useMe } from "@/lib/useMe";
import type { Category, Movement } from "@/types";

export default function Dashboard() {
  const [settle, setSettle] = useState(false);
  const [viewing, setViewing] = useState<Movement | null>(null);
  const balance = useQuery({ queryKey: ["balance"], queryFn: getBalance });
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: getSummary });
  const byCat = useQuery({ queryKey: ["dashboard", "cat"], queryFn: getByCategory });
  const pace = useQuery({ queryKey: ["dashboard", "pace"], queryFn: getPace });
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers, staleTime: Infinity });
  const recent = useQuery({ queryKey: ["movements"], queryFn: listMovements });
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories, staleTime: Infinity });
  const stops = useQuery({ queryKey: ["stops"], queryFn: getStops, staleTime: 60_000 });
  const me = useMe();

  const catMap = useMemo(
    () => Object.fromEntries((categories.data ?? []).map((c) => [c.id, c])) as Record<number, Category>,
    [categories.data],
  );
  const stopFlags = useMemo(
    () => Object.fromEntries((stops.data ?? []).map((s) => [s.slug, s.country_flag])),
    [stops.data],
  );
  const lastMovs = (recent.data ?? []).slice(0, 4);

  // Parte del total del hero que todavía no entró al balance (pending/awaiting).
  // El hero muestra `summary.total_usd`, que es la parte del usuario, así que se
  // suma con `myShare` para que las dos cifras hablen de lo mismo.
  const unsettled = useMemo(() => {
    let usd = 0;
    let count = 0;
    for (const m of recent.data ?? []) {
      if (m.type !== "expense") continue;
      if (m.status !== "pending" && m.status !== "awaiting") continue;
      const share = me.data ? myShare(m, me.data.id) : 0;
      if (share <= 0) continue;
      usd += share;
      count += 1;
    }
    return { usd, count };
  }, [recent.data, me.data]);

  const names: Record<number, string> = Object.fromEntries(
    (users.data ?? []).map((u) => [u.id, capitalize(u.username)]),
  );

  const queries = [balance, summary, byCat, pace];
  if (queries.some((q) => q.isError)) {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>Dashboard</PageTitle>
        <ErrorState onRetry={() => queries.forEach((q) => q.isError && q.refetch())} />
      </div>
    );
  }

  const trip = pace.data?.trip;
  const preTrip = trip?.status === "not_started";

  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Dashboard</PageTitle>
      </div>

      {/* Hero del viaje: el gasto total manda; el balance es secundario. */}
      <div className="animate-rise-in stagger-1">
        <SkeletonReveal ready={!!summary.data} skeleton={<Skeleton className="h-44" />}>
          {() => (
          <Card className="relative overflow-hidden p-6 text-white hero-gradient soft-hero lg:p-7">
            <div className="spit-dots absolute inset-0" aria-hidden="true" />
            <div className="hero-sheen absolute inset-0" aria-hidden="true" />
            <div className="relative">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
                Mis gastos · todo el viaje
              </p>
              <p className="mt-2 font-display text-6xl leading-none tracking-[-0.02em] font-tabular lg:text-7xl">
                <AnimatedUsd value={summary.data!.total_usd} />
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-white/85">
                <span className="inline-flex items-center gap-1.5">
                  <Receipt size={15} strokeWidth={2} aria-hidden="true" />
                  {summary.data!.movement_count} movimiento{summary.data!.movement_count === 1 ? "" : "s"}
                </span>
                {trip?.avg_per_day_usd && (
                  <span className="inline-flex items-center gap-1.5">
                    <TrendingUp size={15} strokeWidth={2} aria-hidden="true" />
                    <span className="font-tabular">{formatUsd(trip.avg_per_day_usd)}</span>
                    {preTrip ? " previsto/día" : " por día"}
                  </span>
                )}
              </div>
              {/* El total incluye reservas futuras; el balance de abajo no. Sin
                  decirlo, la diferencia entre las dos cifras no se explica. */}
              {unsettled.count > 0 && (
                <p className="mt-3 text-xs text-white/70">
                  Incluye {unsettled.count} {unsettled.count === 1 ? "gasto" : "gastos"} por confirmar ·{" "}
                  <span className="font-tabular font-semibold">{formatUsd(String(unsettled.usd))}</span> — fuera del balance
                </p>
              )}
            </div>
          </Card>
          )}
        </SkeletonReveal>
      </div>

      <div className="animate-rise-in stagger-2">
        <SkeletonReveal ready={!!balance.data} skeleton={<Skeleton className="h-20" />}>
          {() => (
            <BalanceHero balance={balance.data!} names={names} myId={me.data?.id} onSettle={() => setSettle(true)} />
          )}
        </SkeletonReveal>
      </div>

      <div className="animate-rise-in stagger-3">
        <SkeletonReveal ready={!!pace.data} skeleton={<Skeleton className="h-40" />}>
          {() => <TripPaceCard pace={pace.data!} />}
        </SkeletonReveal>
      </div>

      {/* items-stretch + grid 12: el donut (denso) va angosto, el ritmo por
          ciudad respira en la columna ancha; nadie deja huecos. */}
      <div className="animate-rise-in stagger-4 grid grid-cols-1 items-stretch gap-5 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <SkeletonReveal ready={!!byCat.data} skeleton={<Skeleton className="h-64" />}>
            {() => <CategoryDonut data={byCat.data!} subtitle="Todo el viaje" />}
          </SkeletonReveal>
        </div>
        <div className="lg:col-span-7">
          <SkeletonReveal ready={!!pace.data} skeleton={<Skeleton className="h-64" />}>
            {() => <CityPaceChart cities={pace.data!.cities} trip={pace.data!.trip} />}
          </SkeletonReveal>
        </div>
      </div>

      {/* Lo último que entró (por carga, no por fecha): el pulso del ledger
          sin salir del dashboard. */}
      {lastMovs.length > 0 && (
        <div className="animate-rise-in stagger-5">
          <Card className="px-5 py-1">
            <div className="flex items-center justify-between py-3">
              <h2 className="text-sm font-bold text-ink">Últimos movimientos</h2>
              <Link
                to="/movimientos"
                className="flex items-center gap-1 text-[12px] font-semibold text-brick transition-colors hover:text-brick-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40 rounded-md"
              >
                Ver todos
                <ArrowRight size={13} strokeWidth={2.25} aria-hidden="true" />
              </Link>
            </div>
            {lastMovs.map((m) => (
              <MovementRow
                key={m.id}
                mv={m}
                myId={me.data?.id}
                category={m.category_id != null ? catMap[m.category_id] : undefined}
                flag={m.stop_slug ? stopFlags[m.stop_slug] : undefined}
                readOnly
                onOpen={setViewing}
              />
            ))}
          </Card>
        </div>
      )}

      {viewing && (
        <MovementSheet
          mv={viewing}
          myId={me.data?.id}
          category={viewing.category_id != null ? catMap[viewing.category_id] : undefined}
          flag={viewing.stop_slug ? stopFlags[viewing.stop_slug] : undefined}
          onClose={() => setViewing(null)}
        />
      )}
      {settle && <SettleDialog balance={balance.data} onClose={() => setSettle(false)} />}
    </div>
  );
}
