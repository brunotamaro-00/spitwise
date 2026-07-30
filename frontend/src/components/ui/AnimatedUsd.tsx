import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

import { formatUsd, type MoneyPrecision, parseMoney } from "@/lib/format";
import { EASE_SMOOTH_OUT } from "@/lib/motion";

/** Monto USD con count-up al montar/cambiar. Anima solo el texto (sin relayout:
 *  usar junto con font-tabular). Con reduced-motion muestra el valor directo.
 *  `precision` default "whole": todos los usos son cifras grandes (heros, ritmo). */
export default function AnimatedUsd({ value, className, precision = "whole" }: {
  value: string;
  className?: string;
  precision?: MoneyPrecision;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const last = useRef(0);
  const reduced = useReducedMotion();
  const target = parseMoney(value);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced) {
      el.textContent = formatUsd(String(target), precision);
      last.current = target;
      return;
    }
    const controls = animate(last.current, target, {
      duration: 0.7,
      ease: EASE_SMOOTH_OUT,
      onUpdate: (v) => { el.textContent = formatUsd(String(v), precision); },
    });
    last.current = target;
    return () => controls.stop();
  }, [target, reduced, precision]);

  // Contenido inicial = valor final: sin JS raro para lectores/SSR/tests.
  return <span ref={ref} className={className}>{formatUsd(String(target), precision)}</span>;
}
