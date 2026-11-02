import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderAnalysis, renderError, renderLoading } from "../src/panel/render";
import { analyze, ApiError } from "../src/shared/api";
import type { Analysis, ListingPayload } from "../src/shared/types";

const ANALYSIS: Analysis = {
  risk_score: 76,
  level: "rojo",
  confidence: 0.93,
  reasons: [
    {
      signal: "pago_fuera_app",
      kind: "risk",
      points: 36,
      intensity: 1,
      confidence: 0.9,
      message: "Pide pagar fuera de la plataforma, sin protección",
      evidence: "solo Bizum",
    },
    {
      signal: "envio_protegido",
      kind: "mitigator",
      points: -5.6,
      intensity: 1,
      confidence: 1,
      message: "Ofrece envío con protección de la app",
      evidence: "Envío disponible",
    },
  ],
  unavailable_signals: ["precio_anomalo"],
  text_analysis: "basico",
  analyzed_at: "2026-11-02T12:00:00Z",
  version: "0.1.0",
};

let root: HTMLElement;

beforeEach(() => {
  document.body.innerHTML = '<main id="app"></main>';
  root = document.getElementById("app") as HTMLElement;
});

describe("renderAnalysis", () => {
  it("shows score, level and reasons", () => {
    renderAnalysis(root, ANALYSIS);

    expect(root.querySelector(".score")?.textContent).toBe("76");
    expect(root.dataset.level).toBe("rojo");
    expect(root.textContent).toContain("Alto riesgo de estafa");
    expect(root.textContent).toContain("Pide pagar fuera de la plataforma, sin protección");
    expect(root.textContent).toContain("«solo Bizum»");
    expect(root.querySelectorAll(".reason")).toHaveLength(2);
    expect(root.querySelector(".reason.mitigator")?.textContent).toContain("−5,6");
  });

  it("explains degraded analysis and missing data", () => {
    renderAnalysis(root, ANALYSIS);

    expect(root.textContent).toContain("Análisis de texto básico");
    expect(root.textContent).toContain("sin precio de referencia");
    expect(root.textContent).toContain("Fiabilidad alta");
  });

  it("never accuses the seller", () => {
    renderAnalysis(root, ANALYSIS);

    expect(root.textContent).toContain("señales de riesgo");
    expect(root.textContent?.toLowerCase()).not.toContain("es una estafa");
  });

  it("renders listing text as text, never as HTML (XSS)", () => {
    const evil = {
      ...ANALYSIS,
      reasons: [{ ...ANALYSIS.reasons[0]!, evidence: '<img src=x onerror="alert(1)">' }],
    };

    renderAnalysis(root, evil);

    expect(root.querySelector("img")).toBeNull();
    expect(root.textContent).toContain('<img src=x onerror="alert(1)">');
  });

  it("shows a check for a mitigator with nothing to subtract (never +-0)", () => {
    const mitigator = { ...ANALYSIS.reasons[1]!, points: -0 };

    renderAnalysis(root, { ...ANALYSIS, risk_score: 0, level: "verde", reasons: [mitigator] });

    expect(root.querySelector(".reason.mitigator .points")?.textContent).toBe("✓");
    expect(root.textContent).not.toContain("-0");
  });

  it("shows a calm message when there are no reasons", () => {
    renderAnalysis(root, { ...ANALYSIS, risk_score: 3, level: "verde", reasons: [] });

    expect(root.textContent).toContain("Sin señales claras");
    expect(root.textContent).toContain("No hemos encontrado señales de riesgo");
  });
});

describe("renderLoading / renderError", () => {
  it("replaces previous content", () => {
    renderAnalysis(root, ANALYSIS);
    renderLoading(root);
    expect(root.textContent).toContain("Analizando");

    renderError(root, "Algo falló");
    expect(root.textContent).toContain("Algo falló");
    expect(root.querySelector(".score")).toBeNull();
  });
});

describe("analyze", () => {
  const listing = { platform: "wallapop", listing_id: "x" } as ListingPayload;

  it("posts the listing and returns the analysis", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(ANALYSIS), { status: 200 }));

    const result = await analyze(listing, fetchMock);

    expect(result.risk_score).toBe(76);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/analyze");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(listing);
  });

  it.each([
    [422, "rechazado"],
    [429, "Demasiadas"],
    [500, "error"],
  ])("maps HTTP %i to a Spanish message", async (status, text) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status }));

    await expect(analyze(listing, fetchMock)).rejects.toThrow(text);
  });

  it("explains when the backend is not running", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await analyze(listing, fetchMock).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toContain("localhost:8000");
  });
});
