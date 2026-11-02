// Popup rendering. Listing text comes from third-party pages, so everything is written with
// textContent (never innerHTML) to rule out XSS.

import type { Analysis, Reason, RiskLevel } from "../shared/types";

const LEVEL_TITLES: Record<RiskLevel, string> = {
  verde: "Sin señales claras",
  amarillo: "Revisa con cuidado",
  rojo: "Alto riesgo de estafa",
};

const UNAVAILABLE_NOTES: Record<string, string> = {
  precio_anomalo: "Producto sin precio de referencia: no se ha comparado el precio.",
  cuenta_nueva: "La antigüedad de la cuenta no es visible.",
  sin_historial: "El historial del vendedor no es visible.",
};

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "Fiabilidad alta";
  if (confidence >= 0.5) return "Fiabilidad media";
  return "Fiabilidad baja: faltan datos";
}

const NUMBER = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });

function formatPoints(reason: Reason): string {
  const value = NUMBER.format(Math.abs(reason.points));
  if (reason.kind === "risk") return `+${value}`;
  // A mitigator on a listing with no risk has nothing to subtract: show a check instead of −0.
  return value === "0" ? "✓" : `−${value}`;
}

function reasonItem(reason: Reason): HTMLLIElement {
  const item = el("li", reason.kind === "mitigator" ? "reason mitigator" : "reason");
  item.append(
    el("span", "points", formatPoints(reason)),
    el("span", "message", reason.message),
  );
  if (reason.evidence) item.append(el("span", "evidence", `«${reason.evidence}»`));
  return item;
}

export function renderAnalysis(root: HTMLElement, analysis: Analysis): void {
  root.replaceChildren();
  root.dataset.level = analysis.level;

  const header = el("header", "verdict");
  header.append(
    el("span", "score", String(analysis.risk_score)),
    el("span", "level", LEVEL_TITLES[analysis.level]),
    el("span", "confidence", confidenceLabel(analysis.confidence)),
  );
  root.append(header);

  if (analysis.reasons.length === 0) {
    root.append(el("p", "empty", "No hemos encontrado señales de riesgo en este anuncio."));
  } else {
    const list = el("ul", "reasons");
    list.append(...analysis.reasons.map(reasonItem));
    root.append(list);
  }

  const priceShown = analysis.reasons.some((reason) => reason.signal === "precio_anomalo");
  if (analysis.price_check && !priceShown) {
    const price = el("p", "price-check");
    price.append(
      el("span", "message", analysis.price_check.message),
      el("span", "evidence", analysis.price_check.evidence),
    );
    root.append(price);
  }

  const notes = analysis.unavailable_signals
    .map((signal) => UNAVAILABLE_NOTES[signal])
    .filter((note): note is string => note !== undefined);
  if (analysis.text_analysis === "basico") {
    notes.push("Análisis de texto básico (sin IA): reglas en español.");
  }
  if (notes.length > 0) {
    const list = el("ul", "notes");
    list.append(...notes.map((note) => el("li", "note", note)));
    root.append(list);
  }

  root.append(
    el(
      "p",
      "disclaimer",
      "Son señales de riesgo, no una acusación: un vendedor honrado también puede tenerlas.",
    ),
  );
}

export function renderLoading(root: HTMLElement): void {
  root.replaceChildren(el("p", "status", "Analizando el anuncio…"));
  delete root.dataset.level;
}

export function renderError(root: HTMLElement, message: string): void {
  root.replaceChildren(el("p", "status error", message));
  delete root.dataset.level;
}
