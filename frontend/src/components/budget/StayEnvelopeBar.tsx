import { formatUsd } from "@/lib/format";

/** El pote de la parada: lo gastado contra lo que el plan separó, con el fin
 *  del pote a la vista.
 *
 *  Habla el mismo idioma que `CushionMeter` —relleno = gastado, poste = lo
 *  devengado del plan hasta hoy, y **el hueco entre los dos es el ahorro**—
 *  pero el eje no es el mayor de los dos números sino **el pote entero**: acá
 *  la barra tiene un final que significa algo (el plan de la ciudad se acaba),
 *  y ese final es justo lo que el hero está contando. Por eso tampoco aplica
 *  `BAR_MAX_USD`: ese eje fijo es de las barras de USD/día, y esta es plata
 *  total de una parada.
 *
 *  El techo de la banda va como marca tenue después del objetivo: es el margen
 *  que queda antes de "pasarse" de verdad. Pasado el eje el relleno capea y lo
 *  dice con el tope; nunca crece fuera de la barra.
 *
 *  Variante hero: blancos sobre el gradiente ladrillo, como `BudgetBandBar`. */
export default function StayEnvelopeBar({
  spent,
  envelope,
  max,
  accrued,
  over,
}: {
  spent: number;
  envelope: number;
  max: number;
  accrued: number | null;
  over: boolean;
}) {
  const scale = Math.max(max, envelope, spent, 1);
  const pct = (n: number) => Math.min(Math.max((n / scale) * 100, 0), 100);
  const fill = pct(spent);
  const target = pct(envelope);
  const ceiling = pct(max);
  const post = accrued == null ? null : pct(accrued);

  return (
    <div>
      <div
        className="relative flex h-5 items-center"
        role="img"
        aria-label={
          `Gastaron ${formatUsd(String(spent), "whole")} del plan de ` +
          `${formatUsd(String(envelope), "whole")} de esta parada ` +
          `(techo ${formatUsd(String(max), "whole")})`
        }
      >
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-white/15">
          {/* El hueco, tintado: entre lo gastado y el poste está el ahorro de la
              parada. Es EL mensaje de la barra, así que tiene que separarse del
              track — a 5 puntos de opacidad de diferencia no se veía. */}
          {post != null && post > fill && (
            <div
              className="absolute inset-y-0 bg-white/35"
              style={{ left: `${fill}%`, width: `${post - fill}%` }}
            />
          )}
          {/* Lo gastado que todavía entraba en el plan. */}
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-white"
            style={{ width: `${Math.min(fill, target)}%` }}
          />
          {/* Y el exceso, aparte: pintar TODO el relleno de rojo decía "te
              pasaste" pero escondía dónde se había terminado el plan, que es la
              única parte accionable — cuánto de lo gastado sobra. */}
          {over && (
            <div
              className="absolute inset-y-0 bg-heat-over"
              style={{ left: `${target}%`, width: `${Math.max(fill - target, 0)}%` }}
            />
          )}
        </div>

        {/* Poste del plan hasta hoy: sin él, el relleno es una barra a medio
            llenar en vez de una comparación. */}
        {post != null && (
          <span
            aria-hidden="true"
            className="absolute h-5 w-0.5 rounded-full bg-white/80"
            style={{ left: `calc(${post}% - 1px)` }}
          />
        )}
        {/* Fin del pote: hasta acá cuenta el número del hero. Va más marcado que
            el techo — el techo es contexto, el objetivo es lo que se está
            contando. */}
        <span
          aria-hidden="true"
          className="absolute h-3.5 w-0.5 rounded-full bg-white/55"
          style={{ left: `calc(${target}% - 1px)` }}
        />
        {ceiling > target && (
          <span
            aria-hidden="true"
            className="absolute h-2.5 w-px rounded-full bg-white/30"
            style={{ left: `calc(${ceiling}% - 0.5px)` }}
          />
        )}
      </div>
    </div>
  );
}
