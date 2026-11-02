// All Wallapop-specific selectors and data paths live in this file.
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

const NEXT_DATA = "script#__NEXT_DATA__";
const DAY_MS = 86_400_000;

// Search API used by the website itself (undocumented: may change without notice).
// The user decided to use it for price comparison: one request per analysis, started by a click.
const SEARCH_URL = "https://api.wallapop.com/api/v3/search/section";
const SEARCH_PARAMS = {
  source: "search_box",
  order_by: "most_relevance",
  search_section: "organic_search_results",
  section_type: "keyword_search",
  latitude: "40.4168", // Madrid: country-wide relevance, not the user's location
  longitude: "-3.7038",
  search_country: "ES",
};
const SEARCH_HEADERS = { "X-DeviceOS": "0" }; // the web client; without it the API answers 403

function pageItem(doc: Document): unknown {
  return at(parseJson(doc.querySelector(NEXT_DATA)?.textContent), "props", "pageProps", "item");
}

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
      condition: asString(at(item, "typeAttributes", "condition", "text")) ?? null,
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
  // counters.reviews is the count shown on the page ("4,9 (76)"). Beware: stats.ratings.reviews
  // is the score as a percentage (98 = 4,9 stars), not a count.
  const ratings = asNumber(at(seller, "stats", "counters", "reviews"));
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

export interface WallapopSearch {
  query: string;
  leafCategoryId: number | undefined;
}

/** Search terms for the same product: structured brand + model if present, else the title. */
export function wallapopSearch(doc: Document): WallapopSearch | undefined {
  const item = pageItem(doc);
  const title = asString(at(item, "title", "original"));
  const model = asString(at(item, "typeAttributes", "model", "value")) ?? asString(at(item, "model"));
  const brand = asString(at(item, "typeAttributes", "brand", "value")) ?? asString(at(item, "brand"));
  const taxonomies = at(item, "taxonomies");
  const leafCategoryId = Array.isArray(taxonomies) ? asNumber(at(taxonomies.at(-1), "id")) : undefined;

  let query = title;
  if (model) {
    query = brand && !model.toLowerCase().includes(brand.toLowerCase()) ? `${brand} ${model}` : model;
  }
  return query ? { query: query.slice(0, 100), leafCategoryId } : undefined;
}

/** One search; keeps priced listings of the same leaf category (drops cases, boxes...). */
export async function fetchWallapopComparables(
  search: WallapopSearch,
  ownId: string,
  fetchImpl: typeof fetch,
): Promise<Comparable[]> {
  const url = new URL(SEARCH_URL);
  url.searchParams.set("keywords", search.query);
  for (const [key, value] of Object.entries(SEARCH_PARAMS)) url.searchParams.set(key, value);

  const response = await fetchImpl(url, { credentials: "omit", headers: SEARCH_HEADERS });
  if (!response.ok) return [];
  const items = at(await response.json(), "data", "section", "items");
  if (!Array.isArray(items)) return [];

  const comparables: Comparable[] = [];
  for (const item of items) {
    const title = asString(at(item, "title"));
    const price = asNumber(at(item, "price", "amount"));
    const taxonomy = at(item, "taxonomy");
    const leaf = Array.isArray(taxonomy) ? asNumber(at(taxonomy.at(-1), "id")) : undefined;
    if (!title || price === undefined || at(item, "id") === ownId) continue;
    if (search.leafCategoryId !== undefined && leaf !== search.leafCategoryId) continue;
    comparables.push({ title: title.slice(0, 300), price_eur: price });
  }
  return comparables.slice(0, MAX_COMPARABLES);
}
