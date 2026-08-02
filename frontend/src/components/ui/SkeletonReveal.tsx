import { useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import { DURATION } from "@/lib/motion";

/** Envuelve el patrón `{data ? <Contenido/> : <Skeleton/>}` para que, cuando la
 *  data llega, el skeleton se desvanezca + difumine y el contenido entre
 *  enfocándose (cross-blur), en vez de un swap seco. El contenido va como
 *  render-prop porque sólo puede construirse con data presente.
 *
 *  Ciclo: loading (solo skeleton) → revealing (ambos apilados, cross-fade) →
 *  done (solo contenido). Con reduced-motion salta directo a done. */
export default function SkeletonReveal({ ready, skeleton, children }: {
  ready: boolean;
  skeleton: ReactNode;
  children: () => ReactNode;
}) {
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState<"loading" | "revealing" | "done">(ready ? "done" : "loading");
  const [lit, setLit] = useState(false);

  // Al llegar la data por primera vez: loading → revealing (o directo a done).
  useEffect(() => {
    if (!ready) { setPhase("loading"); setLit(false); return; }
    setPhase((p) => (p === "loading" ? (reduced ? "done" : "revealing") : p));
  }, [ready, reduced]);

  // Dispara el cross-fade un frame después de montar el stack.
  useEffect(() => {
    if (phase !== "revealing") return;
    const raf = requestAnimationFrame(() => setLit(true));
    return () => cancelAnimationFrame(raf);
  }, [phase]);

  // Asienta a `done` (desmonta el skeleton) al terminar el reveal (~--duration-slow).
  useEffect(() => {
    if (phase !== "revealing" || !lit) return;
    // +20ms de colchón sobre --duration-slow: desmontar el skeleton justo al
    // borde del tween cortaba el último frame del cross-blur.
    const t = setTimeout(() => setPhase("done"), DURATION.slow * 1000 + 20);
    return () => clearTimeout(t);
  }, [phase, lit]);

  // `aria-busy` + un status con texto: los skeletons son aria-hidden, así que sin
  // esto un lector de pantalla no oía nada mientras cargaba y el contenido
  // aparecía sin aviso.
  if (phase === "loading") {
    return (
      <div aria-busy="true">
        <span role="status" className="sr-only">Cargando…</span>
        {skeleton}
      </div>
    );
  }
  if (phase === "done") return <>{children()}</>;
  return (
    <div className={cn("t-skel relative", lit && "is-revealed")}>
      <div className="t-skel-content">{children()}</div>
      <div className="t-skel-skeleton" aria-hidden="true">{skeleton}</div>
    </div>
  );
}
