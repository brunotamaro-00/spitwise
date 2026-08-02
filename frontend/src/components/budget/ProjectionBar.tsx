import type { BandLevel } from "@/lib/budget";
import { formatUsd } from "@/lib/format";

const MARK = {
  save: "bg-heat-save",
  plan: "bg-heat-plan",
  edge: "bg-heat-edge",
  over: "bg-heat-over",
  far: "bg-heat-far",
} as const;

/** Dónde cae la proyección del viaje dentro del plan.
 *
 *  Hermana de `BudgetBandBar` en lenguaje visual —zona del plan tenue, postes,
 *  mismo alto— pero **no** comparte su escala: acá el eje son los miles de
 *  dólares de vivir del viaje entero, no USD/día, así que el eje fijo de
 *  `BAR_MAX_USD` no aplica y la escala se arma alrededor de la banda.
 *
 *  Y la proyección se marca con una **aguja**, no con relleno: no es "cuánto
 *  llevás" (eso sí crece) sino "dónde vas a caer si seguís así". Un relleno
 *  diría una cosa que no es. */
export default function ProjectionBar({
  min,
  max,
  value,
  level,
}: {
  min: number;
  max: number;
  value: number;
  level: BandLevel;
}) {
  const scale = Math.max(max * 1.15, value * 1.08, 1);
  const pct = (n: number) => Math.min(Math.max((n / scale) * 100, 0), 100);
  const start = pct(min);
  const end = pct(max);
  const at = pct(value);

  return (
    <div
      className="relative flex h-5 items-center"
      role="img"
      aria-label={
        `Proyección de ${formatUsd(String(value), "whole")} contra un plan de ` +
        `${formatUsd(String(min), "whole")} a ${formatUsd(String(max), "whole")}`
      }
    >
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className="absolute inset-y-0 rounded-full bg-accent-teal-bg"
          style={{ left: `${start}%`, width: `${end - start}%` }}
        />
      </div>
      {/* Postes del plan: piso y techo. Sin ellos la zona tenue se pierde
          apenas la aguja le cae encima. */}
      {[
        { role: "floor", at: start },
        { role: "ceiling", at: end },
      ].map((p) => (
        <span
          key={p.role}
          aria-hidden="true"
          className="absolute h-3 w-0.5 rounded-full bg-ink/20"
          style={{ left: `calc(${p.at}% - 1px)` }}
        />
      ))}
      {/* La aguja: dónde termina el viaje al ritmo de lo ya cerrado. */}
      <span
        aria-hidden="true"
        className={`absolute h-5 w-1 rounded-full ring-2 ring-surface ${MARK[level]}`}
        style={{ left: `calc(${at}% - 2px)` }}
      />
    </div>
  );
}
