import type { Comparable, ExtractResult, ListingPayload, Platform } from "../shared/types";
import { MESSAGES } from "./messages";
import { extractVinted, fetchVintedComparables } from "./vinted";
import { extractWallapop, fetchWallapopComparables, wallapopSearch } from "./wallapop";

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

function searchComparables(
  doc: Document,
  url: URL,
  listing: ListingPayload,
  fetchImpl: typeof fetch,
): Promise<Comparable[]> {
  if (listing.platform === "vinted") {
    return fetchVintedComparables(listing.title, listing.listing_id, url, fetchImpl);
  }
  const search = wallapopSearch(doc);
  return search ? fetchWallapopComparables(search, listing.listing_id, fetchImpl) : Promise.resolve([]);
}

/** The open listing plus the same product listed now (one search; skipped if it fails). */
export async function collectListing(
  doc: Document,
  url: URL,
  now: Date,
  fetchImpl: typeof fetch,
): Promise<ExtractResult> {
  const result = extractListing(doc, url, now);
  if (!result.ok) return result;
  let comparables: Comparable[] = [];
  try {
    comparables = await searchComparables(doc, url, result.listing, fetchImpl);
  } catch {
    // Price comparison is optional: the analysis continues with the reference table.
  }
  return { ok: true, listing: { ...result.listing, comparables } };
}
