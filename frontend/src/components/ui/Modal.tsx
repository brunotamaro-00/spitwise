import { X } from "lucide-react";
import { AnimatePresence, motion, useDragControls, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { DURATION } from "@/lib/motion";

// Spring gestual: comparte física con el drag-to-dismiss (el sheet que soltás
// vuelve con la misma inercia con la que entró). Deliberadamente fuera de la
// escala de motion — ver la nota de SPRING_* en lib/motion.ts.
const SPRING = { type: "spring", stiffness: 420, damping: 38 } as const;

/** Cuántos diálogos hay abiertos ahora mismo.
 *
 *  Existe porque los gestos globales de la app (hoy el pull-to-refresh) escuchan
 *  en `window` y no tienen forma de saber que el dedo está adentro de un sheet.
 *  Con la página en el tope —el caso normal— arrastrar el sheet hacia abajo para
 *  descartarlo superaba el umbral del pull y refetcheaba TODA la app, con
 *  vibración incluida, justo mientras el usuario cerraba un modal.
 *
 *  Contador y no booleano: el sheet de detalle abre el de edición encima, así
 *  que el cierre del primero no puede desbloquear el gesto mientras el segundo
 *  sigue arriba. Como todo diálogo de la app pasa por este componente, un
 *  diálogo nuevo hereda la protección sin tocar nada. */
let openDialogs = 0;

export function anyDialogOpen(): boolean {
  return openDialogs > 0;
}

/** Shell de diálogo: bottom sheet en mobile (slide-up con spring, drag para
 *  cerrar desde el handle/header, scroll-lock, focus trap) y diálogo centrado
 *  en desktop. Portal al body porque un ancestro con transform re-ancla `fixed`.
 *  El cierre siempre pasa por la animación de salida antes de desmontar. */
export default function Modal({ title, onClose, children, size = "md", locked = false }: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  size?: "sm" | "md";
  /** true mientras corre una mutación: bloquea cerrar por drag/overlay/Escape. */
  locked?: boolean;
}) {
  const [open, setOpen] = useState(true);
  const panelRef = useRef<HTMLDivElement>(null);
  const lockedRef = useRef(locked);
  lockedRef.current = locked;
  const dragControls = useDragControls();
  const reduced = useReducedMotion();
  // Sheet solo en mobile: en desktop el diálogo centrado no se arrastra.
  // Reactivo a resize/rotación: si cambia el breakpoint con el modal abierto,
  // el modo (drag, animación de salida) acompaña.
  const [isSheet, setIsSheet] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(max-width: 639px)").matches,
  );
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 639px)");
    const onChange = (e: MediaQueryListEvent) => setIsSheet(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  function requestClose() {
    if (lockedRef.current) return;
    setOpen(false); // AnimatePresence corre la salida y onExitComplete desmonta
  }

  // Scroll-lock del fondo + registro del diálogo abierto (ver `openDialogs`),
  // mientras el diálogo está montado. Van juntos a propósito: los dos describen
  // "el fondo no se toca", y separarlos abre la puerta a que un gesto global
  // quede escuchando sobre un modal abierto.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    openDialogs += 1;
    return () => {
      document.body.style.overflow = prev;
      openDialogs -= 1;
    };
  }, []);

  // Foco inicial adentro + trap de Tab + restaurar foco al cerrar.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    if (panel && !panel.contains(document.activeElement)) panel.focus();

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panelRef.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previouslyFocused?.focus?.();
    };
  }, []);

  return createPortal(
    <AnimatePresence onExitComplete={onClose}>
      {open && (
        <motion.div
          className="fixed inset-0 z-(--z-overlay) flex items-end justify-center bg-ink/40 backdrop-blur-[2px] sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: DURATION.quick }}
          onClick={requestClose}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            initial={isSheet ? { y: "100%" } : { opacity: 0, scale: 0.96, y: 8 }}
            animate={isSheet ? { y: 0 } : { opacity: 1, scale: 1, y: 0 }}
            exit={isSheet ? { y: "100%" } : { opacity: 0, scale: 0.97, y: 8 }}
            transition={reduced ? { duration: 0 } : SPRING}
            drag={isSheet ? "y" : false}
            dragControls={dragControls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.55 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 110 || info.velocity.y > 700) requestClose();
            }}
            className={`max-h-[92dvh] w-full ${size === "sm" ? "max-w-sm" : "max-w-md"} overflow-y-auto overscroll-contain rounded-t-3xl border border-border bg-surface p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] outline-none soft-pop sm:max-h-[85dvh] sm:rounded-2xl`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Handle + header: zona de arrastre del sheet en mobile. */}
            <div
              className="-mx-5 -mt-5 touch-none px-5 pt-3 sm:touch-auto sm:pt-5"
              onPointerDown={(e) => { if (isSheet) dragControls.start(e); }}
            >
              <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border-strong sm:hidden" aria-hidden="true" />
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl font-bold text-ink">{title}</h2>
                <button
                  aria-label="Cerrar"
                  className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-ring"
                  onClick={requestClose}
                >
                  <X size={20} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
