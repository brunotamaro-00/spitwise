import { formatUsd } from "@/lib/format";

/** Lo gastado contra lo que el plan ya había separado, en una sola barra.
 *
 *  **El hueco es el colchón.** El poste marca lo devengado del plan hasta hoy
 *  y el relleno lo que realmente se gastó: lo que sobra entre uno y otro es el
 *  número grande de la card, dibujado. Al revés —gastando de más— el relleno
 *  cruza el poste y el exceso queda del otro lado, más tenue.
 *
 *  Por eso no es una barra de progreso normalizada a 100: acá el 100 es el
 *  mayor de los dos números, así el poste se mueve y el hueco significa algo. */
export default function CushionMeter({
  spent,
  planned,
  ahead,
}: {
  spent: number;
  planned: number;
  ahead: boolean;
}) {
  const scale = Math.max(spent, planned, 1);
  const pct = (n: number) => Math.min(Math.max((n / scale) * 100, 0), 100);
  const at = pct(planned);
  const fill = pct(spent);
  const over = fill > at;

  return (
    <div>
      <div
        className="relative flex h-4 items-center"
        role="img"
        aria-label={
          `Gastaste ${formatUsd(String(spent), "whole")} de los ` +
          `${formatUsd(String(planned), "whole")} que el plan separó hasta hoy`
        }
      >
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-surface-2">
          {/* El hueco, tintado: entre lo gastado y el poste está el colchón.
              En gris se leía como "barra a medio llenar" —una carencia— y es
              justo lo contrario. */}
          {!over && (
            <div
              className="absolute inset-y-0 bg-heat-save/25"
              style={{ left: `${fill}%`, width: `${at - fill}%` }}
            />
          )}
          <div
            className={`absolute inset-y-0 left-0 rounded-full ${
              ahead ? "bg-heat-save" : "bg-heat-over"
            }`}
            style={{ width: `${Math.min(fill, at)}%` }}
          />
          {over && (
            <div
              className="absolute inset-y-0 bg-heat-over/45"
              style={{ left: `${at}%`, width: `${fill - at}%` }}
            />
          )}
        </div>
        {/* El poste del plan: sin él, el hueco es solo una barra a medio llenar. */}
        <span
          aria-hidden="true"
          className="absolute h-4 w-0.5 rounded-full bg-ink/45"
          style={{ left: `calc(${at}% - 1px)` }}
        />
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-3 text-fine font-medium text-ink-3">
        <span>
          gastaron <span className="font-tabular">{formatUsd(String(spent), "whole")}</span>
        </span>
        <span>
          el plan separó{" "}
          <span className="font-tabular">{formatUsd(String(planned), "whole")}</span>
        </span>
      </div>
    </div>
  );
}
