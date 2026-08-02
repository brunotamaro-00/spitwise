import { BAR_MAX_USD, bandGeometry, bandLevel } from "@/lib/budget";
import { formatUsd } from "@/lib/format";

/* Relleno = dónde estás, en la rampa de ritmo (`--color-heat-*`): teal si
   ahorrás, verde en plan, dorado pegado al techo, naranja pasado y rojo
   pasado fuerte. La escala es SIEMPRE la misma (USD 100/día), así que la
   altura del relleno se puede comparar entre filas — ese es el punto. */
const FILL = {
  save: "bg-heat-save",
  plan: "bg-heat-plan",
  edge: "bg-heat-edge",
  over: "bg-heat-over",
  far: "bg-heat-far",
} as const;

/** El excedente arriba del techo, más tenue: dice *cuánto* se pasaron sin
 *  competir con el relleno. Tailwind necesita la clase literal. */
const SPILL = {
  save: "bg-heat-save/40",
  plan: "bg-heat-plan/40",
  edge: "bg-heat-edge/45",
  over: "bg-heat-over/45",
  far: "bg-heat-far/45",
} as const;

const SIZES = {
  sm: { track: "h-2", fill: "h-1", tick: "h-3", cap: "w-1.5" },
  lg: { track: "h-3", fill: "h-1.5", tick: "h-[18px]", cap: "w-2" },
} as const;

/** El gasto diario contra la banda del plan, en una barra de eje fijo.
 *
 *  Cuatro capas: la pista (0 → USD 100/día, igual en toda la app), la **zona
 *  del plan** (min–max, tenue: "acá querés caer"), el **relleno** (lo que
 *  gastás por día, sólido y más fino, encima) y el **tope** cuando el gasto se
 *  sale del eje. La marca vertical del medio es el centro de la banda.
 *
 *  Sin números adentro a propósito: los pone la fila que la contiene, así el
 *  mismo componente sirve en el hero y en una lista de 27 renglones. El color
 *  nunca es el único canal — `aria-label` dice los tres números y al lado
 *  siempre va el `BandBadge` con la palabra.
 *
 *  `variant="hero"` la pinta monocroma en blanco para el gradiente del hero,
 *  donde ni los tokens de superficie ni la rampa tienen contraste. */
export default function BudgetBandBar({
  min,
  max,
  value,
  size = "sm",
  variant = "surface",
  label,
}: {
  min: string;
  max: string;
  /** null = todavía no hay ritmo (parada futura): solo se dibuja el plan. */
  value: string | null;
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
  const level = bandLevel(real, lo, hi);
  const s = SIZES[size];
  const hero = variant === "hero";
  const bandEnd = g.bandStart + g.bandWidth;
  const over = g.value != null && g.value > bandEnd;

  const scale = `escala de 0 a ${formatUsd(String(BAR_MAX_USD), "whole")} por día`;
  const aria =
    real == null
      ? `${label}: plan de ${formatUsd(min, "whole")} a ${formatUsd(max, "whole")} por día; todavía sin gasto (${scale})`
      : `${label}: gastás ${formatUsd(value!, "whole")} por día; el plan va de ` +
        `${formatUsd(min, "whole")} a ${formatUsd(max, "whole")} (${scale})`;

  return (
    <div className="relative flex items-center" role="img" aria-label={aria}>
      <div
        className={`relative w-full overflow-hidden rounded-full ${s.track} ${
          hero ? "bg-white/15" : "bg-surface-2"
        }`}
      >
        {/* Zona del plan: dónde se quiere caer. Tinte NEUTRO a propósito —
            desde que el relleno es una rampa semántica, un fondo teal competía
            con el paso "ahorrando" y se leía como parte del gasto. */}
        <div
          className={`absolute inset-y-0 rounded-full ${hero ? "bg-white/40" : "bg-ink/10"}`}
          style={{ left: `${g.bandStart}%`, width: `${g.bandWidth}%` }}
        />
        {/* Gasto real, encima y más fino para que la zona siga leyéndose.
            Cuando se pasa del techo, el excedente va aparte y más tenue: si
            fuera un solo bloque sólido, un +5% y un +70% se verían igual de
            "lleno" y la barra dejaría de decir *cuánto* se pasaron. */}
        {g.value != null && level != null && (
          <>
            <div
              className={`absolute left-0 top-1/2 -translate-y-1/2 ${s.fill} ${
                over ? "rounded-l-full" : "rounded-full"
              } ${hero ? "bg-white" : FILL[level]}`}
              style={{ width: `${Math.max(Math.min(g.value, bandEnd), 1.5)}%` }}
            />
            {over && (
              <div
                className={`absolute top-1/2 -translate-y-1/2 ${s.fill} ${
                  g.overCap ? "" : "rounded-r-full"
                } ${hero ? "bg-white/55" : SPILL[level]}`}
                style={{ left: `${bandEnd}%`, width: `${g.value - bandEnd}%` }}
              />
            )}
          </>
        )}
        {/* Tope: el gasto se salió del eje. Sin esta cuña, USD 100/día y
            USD 300/día se ven idénticos —relleno completo— y la barra vuelve a
            no decir cuánto. El badge de al lado pone el número exacto. */}
        {g.overCap && (
          <span
            aria-hidden="true"
            className={`absolute inset-y-0 right-0 border-l-2 ${s.cap} ${
              hero ? "border-white/30 bg-white" : "border-surface bg-heat-far"
            }`}
          />
        )}
      </div>
      {/* Postes del plan: piso, objetivo y techo, SIEMPRE arriba del relleno y
          sobresaliendo de la pista. Sin ellos, un gasto que se pasa tapa la
          zona del plan con su propio relleno y la barra deja de decir dónde
          estaba el límite — justo en el caso en que más importa. Con eje fijo
          además caen en lugares distintos según el plan de cada ciudad, que es
          la mitad de lo que hace comparable a la lista. */}
      {/* La key va por ROL y no por posición: con una banda de ancho cero
          (`min === max`, el caso de no-regresión del modelo de target único)
          los tres postes caen en el mismo %, y `key={at}` daba tres keys
          idénticas — React lo reporta como error y avisa que duplicar u omitir
          hijos es comportamiento no soportado. */}
      {[
        { role: "floor", at: g.bandStart, strong: false },
        { role: "center", at: g.center, strong: true },
        { role: "ceiling", at: bandEnd, strong: false },
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
