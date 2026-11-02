// All Wallapop-specific selectors and data paths live in this file.
// If the extension stops reading listings, check these first: the site changes over time.

import { asNumber, asString, at, parseJson } from "../shared/json";
import { MAX_TEXT_LENGTH, type ExtractResult, type Seller } from "../shared/types";
import { MESSAGES } from "./messages";

const NEXT_DATA = "script#__NEXT_DATA__";
const DAY_MS = 86_400_000;

export function extractWallapop(doc: Document, url: URL, now: Date): ExtractResult {
  const pageProps = at(parseJson(doc.querySelector(NEXT_DATA)?.textContent), "props", "pageProps");
  const item = at(pageProps, "item");
  const sellerData = at(pageProps, "itemSeller");
  if (item === undefined) return { ok: false, error: MESSAGES.noData };

  // Next.js keeps the first page's __NEXT_DATA__ after client-side navigation.
  const slug = url.pathname.split("/").filter(Boolean).at(-1);
  if (asString(at(item, "slug")) !== slug) return { ok: false, error: MESSAGES.stale };

  const id = asString(at(item, "id"));
  const title = asString(at(item, "title", "original"));
  const price = asNumber(at(item, "price", "cash", "amount"));
  if (!id || !title || price === undefined) return { ok: false, error: MESSAGES.noData };

  const taxonomies = at(item, "taxonomies");
  const lastTaxonomy = Array.isArray(taxonomies) ? at(taxonomies.at(-1), "name") : undefined;
  const images = at(item, "images");

  return {
    ok: true,
    listing: {
      platform: "wallapop",
      listing_id: id,
      title: title.slice(0, MAX_TEXT_LENGTH),
      description: (asString(at(item, "description", "original")) ?? "").slice(0, MAX_TEXT_LENGTH),
      price_eur: price,
      category: asString(lastTaxonomy) ?? null,
      seller: readSeller(sellerData, now),
      shipping_available:
        at(item, "shipping", "isItemShippable") === true &&
        at(item, "shipping", "isShippingAllowedByUser") === true,
      image_count: Array.isArray(images) ? images.length : 0,
    },
  };
}

function readSeller(seller: unknown, now: Date): Seller {
  const result: Seller = {};
  const registered = asNumber(at(seller, "registerDate"));
  if (registered !== undefined) {
    result.account_age_days = Math.max(0, Math.floor((now.getTime() - registered) / DAY_MS));
  }
  const ratings = asNumber(at(seller, "stats", "ratings", "reviews"));
  if (ratings !== undefined) {
    result.ratings_count = ratings;
    const average = asNumber(at(seller, "stats", "ratingAverage"));
    // Wallapop reports 0 as the average when there are no ratings yet.
    if (ratings > 0 && average !== undefined) result.ratings_avg = average;
  }
  const sold = asNumber(at(seller, "stats", "counters", "sold"));
  if (sold !== undefined) result.sales_count = sold;
  return result;
}
