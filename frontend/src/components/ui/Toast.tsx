import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { SPRING_POP } from "@/lib/motion";

type Kind = "success" | "error";
type Toast = { id: number; kind: Kind; text: string };

const ToastContext = createContext<(kind: Kind, text: string) => void>(() => {});

/** Feedback de acciones: `const toast = useToast(); toast("success", "Gasto guardado")`. */
export function useToast() {
  return useContext(ToastContext);
}

/** Duración por tipo. Un éxito se puede perder sin costo; un error hay que poder
 *  leerlo — y son los mensajes más largos ("No se pudo confirmar. Probá de
 *  nuevo."). Los 2,6s que había para ambos no alcanzaban para el de error. */
const DURATION_MS: Record<Kind, number> = { success: 4000, error: 8000 };
const MAX_VISIBLE = 3;

/** Pills efímeras sobre la bottom nav, con la superficie espresso de marca. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    const t = timers.current.get(id);
    if (t) { clearTimeout(t); timers.current.delete(id); }
    setToasts((ts) => ts.filter((x) => x.id !== id));
  }, []);

  const show = useCallback((kind: Kind, text: string) => {
    const id = nextId.current++;
    // Cola real: antes `ts.slice(-1)` dejaba UNO solo, así que un éxito posterior
    // se comía el error que el usuario todavía no había leído.
    setToasts((ts) => [...ts, { id, kind, text }].slice(-MAX_VISIBLE));
    timers.current.set(id, setTimeout(() => dismiss(id), DURATION_MS[kind]));
  }, [dismiss]);

  const viewport = useMemo(
    () =>
      createPortal(
        <div
          aria-live="polite"
          className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+4.5rem)] z-(--z-toast) flex flex-col items-center gap-2 px-4 lg:bottom-8"
        >
          <AnimatePresence>
            {toasts.map((t) => (
              <motion.div
                key={t.id}
                // Un error es una interrupción, no un status: `alert` lo hace
                // anunciar de inmediato en vez de esperar una pausa del lector.
                role={t.kind === "error" ? "alert" : "status"}
                initial={{ opacity: 0, y: 14, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.97 }}
                transition={SPRING_POP}
                // rounded-2xl y no rounded-full: un error puede ocupar dos o
                // tres líneas (ver el span de abajo) y la píldora deja de ser
                // una píldora. El éxito, de una línea, se ve igual.
                className={`pointer-events-auto flex max-w-full items-start gap-2 rounded-2xl py-2.5 pl-4 pr-2 text-sm font-semibold soft-pop ${
                  t.kind === "success" ? "espresso-panel" : "bg-danger text-white"
                }`}
              >
                {t.kind === "success" ? (
                  <CheckCircle2 size={17} strokeWidth={2.25} className="shrink-0 text-gold" aria-hidden="true" />
                ) : (
                  <AlertCircle size={17} strokeWidth={2.25} className="shrink-0" aria-hidden="true" />
                )}
                {/* Wrapea, no trunca. Los errores traen el `detail` real de la
                    API ("fx_rate para ARS debe ser el multiplicador a USD…",
                    83 chars) y a 402px `truncate` cortaba en ~48: se veía la
                    mitad justo del mensaje que dice qué corregir, que es todo
                    el motivo por el que `errorDetail` existe. `line-clamp-3`
                    pone el tope antes de que un detail largo tape la pantalla. */}
                <span className="min-w-0 flex-1 line-clamp-3 break-words">{t.text}</span>
                {/* Cerrar a mano: el contenedor es pointer-events-none y cada
                    toast lo reactiva, para poder sacarlo antes de que expire. */}
                <button
                  type="button"
                  aria-label="Cerrar aviso"
                  onClick={() => dismiss(t.id)}
                  // before:-inset-2.5 estira el hit area a 44×44 sin tocar el
                  // visual de 24px (los pseudo-elementos cuentan para el hit test).
                  className="focus-ring-inverse relative flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors before:absolute before:-inset-2.5 before:content-[''] hover:bg-white/15"
                >
                  <X size={14} strokeWidth={2.25} aria-hidden="true" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>,
        document.body,
      ),
    [toasts, dismiss],
  );

  return (
    <ToastContext.Provider value={show}>
      {children}
      {viewport}
    </ToastContext.Provider>
  );
}
