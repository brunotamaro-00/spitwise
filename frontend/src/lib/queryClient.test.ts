import { afterEach, describe, expect, it, vi } from "vitest";

import { authCacheBuster, QUERY_CACHE_KEY, resetSessionCache } from "./queryClient";

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
