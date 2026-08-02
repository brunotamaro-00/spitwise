import { ArrowRight, Compass } from "lucide-react";
import { Link } from "react-router-dom";

import { PageTitle } from "@/components/ui/Brand";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";

/** Catch-all para URLs desconocidas: mantiene el chrome (nav) y ofrece volver. */
export default function NotFound() {
  return (
    <div className="flex flex-col gap-5">
      <div className="animate-rise-in">
        <PageTitle>Página no encontrada</PageTitle>
      </div>
      <Card className="animate-rise-in stagger-1">
        <EmptyState
          icon={Compass}
          title="Esta página no existe"
          description="La dirección no coincide con ninguna sección de la app."
        />
        <div className="flex justify-center pb-8">
          <Link
            to="/"
            className="flex items-center gap-1 rounded-lg text-sm font-semibold text-brick transition-colors hover:text-brick-hover focus-ring"
          >
            Volver al dashboard
            <ArrowRight size={14} strokeWidth={2.25} aria-hidden="true" />
          </Link>
        </div>
      </Card>
    </div>
  );
}
