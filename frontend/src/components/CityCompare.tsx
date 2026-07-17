import { BedDouble, Crown, Feather, UtensilsCrossed } from "lucide-react";
import { useNavigate } from "react-router-dom";

import DeltaBadge from "@/components/DeltaBadge";
import Flag from "@/components/Flag";
import Card from "@/components/ui/Card";
import { Label } from "@/components/ui/Field";
import { formatUsd, parseMoney } from "@/lib/format";
import type { CityPace, TripBlock } from "@/types";

type Row = {
  city: CityPace;
  perDay: number;
  sleep: number;
  live: number;
};

/** Comparador real entre ciudades ya vividas: ranking $/día con la barra
 *  partida en dormir (alojamiento prorrateado/noche) vs vivir (el resto/día).
 *  Solo paradas con ritmo comparable (pasadas o en curso, con noches); las
 *  futuras no compiten — sus reservas no son ritmo. */
export default function CityCompare({ cities, trip }: { cities: CityPace[]; trip: TripBlock }) {
  const navigate = useNavigate();
  const rows: Row[] = cities
    .filter((c) => c.status !== "future" && c.nights > 0 && c.per_day_usd != null)
    .map((c) => ({
      city: c,
      perDay: parseMoney(c.per_day_usd!),
      sleep: c.lodging_per_night_usd ? parseMoney(c.lodging_per_night_usd) : 0,
      live: c.other_per_day_usd ? parseMoney(c.other_per_day_usd) : 0,
    }))
    .filter((r) => r.perDay > 0)
    .sort((a, b) => b.perDay - a.perDay);

  if (rows.length < 2) return null;

  const max = rows[0].perDay;
  const top = rows[0];
  const bottom = rows[rows.length - 1];
  const podium = [
    { icon: Crown, label: "Más cara", row: top, tint: "bg-accent-amber-bg text-accent-amber" },
    { icon: Feather, label: "Más barata", row: bottom, tint: "bg-accent-teal-bg text-accent-teal" },
  ];

  return (
    <Card className="flex h-full flex-col gap-4 p-5">
      <div className="flex items-baseline justify-between gap-2">
        <Label>Mano a mano ($/día)</Label>
        {trip.avg_per_day_usd && (
          <span className="text-[11px] font-medium text-ink-3">
            promedio <span className="font-tabular font-semibold">{formatUsd(trip.avg_per_day_usd)}</span>
          </span>
        )}
      </div>

      {/* Podio: extremos del ranking, para leer el veredicto de un vistazo.
          Nombre y monto apilados: así el nombre entra completo sin cortarse. */}
      <div className="grid grid-cols-2 gap-3">
        {podium.map(({ icon: Icon, label, row, tint }) => (
          <div key={label} className="flex items-center gap-2.5 rounded-xl bg-surface-2/60 p-2.5">
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tint}`}>
              <Icon size={15} strokeWidth={2} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-3">{label}</p>
              <p className="flex min-w-0 items-center gap-1.5 text-sm font-bold text-ink">
                <Flag flag={row.city.country_flag} className="shrink-0 text-xs" />
                <span className="truncate">{row.city.city_name}</span>
              </p>
              <p className="font-tabular text-xs font-semibold text-ink-2">
                {formatUsd(row.city.per_day_usd!)}/día
              </p>
            </div>
          </div>
        ))}
      </div>

      <ul className="flex flex-col gap-2.5">
        {rows.map((r) => (
          <li key={r.city.stop_slug}>
            <button
              type="button"
              onClick={() => navigate(`/ciudades?c=${r.city.stop_slug}`)}
              className="w-full cursor-pointer rounded-lg px-1 py-0.5 text-left transition-colors hover:bg-surface-2/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/30"
            >
              <div className="flex items-baseline justify-between gap-2 text-[12px]">
                <span className="flex min-w-0 items-center gap-1.5 font-semibold text-ink">
                  <Flag flag={r.city.country_flag} className="shrink-0" />
                  <span className="truncate">{r.city.city_name}</span>
                  {r.city.status === "current" && (
                    <span className="shrink-0 text-[10px] font-bold uppercase text-brick">hoy</span>
                  )}
                </span>
                <span className="flex shrink-0 items-baseline gap-1.5">
                  <span className="font-tabular font-bold text-ink">{formatUsd(r.city.per_day_usd!)}</span>
                  <DeltaBadge pct={r.city.delta_vs_trip_pct} compact />
                </span>
              </div>
              {/* Barra apilada dormir/vivir, misma escala para todas las filas. */}
              <div
                className="mt-1 flex h-2.5 overflow-hidden rounded-full bg-surface-2"
                role="img"
                aria-label={`Dormir ${formatUsd(String(r.sleep))} por noche, vivir ${formatUsd(String(r.live))} por día`}
              >
                <div className="h-full bg-brick" style={{ width: `${(r.sleep / max) * 100}%` }} />
                <div className="h-full bg-accent-teal" style={{ width: `${(r.live / max) * 100}%` }} />
              </div>
            </button>
          </li>
        ))}
      </ul>

      <div className="flex items-center gap-4 text-[11px] font-medium text-ink-3">
        <span className="flex items-center gap-1.5">
          <BedDouble size={13} strokeWidth={2} className="text-brick" aria-hidden="true" /> Dormir /noche
        </span>
        <span className="flex items-center gap-1.5">
          <UtensilsCrossed size={13} strokeWidth={2} className="text-accent-teal" aria-hidden="true" /> Vivir /día
        </span>
      </div>
    </Card>
  );
}
