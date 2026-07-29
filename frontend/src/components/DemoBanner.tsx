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
      className="sticky top-0 z-30 flex flex-wrap items-center justify-center gap-x-2 gap-y-0.5 border-b-2 border-ink/15 bg-gold px-4 py-2 text-ink"
    >
      <FlaskConical size={13} strokeWidth={2.5} aria-hidden="true" className="shrink-0" />
      <span className="text-[12px] font-extrabold uppercase tracking-[0.08em]">Demo pública</span>
      <span className="text-[12px] font-semibold">datos inventados, no es un viaje real</span>
      {config.andiamo_url ? (
        <a
          href={config.andiamo_url}
          className="text-[12px] font-extrabold uppercase tracking-[0.08em] underline decoration-2 underline-offset-2"
        >
          Ver Andiamo ↗
        </a>
      ) : null}
    </div>
  );
}
