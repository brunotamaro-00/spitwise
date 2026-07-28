import { FlaskConical } from "lucide-react";

import { usePublicConfig } from "@/lib/useConfig";

/** Barra fina del deploy público (demo.spitwise.lat). Se monta arriba de todo,
 *  incluida /login, que es donde aterriza quien llega desde el CV.
 *
 *  `sticky` en vez de `fixed`: las páginas ya manejan su propio scroll y un
 *  overlay taparía el header del Layout. */
export default function DemoBanner() {
  const config = usePublicConfig();
  if (!config?.demo) return null;

  return (
    <div
      role="status"
      className="sticky top-0 z-30 flex items-center justify-center gap-2 border-b border-gold/40 bg-gold-bg px-4 py-1.5"
    >
      <FlaskConical size={12} strokeWidth={2} aria-hidden="true" className="shrink-0 text-ink-2" />
      <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-ink-2">
        Demo · datos ficticios
      </span>
      {config.andiamo_url ? (
        <a
          href={config.andiamo_url}
          className="text-[11px] font-bold uppercase tracking-[0.08em] text-brick underline underline-offset-2"
        >
          Ver Andiamo
        </a>
      ) : null}
    </div>
  );
}
