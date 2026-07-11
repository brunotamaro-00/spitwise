import { X } from "lucide-react";
import { useEffect } from "react";
import { createPortal } from "react-dom";

/** Shell de diálogo: portal al body, overlay, panel sobrio, foco/Escape/safe-area.
 *  Portal al body porque un ancestro con transform re-ancla el `fixed`. */
export default function Modal({ title, onClose, children, size = "md" }: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  size?: "sm" | "md";
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-30 flex items-end justify-center bg-ink/40 backdrop-blur-[2px] sm:items-center"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`max-h-[92dvh] w-full ${size === "sm" ? "max-w-sm" : "max-w-md"} animate-fade-in overflow-y-auto rounded-t-3xl border border-border bg-surface p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] soft-pop sm:max-h-[85dvh] sm:rounded-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-ink">{title}</h2>
          <button
            aria-label="Cerrar"
            className="flex min-h-[40px] min-w-[40px] cursor-pointer items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brick/40"
            onClick={onClose}
          >
            <X size={20} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
