import { formatUsd } from "@/lib/format";

/** Lo gastado contra el plan de la parada: una barra que se llena.
 *
 *  Deliberadamente **simple**. Antes marcaba también el plan devengado hasta
 *  hoy (el "poste") y el techo de la banda: dos marcas que sin su leyenda al
 *  lado son un misterio, y la leyenda era la línea más jergosa de la página.
 *  El veredicto de ritmo que daba el poste lo dice el `BandBadge` con una
 *  palabra ("ahorrando"), que es lo que alguien entiende de una.
 *
 *  Por eso el eje es el pote (`max(envelope, spent)`): el final de la barra ES
 *  el plan de la ciudad, el mismo número que el pie escribe al lado. Con el
 *  techo como eje, la barra terminaba en una cifra que no estaba escrita en
 *  ningún lado. Tampoco aplica `BAR_MAX_USD`: ese eje fijo es de las barras de
 *  USD/día, y esta es plata total de una parada.
 *
 *  Pasados de pote el relleno **no** se pinta todo de rojo: el tramo que
 *  entraba en el plan queda blanco y solo el exceso va en la rampa, que es la
 *  parte accionable.
 *
 *  Variante hero: blancos sobre el gradiente ladrillo, como `BudgetBandBar`. */
export default function StayEnvelopeBar({
  spent,
  envelope,
  over,
}: {
  spent: number;
  envelope: number;
  over: boolean;
}) {
  const scale = Math.max(envelope, spent, 1);
  const pct = (n: number) => Math.min(Math.max((n / scale) * 100, 0), 100);
  const fill = pct(spent);
  const target = pct(envelope);

  return (
    <div
      className="relative flex h-4 items-center"
      role="img"
      aria-label={
        `Gastaron ${formatUsd(String(spent), "whole")} de los ` +
        `${formatUsd(String(envelope), "whole")} del plan de esta parada`
      }
    >
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-white/15">
        {/* Lo gastado que todavía entraba en el plan. */}
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-white"
          style={{ width: `${Math.min(fill, target)}%` }}
        />
        {over && (
          <div
            className="absolute inset-y-0 bg-heat-over"
            style={{ left: `${target}%`, width: `${Math.max(fill - target, 0)}%` }}
          />
        )}
      </div>
    </div>
  );
}
