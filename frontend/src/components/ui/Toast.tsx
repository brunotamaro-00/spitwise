import { AlertCircle, CheckCircle2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

type Kind = "success" | "error";
type Toast = { id: number; kind: Kind; text: string };

const ToastContext = createContext<(kind: Kind, text: string) => void>(() => {});

/** Feedback de acciones: `const toast = useToast(); toast("success", "Gasto guardado")`. */
export function useToast() {
  return useContext(ToastContext);
}

const DURATION_MS = 2600;

/** Pills efímeras sobre la bottom nav, con la superficie espresso de marca.
 *  Una a la vez alcanza para esta app (acciones puntuales, no streams). */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const show = useCallback((kind: Kind, text: string) => {
    const id = nextId.current++;
    setToasts((ts) => [...ts.slice(-1), { id, kind, text }]);
    setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), DURATION_MS);
  }, []);

  const viewport = useMemo(
    () =>
      createPortal(
        <div
          aria-live="polite"
          className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+4.5rem)] z-50 flex flex-col items-center gap-2 px-4 lg:bottom-8"
        >
          <AnimatePresence>
            {toasts.map((t) => (
              <motion.div
                key={t.id}
                role="status"
                initial={{ opacity: 0, y: 14, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 500, damping: 32 }}
                className={`flex max-w-full items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold soft-pop ${
                  t.kind === "success" ? "espresso-panel" : "bg-danger text-white"
                }`}
              >
                {t.kind === "success" ? (
                  <CheckCircle2 size={17} strokeWidth={2.25} className="shrink-0 text-gold" aria-hidden="true" />
                ) : (
                  <AlertCircle size={17} strokeWidth={2.25} className="shrink-0" aria-hidden="true" />
                )}
                <span className="truncate">{t.text}</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>,
        document.body,
      ),
    [toasts],
  );

  return (
    <ToastContext.Provider value={show}>
      {children}
      {viewport}
    </ToastContext.Provider>
  );
}
