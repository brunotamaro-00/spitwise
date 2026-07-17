import { useQuery } from "@tanstack/react-query";

import { getMe } from "@/api/users";

/** Usuario actual. Siempre revalida al montar: no reutilizar identidad de otra sesión. */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    staleTime: 0,
    refetchOnMount: "always",
  });
}
