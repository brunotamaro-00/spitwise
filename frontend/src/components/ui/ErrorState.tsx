import { RefreshCw } from "lucide-react";

import Button from "./Button";
import Card from "./Card";

/** Estado de error con la llama de Spitwise y reintento. */
export default function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <Card className="relative overflow-hidden">
      <div className="spit-dots-ink pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="relative flex flex-col items-center gap-3 px-6 py-12 text-center">
        <img src="/brand/mark.png" alt="" width={52} height={52} className="object-contain opacity-90" />
        <p className="font-semibold text-ink">Algo salió mal</p>
        <p className="max-w-[30ch] text-sm text-ink-3">
          No pudimos cargar los datos. Revisá la conexión y probá de nuevo.
        </p>
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
