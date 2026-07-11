import { beforeEach, describe, expect, it } from "vitest";

import { authHeader } from "./client";

describe("authHeader", () => {
  beforeEach(() => localStorage.clear());
  it("vacío sin token", () => {
    expect(authHeader()).toEqual({});
  });
  it("bearer con token", () => {
    localStorage.setItem("auth_token", "T");
    expect(authHeader()).toEqual({ Authorization: "Bearer T" });
  });
});
