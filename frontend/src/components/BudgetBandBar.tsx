import { bandGeometry, bandTone } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import type { BandPosition } from "@/types";

/* Relleno = dónde estás. Nunca rojo: esto sirve para decidir si salen a comer,
   no es una alarma. "En plan" va en brick (el color de los datos propios en
   toda la app) porque estar adentro del rango es lo esperado, no un logro. */
const FILL = {
  teal: "bg-accent-teal",
  neutral: "bg-brick",
  amber: "bg-accent-amber-solid",
} as const;

const SIZES = {
  sm: { track: "h-2", fill: "h-1", tick: "h-3" },
  lg: { track: "h-3", fill: "h-1.5", tick: "h-[18px]" },
} as const;

/** La banda del plan contra el gasto real, en una barra.
 *
 *  Tres capas: la pista (el rango de escala), la **zona del plan** (min–max,
 *  tenue: "acá querés caer") y el **relleno** (lo que gastás por día, sólido y
 *  más fino, encima). La marca vertical es el centro de la banda, el objetivo.
 *
 *  Sin números adentro a propósito: los pone la fila que la contiene, así el
 *  mismo componente sirve en el hero y en una lista de 27 renglones. El color
 *  nunca es el único canal — `aria-label` dice los tres números y al lado
 *  siempre va el `BandBadge` con la palabra.
 *
 *  `variant="hero"` la pinta monocroma en blanco para el gradiente del hero,
 *  donde los tokens de superficie no tienen contraste. */
export default function BudgetBandBar({
  min,
  max,
  value,
  position,
  size = "sm",
  variant = "surface",
  label,
}: {
  min: string;
  max: string;
  /** null = todavía no hay ritmo (parada futura): solo se dibuja el plan. */
  value: string | null;
  position: BandPosition | null;
  size?: keyof typeof SIZES;
  variant?: "surface" | "hero";
  /** Nombre de la parada, para la descripción accesible. */
  label: string;
}) {
  const lo = Number(min);
  const hi = Number(max);
  const real = value == null ? null : Number(value);
  // Mismo criterio que `budget._band` en el backend: un piso <= 0 o una banda
  // invertida no es un plan. `Number("")` da 0, así que el chequeo tiene que
  // ser `> 0` y no `isFinite`, o un plan vacío dibujaba una barra degenerada.
  if (!(lo > 0) || !(hi >= lo)) return null;

  const g = bandGeometry(lo, hi, real);
  const s = SIZES[size];
  const hero = variant === "hero";
  const bandEnd = g.bandStart + g.bandWidth;
  const over = g.value != null && g.value > bandEnd;

  const aria =
    real == null
      ? `${label}: plan de ${formatUsd(min, "whole")} a ${formatUsd(max, "whole")} por día; todavía sin gasto`
      : `${label}: gastás ${formatUsd(value!, "whole")} por día; el plan va de ` +
        `${formatUsd(min, "whole")} a ${formatUsd(max, "whole")}`;

  return (
    <div className="relative flex items-center" role="img" aria-label={aria}>
      <div
        className={`relative w-full overflow-hidden rounded-full ${s.track} ${
          hero ? "bg-white/15" : "bg-surface-2"
        }`}
      >
        {/* Zona del plan: dónde se quiere caer. */}
        <div
          className={`absolute inset-y-0 rounded-full ${hero ? "bg-white/40" : "bg-accent-teal-bg"}`}
          style={{ left: `${g.bandStart}%`, width: `${g.bandWidth}%` }}
        />
        {/* Gasto real, encima y más fino para que la zona siga leyéndose.
            Cuando se pasa del techo, el excedente va aparte y más tenue: si
            fuera un solo bloque sólido, un +5% y un +70% se verían igual de
            "lleno" y la barra dejaría de decir *cuánto* se pasaron. */}
        {g.value != null && (
          <>
            <div
              className={`absolute left-0 top-1/2 -translate-y-1/2 ${s.fill} ${
                over ? "rounded-l-full" : "rounded-full"
              } ${hero ? "bg-white" : FILL[bandTone(position)]}`}
              style={{ width: `${Math.max(Math.min(g.value, bandEnd), 1.5)}%` }}
            />
            {over && (
              <div
                className={`absolute top-1/2 -translate-y-1/2 rounded-r-full ${s.fill} ${
                  hero ? "bg-white/55" : "bg-accent-amber-solid/45"
                }`}
                style={{ left: `${bandEnd}%`, width: `${g.value - bandEnd}%` }}
              />
            )}
          </>
        )}
      </div>
      {/* Postes del plan: piso, objetivo y techo, SIEMPRE arriba del relleno y
          sobresaliendo de la pista. Sin ellos, un gasto que se pasa tapa la
          zona del plan con su propio relleno y la barra deja de decir dónde
          estaba el límite — justo en el caso en que más importa. */}
      {/* La key va por ROL y no por posición: con una banda de ancho cero
          (`min === max`, el caso de no-regresión del modelo de target único)
          los tres postes caen en el mismo %, y `key={at}` daba tres keys
          idénticas — React lo reporta como error y avisa que duplicar u omitir
          hijos es comportamiento no soportado. */}
      {[
        { role: "floor", at: g.bandStart, strong: false },
        { role: "center", at: g.center, strong: true },
        { role: "ceiling", at: g.bandStart + g.bandWidth, strong: false },
      ].map(({ role, at, strong }) => (
        <span
          key={role}
          aria-hidden="true"
          className={`absolute w-0.5 rounded-full ${s.tick} ${
            hero
              ? strong ? "bg-white" : "bg-white/60"
              : strong ? "bg-ink/45" : "bg-ink/20"
          }`}
          style={{ left: `calc(${at}% - 1px)` }}
        />
      ))}
    </div>
  );
}
