import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { anyDialogOpen } from "@/components/ui/Modal";

const TRIGGER_PX = 72;
const MAX_PX = 110;

/** Pull-to-refresh táctil (patrón de Andiamo): tirar hacia abajo con el scroll
 *  en el tope invalida todas las queries. Devuelve el estado para dibujar el
 *  indicador. Solo escucha touch: en desktop no hace nada. */
export function usePullToRefresh(): { pull: number; refreshing: boolean } {
  const qc = useQueryClient();
  const [pull, setPull] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);
  const pullRef = useRef(0);

  useEffect(() => {
    function onStart(e: TouchEvent) {
      // Con un sheet abierto el dedo está adentro del modal, no en la página:
      // el `scrollY <= 0` de abajo es cierto igual (el fondo está lockeado en el
      // tope), así que sin este corte arrastrar el sheet para cerrarlo pasaba el
      // umbral y refetcheaba toda la app. Ver `anyDialogOpen` en ui/Modal.
      startY.current =
        !anyDialogOpen() && window.scrollY <= 0 ? e.touches[0].clientY : null;
    }
    function onMove(e: TouchEvent) {
      if (startY.current == null) return;
      // Un diálogo puede abrirse a mitad del gesto (tocar una fila mientras se
      // arrastra): ahí el pull se cancela en vez de seguir acumulando.
      if (anyDialogOpen()) {
        startY.current = null;
        pullRef.current = 0;
        setPull(0);
        return;
      }
      const dy = e.touches[0].clientY - startY.current;
      const next = dy > 0 && window.scrollY <= 0 ? Math.min(dy * 0.5, MAX_PX) : 0;
      pullRef.current = next;
      setPull(next);
    }
    function onEnd() {
      const should = pullRef.current >= TRIGGER_PX;
      startY.current = null;
      pullRef.current = 0;
      setPull(0);
      if (!should) return;
      if ("vibrate" in navigator) navigator.vibrate?.(10);
      setRefreshing(true);
      void qc.invalidateQueries().finally(() => {
        // Mínimo visible: que el spinner no parpadee si la red es instantánea.
        setTimeout(() => setRefreshing(false), 500);
      });
    }
    window.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("touchmove", onMove, { passive: true });
    window.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onStart);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("touchend", onEnd);
    };
  }, [qc]);

  return { pull, refreshing };
}
