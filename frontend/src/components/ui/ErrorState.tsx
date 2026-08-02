import { RefreshCw } from "lucide-react";

import Button from "./Button";
import Card from "./Card";

/** Estado de error con la llama de Spitwise y reintento. El copy default cubre
 *  el caso genérico de red; pasá `title`/`description` cuando sepas qué falló
 *  — un error con causa conocida no debería sonar a "algo salió mal". */
export default function ErrorState({
  title = "Algo salió mal",
  description = "No pudimos cargar los datos. Revisá la conexión y probá de nuevo.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="relative overflow-hidden">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="relative flex flex-col items-center gap-3 px-6 py-12 text-center">
        <img src="/brand/mark-128.png" alt="" width={52} height={52} className="object-contain opacity-90" />
        <p className="font-semibold text-ink">{title}</p>
        <p className="max-w-[30ch] text-sm text-ink-3">{description}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry} className="mt-1">
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Reintentar
          </Button>
        )}
      </div>
    </Card>
  );
}
