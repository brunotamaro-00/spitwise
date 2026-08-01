import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  authCacheBuster,
  CACHE_SCHEMA_VERSION,
  invalidateLedger,
  QUERY_CACHE_KEY,
  resetSessionCache,
} from "./queryClient";

function jwtFor(sub: string): string {
  const payload = btoa(JSON.stringify({ sub, exp: 9999999999 }));
  return `hdr.${payload}.sig`;
}

describe("authCacheBuster", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("devuelve anon sin token", () => {
    expect(authCacheBuster()).toBe("anon");
  });

  it("lee el sub del JWT", () => {
    localStorage.setItem("auth_token", jwtFor("Katia"));
    expect(authCacheBuster()).toBe("katia");
  });

  it("CACHE_SCHEMA_VERSION es un string no vacío (buster de PersistQueryClient)", () => {
    expect(CACHE_SCHEMA_VERSION.length).toBeGreaterThan(0);
  });
});

/** El bug que esto cubre: /presupuesto se agregó con su propia queryKey y
 *  ninguna de las cinco mutaciones del ledger la invalidaba, así que cargar un
 *  gasto desde el FAB parado en esa página dejaba los números viejos en
 *  pantalla — con el ritmo real ya en 164/día, seguía diciendo 107. Cada
 *  pantalla derivada del ledger tiene que estar acá. */
describe("invalidateLedger", () => {
  function keysInvalidatedBy(): string[] {
    const qc = new QueryClient();
    const seen: string[] = [];
    vi.spyOn(qc, "invalidateQueries").mockImplementation((filters) => {
      seen.push(JSON.stringify(filters?.queryKey));
      return Promise.resolve();
    });
    invalidateLedger(qc);
    return seen;
  }

  it("invalida presupuesto, balance, movimientos, dashboard y ciudades", () => {
    const seen = keysInvalidatedBy();
    for (const key of ["movements", "balance", "dashboard", "city", "budget"]) {
      expect(seen).toContain(JSON.stringify([key]));
    }
  });

  it("no invalida el catálogo (no cambia al cargar un gasto)", () => {
    const seen = keysInvalidatedBy();
    for (const key of ["categories", "users", "stops", "me"]) {
      expect(seen).not.toContain(JSON.stringify([key]));
    }
  });
});

describe("resetSessionCache", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("borra la caché persistida en localStorage", async () => {
    localStorage.setItem(QUERY_CACHE_KEY, JSON.stringify({ clientState: {} }));
    await resetSessionCache();
    expect(localStorage.getItem(QUERY_CACHE_KEY)).toBeNull();
  });
});
