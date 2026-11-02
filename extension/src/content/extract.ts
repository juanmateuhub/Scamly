import type { ExtractResult, Platform } from "../shared/types";
import { MESSAGES } from "./messages";
import { extractVinted } from "./vinted";
import { extractWallapop } from "./wallapop";

export { MESSAGES };

export function detectPlatform(url: URL): Platform | null {
  if (url.hostname.endsWith("wallapop.com") && url.pathname.startsWith("/item/")) return "wallapop";
  if (url.hostname.endsWith("vinted.es") && /^\/items\/\d+/.test(url.pathname)) return "vinted";
  return null;
}

export function extractListing(doc: Document, url: URL, now: Date): ExtractResult {
  switch (detectPlatform(url)) {
    case "wallapop":
      return extractWallapop(doc, url, now);
    case "vinted":
      return extractVinted(doc, url);
    case null:
      return { ok: false, error: MESSAGES.notListing };
  }
}
