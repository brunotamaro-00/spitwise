import { useQuery } from "@tanstack/react-query";

import { getConfig } from "@/api/config";

/** URL pública de Andiamo para deep links; null si no está configurada.
 *  Cacheado para siempre (y persistido en localStorage): funciona offline. */
export function useAndiamoUrl(): string | null {
  const { data } = useQuery({ queryKey: ["config"], queryFn: getConfig, staleTime: Infinity });
  return data?.andiamo_url ?? null;
}
