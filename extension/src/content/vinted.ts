// All Vinted-specific selectors and data paths live in this file.
// If the extension stops reading listings, check these first: the site changes over time.

import { asNumber, asString, at, parseJson } from "../shared/json";
import { MAX_TEXT_LENGTH, type ExtractResult, type Seller } from "../shared/types";
import { MESSAGES } from "./messages";

const JSON_LD = 'script[type="application/ld+json"]';
const RATING = ".web_ui__Rating__rating";
const PHOTOS = '[data-testid^="item-photo-"][data-testid$="--img"]';
const ITEM_ID = /^\/items\/(\d+)/;
const RATING_AVERAGE = /(\d+(?:[.,]\d+)?)\s+sobre\s+5/i;

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
      // Vinted does not show account age or sales on the item page.
      seller: readSeller(doc),
      // On Vinted every purchase goes through the platform's protected checkout and shipping.
      shipping_available: true,
      image_count: countPhotos(doc),
    },
  };
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
