import { useQuery } from "@tanstack/react-query";

import { getConfig, getPublicConfig } from "@/api/config";

/** URL pública de Andiamo para deep links; null si no está configurada.
 *  Cacheado para siempre (y persistido en localStorage): funciona offline. */
export function useAndiamoUrl(): string | null {
  const { data } = useQuery({ queryKey: ["config"], queryFn: getConfig, staleTime: Infinity });
  return data?.andiamo_url ?? null;
}

/** Config del deploy sin JWT — la usan el banner de demo y el CTA de /login,
 *  donde todavía no hay token. Query key propia: `["config"]` se persiste con
 *  buster por usuario y se descarta al desloguear, y este dato no depende de la
 *  sesión. */
export function usePublicConfig() {
  const { data } = useQuery({
    queryKey: ["public-config"],
    queryFn: getPublicConfig,
    staleTime: Infinity,
  });
  return data ?? null;
}
