// All Vinted-specific selectors and data paths live in this file.
// If the extension stops reading listings, check these first: the site changes over time.

import { asNumber, asString, at, parseJson } from "../shared/json";
import {
  MAX_COMPARABLES,
  MAX_TEXT_LENGTH,
  type Comparable,
  type ExtractResult,
  type Seller,
} from "../shared/types";
import { MESSAGES } from "./messages";

const JSON_LD = 'script[type="application/ld+json"]';
const RATING = ".web_ui__Rating__rating";
const PHOTOS = '[data-testid^="item-photo-"][data-testid$="--img"]';
const CONDITION = '[data-testid="item-attributes-status"] [itemprop="status"]';
const ITEM_ID = /^\/items\/(\d+)/;
const RATING_AVERAGE = /(\d+(?:[.,]\d+)?)\s+sobre\s+5/i;

// Search results: the normal catalog page (server-rendered HTML), one request per analysis.
const SEARCH_PATH = "/catalog";
const CARD_LINK = '[data-testid^="product-item-id-"][data-testid$="--overlay-link"]';
const CARD_ID = /^product-item-id-(\d+)--overlay-link$/;

export function extractVinted(doc: Document, url: URL): ExtractResult {
  const id = ITEM_ID.exec(url.pathname)?.[1];
  const product = findProduct(doc);
  if (!id || product === undefined) return { ok: false, error: MESSAGES.noData };

  const offerUrl = asString(at(product, "offers", "url"));
  if (offerUrl && !new URL(offerUrl, url).pathname.startsWith(`/items/${id}`)) {
    return { ok: false, error: MESSAGES.stale };
  }

  const title = asString(at(product, "name"));
  const price = asNumber(at(product, "offers", "price"));
  if (!title || price === undefined) return { ok: false, error: MESSAGES.noData };

  return {
    ok: true,
    listing: {
      platform: "vinted",
      listing_id: id,
      title: title.slice(0, MAX_TEXT_LENGTH),
      description: (asString(at(product, "description")) ?? "").slice(0, MAX_TEXT_LENGTH),
      price_eur: price,
      category: asString(at(product, "category")) ?? null,
      condition: readCondition(doc, product),
      // Vinted does not show account age or sales on the item page.
      seller: readSeller(doc),
      // On Vinted every purchase goes through the platform's protected checkout and shipping.
      shipping_available: true,
      image_count: countPhotos(doc),
    },
  };
}

function readCondition(doc: Document, product: unknown): string | null {
  const shown = doc.querySelector(CONDITION)?.textContent?.trim();
  if (shown) return shown.slice(0, 60);
  // Fallback: JSON-LD only distinguishes new from used.
  return at(product, "offers", "itemCondition") === "NewCondition" ? "Nuevo" : null;
}

function countPhotos(doc: Document): number {
  // The page renders each photo more than once (mobile and desktop layouts).
  const ids = [...doc.querySelectorAll(PHOTOS)].map((photo) => photo.getAttribute("data-testid"));
  return new Set(ids).size;
}

function findProduct(doc: Document): unknown {
  for (const script of doc.querySelectorAll(JSON_LD)) {
    const data = parseJson(script.textContent);
    if (at(data, "@type") === "Product") return data;
  }
  return undefined;
}

function readSeller(doc: Document): Seller {
  const rating = doc.querySelector(RATING);
  if (!rating) return {};
  const result: Seller = {};
  const average = RATING_AVERAGE.exec(rating.getAttribute("aria-label") ?? "")?.[1];
  const count = /\d+/.exec(rating.textContent ?? "")?.[0];
  if (count !== undefined) result.ratings_count = Number(count);
  if (average !== undefined) result.ratings_avg = Number(average.replace(",", "."));
  return result;
}

/** "1.050,00 €" -> 1050 */
function parseEuros(text: string): number | undefined {
  const digits = text.replace(/[^\d,]/g, "").replace(",", ".");
  const value = Number.parseFloat(digits);
  return Number.isFinite(value) ? value : undefined;
}

export async function fetchVintedComparables(
  query: string,
  ownId: string,
  pageUrl: URL,
  fetchImpl: typeof fetch,
): Promise<Comparable[]> {
  const url = new URL(SEARCH_PATH, pageUrl.origin);
  url.searchParams.set("search_text", query.slice(0, 100));
  const response = await fetchImpl(url, { credentials: "include" });
  if (!response.ok) return [];
  const doc = new DOMParser().parseFromString(await response.text(), "text/html");

  const comparables: Comparable[] = [];
  for (const link of doc.querySelectorAll(CARD_LINK)) {
    const id = CARD_ID.exec(link.getAttribute("data-testid") ?? "")?.[1];
    // The link title reads "<title>, Marca: ..., Estado: ..., <price>".
    const title = (link.getAttribute("title") ?? "").split(", Marca:")[0]?.trim();
    const priceText = doc.querySelector(`[data-testid="product-item-id-${id}--price-text"]`)?.textContent;
    const price = priceText ? parseEuros(priceText) : undefined;
    if (!id || id === ownId || !title || price === undefined) continue;
    comparables.push({ title: title.slice(0, 300), price_eur: price });
  }
  return comparables.slice(0, MAX_COMPARABLES);
}
