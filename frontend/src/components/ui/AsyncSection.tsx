import ErrorState from "./ErrorState";
import SkeletonReveal from "./SkeletonReveal";

/** Slot de sección asíncrona — EL patrón de estados de la app (system.md):
 *  loading → skeleton (cross-blur al llegar la data), error → ErrorState
 *  CONTENIDO en la sección con retry. Nunca un early-return de página completa:
 *  una caída de un query no debe esconder las secciones que sí cargaron.
 *  Nacido como `Slot` en Dashboard. */
export default function AsyncSection({ query, skeleton, errorTitle, errorDescription, children }: {
  query: { isError: boolean; data: unknown; refetch: () => unknown };
  skeleton: React.ReactNode;
  errorTitle?: string;
  errorDescription?: string;
  children: () => React.ReactNode;
}) {
  if (query.isError) {
    return (
      <ErrorState
        title={errorTitle}
        description={errorDescription}
        onRetry={() => void query.refetch()}
      />
    );
  }
  return <SkeletonReveal ready={!!query.data} skeleton={skeleton}>{children}</SkeletonReveal>;
}
