import { beforeEach, describe, expect, it } from "vitest";

import { authHeader, errorDetail, OFFLINE_MESSAGE } from "./client";

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

describe("errorDetail", () => {
  const FALLBACK = "No se pudo guardar. Revisá el monto.";

  it("usa el motivo de negocio que manda el backend", () => {
    const err = { response: { status: 422, data: { detail: "Parada desconocida: 'x'" } } };
    expect(errorDetail(err, FALLBACK)).toBe("Parada desconocida: 'x'");
  });

  // Los `msg` de Pydantic vienen en inglés: mostrarlos rompía el idioma de la
  // app ("Input should be greater than 0" adentro de un sheet en castellano).
  it("no muestra el texto crudo de un 422 de Pydantic", () => {
    const err = {
      response: {
        status: 422,
        data: { detail: [{ loc: ["body", "amount"], msg: "Input should be greater than 0" }] },
      },
    };
    expect(errorDetail(err, FALLBACK)).toBe(FALLBACK);
  });

  // Viajando, el error más probable no es el dato: es la señal. El fallback de
  // cada pantalla culpa al dato, así que la falla de transporte gana.
  it("un error sin respuesta se cuenta como falta de conexión", () => {
    expect(errorDetail({ code: "ERR_NETWORK" }, FALLBACK)).toBe(OFFLINE_MESSAGE);
  });
  it("un 5xx de gateway también es falta de conexión", () => {
    for (const status of [502, 503, 504]) {
      expect(errorDetail({ response: { status, data: {} } }, FALLBACK)).toBe(OFFLINE_MESSAGE);
    }
  });
  it("un 500 con motivo del backend NO se disfraza de offline", () => {
    const err = { response: { status: 500, data: { detail: "boom" } } };
    expect(errorDetail(err, FALLBACK)).toBe("boom");
  });
});
