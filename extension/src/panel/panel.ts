// Popup entry: reads the active tab's listing and shows the backend's analysis.

import { MESSAGES } from "../content/messages";
import { analyze, ApiError } from "../shared/api";
import type { ExtractResult } from "../shared/types";
import { renderAnalysis, renderError, renderLoading } from "./render";
import "./panel.css";

async function extractFromActiveTab(): Promise<ExtractResult> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined) return { ok: false, error: MESSAGES.notListing };
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    const [injection] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => globalThis.__scamlyExtract?.(),
    });
    return injection?.result ?? { ok: false, error: MESSAGES.noData };
  } catch {
    // Chrome refuses to inject into its own pages (chrome://, the Web Store...).
    return { ok: false, error: MESSAGES.notListing };
  }
}

async function main(): Promise<void> {
  const root = document.getElementById("app");
  if (!root) return;
  renderLoading(root);

  const extracted = await extractFromActiveTab();
  if (!extracted.ok) {
    renderError(root, extracted.error);
    return;
  }
  try {
    renderAnalysis(root, await analyze(extracted.listing));
  } catch (error) {
    renderError(root, error instanceof ApiError ? error.message : "Error inesperado.");
  }
}

void main();
