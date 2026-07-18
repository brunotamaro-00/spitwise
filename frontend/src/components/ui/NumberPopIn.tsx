import { useReducedMotion } from "motion/react";
import { useLayoutEffect, useRef } from "react";

import { cn } from "@/lib/cn";

/** Número con pop-in por carácter cuando su valor cambia: cada dígito re-entra
 *  con blur + slide vertical (patrón number-pop-in). Los últimos dos caracteres
 *  escalonan para animar los decimales. NO anima en el montaje inicial (el
 *  valor aparece estático); sólo en updates posteriores — pensado para montos
 *  que cambian tras cargar un gasto o saldar. Con reduced-motion no anima.
 *
 *  Es texto puro (sin relayout): usar junto con font-tabular. Distinto de
 *  `AnimatedUsd` (count-up continuo): este es un pop discreto en el update. */
export default function NumberPopIn({ value, className }: { value: string; className?: string }) {
  const groupRef = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const first = useRef(true);

  useLayoutEffect(() => {
    const g = groupRef.current;
    if (!g || reduced) return;
    // Sin pop en el primer render: el número aparece ya asentado.
    if (first.current) { first.current = false; return; }
    // Replay: quitar la clase, forzar reflow, re-agregar.
    g.classList.remove("is-animating");
    void g.offsetWidth;
    g.classList.add("is-animating");
  }, [value, reduced]);

  const chars = [...value];
  return (
    <span ref={groupRef} className={cn("t-digit-group", className)}>
      {/* Texto real para lectores de pantalla (leen el número una vez, no
          carácter por carácter) y para queries de test. */}
      <span className="sr-only">{value}</span>
      {chars.map((ch, i) => (
        <span
          key={`${i}-${ch}`}
          className="t-digit"
          aria-hidden="true"
          data-stagger={i === chars.length - 2 ? "1" : i === chars.length - 1 ? "2" : undefined}
        >
          {ch}
        </span>
      ))}
    </span>
  );
}
