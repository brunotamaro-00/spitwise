import { useEffect, useLayoutEffect, useRef } from "react";

/** Grupo de botones exclusivos (segmented control) con pill deslizante: el
 *  pill blanco se desliza entre opciones (patrón tabs-sliding). JS mide
 *  offsetLeft/offsetWidth del botón activo y los escribe inline; el CSS
 *  (.seg-pill) tweenea. En primer paint y resize se posiciona sin animar
 *  (snap). El borde va como ring-inset para que offsetLeft (border-box) y
 *  el pill (left:0 padding-box) compartan origen.
 *
 *  A11y: es opción ÚNICA, así que va como `radiogroup`/`radio` y no con
 *  `aria-pressed` (que describe toggles independientes: un lector anunciaba
 *  "Bruno, pressed / Katia, not pressed" como si se pudieran prender las dos).
 *  Eso obliga al contrato de teclado del patrón: un solo tab-stop (el activo) y
 *  flechas para moverse. */
export default function Segmented({ options, value, onChange, labelledBy }: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  labelledBy?: string;
}) {
  const pillRef = useRef<HTMLSpanElement>(null);
  const btnRefs = useRef(new Map<string, HTMLButtonElement>());
  const mounted = useRef(false);

  function place(animate: boolean) {
    const pill = pillRef.current;
    const btn = btnRefs.current.get(value);
    if (!pill || !btn) return;
    const apply = () => {
      pill.style.transform = `translateX(${btn.offsetLeft}px)`;
      pill.style.width = `${btn.offsetWidth}px`;
    };
    if (animate) {
      apply();
    } else {
      const prev = pill.style.transition;
      pill.style.transition = "none";
      apply();
      void pill.offsetWidth; // fuerza reflow para que el próximo cambio anime
      pill.style.transition = prev;
    }
  }

  // Snap al montar; anima en cambios de `value` posteriores (click o externo).
  useLayoutEffect(() => {
    place(mounted.current);
    mounted.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Reposicionar sin animar en resize (usa el `value` vigente vía ref indirecto).
  const placeRef = useRef(place);
  placeRef.current = place;
  useEffect(() => {
    const onResize = () => placeRef.current(false);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Flechas: mueve la selección al vecino y le lleva el foco (patrón radiogroup).
  function onKeyDown(e: React.KeyboardEvent, i: number) {
    const delta = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1
      : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const next = options[(i + delta + options.length) % options.length];
    onChange(next.value);
    btnRefs.current.get(next.value)?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-labelledby={labelledBy}
      className="relative flex rounded-lg bg-surface-2 p-0.5 ring-1 ring-inset ring-border"
    >
      {/* rounded-md deliberado: radio concéntrico (contenedor lg 8px − inset 2px = 6px). */}
      <span
        ref={pillRef}
        aria-hidden="true"
        className="seg-pill pointer-events-none absolute bottom-0.5 left-0 top-0.5 w-0 rounded-md bg-surface soft-card"
      />
      {options.map((o, i) => {
        const active = value === o.value;
        return (
          <button
            key={o.value}
            ref={(el) => { if (el) btnRefs.current.set(o.value, el); }}
            type="button"
            role="radio"
            aria-checked={active}
            // Un solo tab-stop por grupo: Tab entra y sale, las flechas navegan.
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`relative z-10 min-h-[36px] flex-1 cursor-pointer rounded-md px-2 text-note font-semibold transition-colors focus-ring ${
              active ? "text-ink" : "text-ink-3 hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
