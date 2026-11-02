import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { detectPlatform, extractListing, MESSAGES } from "../src/content/extract";
import { extractVinted } from "../src/content/vinted";
import { extractWallapop } from "../src/content/wallapop";

const WALLAPOP_URL = new URL("https://es.wallapop.com/item/ps5-nueva-precintada-1000000001");
const VINTED_URL = new URL("https://www.vinted.es/items/2000000002-nike-dunk-low-panda?referrer=catalog");
// registerDate in the fixture is 2025-11-02T00:00:00Z.
const NOW = new Date(Date.UTC(2025, 10, 5, 12));

function fixture(name: string): Document {
  const html = readFileSync(join(import.meta.dirname, "fixtures", name), "utf-8");
  return new DOMParser().parseFromString(html, "text/html");
}

function withJson(doc: Document, selector: string, edit: (data: Record<string, unknown>) => void): Document {
  const script = doc.querySelector(selector);
  const data = JSON.parse(script?.textContent ?? "{}") as Record<string, unknown>;
  edit(data);
  if (script) script.textContent = JSON.stringify(data);
  return doc;
}

describe("detectPlatform", () => {
  it.each([
    ["https://es.wallapop.com/item/ps5-1", "wallapop"],
    ["https://www.vinted.es/items/123-zapatillas", "vinted"],
    ["https://es.wallapop.com/search?keywords=ps5", null],
    ["https://www.vinted.es/catalog", null],
    ["https://example.com/item/1", null],
  ])("%s -> %s", (url, expected) => {
    expect(detectPlatform(new URL(url))).toBe(expected);
  });
});

describe("extractWallapop", () => {
  it("reads listing and seller data from __NEXT_DATA__", () => {
    const result = extractWallapop(fixture("wallapop-item.html"), WALLAPOP_URL, NOW);

    expect(result).toEqual({
      ok: true,
      listing: {
        platform: "wallapop",
        listing_id: "abc123xyz",
        title: "PS5 nueva precintada",
        description: "Me voy del país, solo Bizum, escríbeme por WhatsApp",
        price_eur: 180,
        category: "Consolas",
        condition: "Como nuevo",
        seller: { account_age_days: 3, ratings_count: 0, sales_count: 0 },
        shipping_available: false,
        image_count: 2,
      },
    });
  });

  it("includes the rating average only when there are ratings", () => {
    const doc = withJson(fixture("wallapop-item.html"), "#__NEXT_DATA__", (data) => {
      const seller = (data as { props: { pageProps: { itemSeller: { stats: Record<string, unknown> } } } })
        .props.pageProps.itemSeller;
      seller.stats = { ratings: { reviews: 40 }, ratingAverage: 4.5, counters: { sold: 25 } };
    });

    const result = extractWallapop(doc, WALLAPOP_URL, NOW);

    expect(result.ok && result.listing.seller).toEqual({
      account_age_days: 3,
      ratings_count: 40,
      ratings_avg: 4.5,
      sales_count: 25,
    });
  });

  it("asks to reload when __NEXT_DATA__ belongs to another page (client-side navigation)", () => {
    const otherUrl = new URL("https://es.wallapop.com/item/otro-anuncio-1000000009");

    expect(extractWallapop(fixture("wallapop-item.html"), otherUrl, NOW)).toEqual({
      ok: false,
      error: MESSAGES.stale,
    });
  });

  it("reports missing data instead of guessing", () => {
    const doc = fixture("wallapop-item.html");
    doc.querySelector("#__NEXT_DATA__")?.remove();

    expect(extractWallapop(doc, WALLAPOP_URL, NOW)).toEqual({ ok: false, error: MESSAGES.noData });
  });

  it("truncates very long texts to the backend limit", () => {
    const doc = withJson(fixture("wallapop-item.html"), "#__NEXT_DATA__", (data) => {
      const item = (data as { props: { pageProps: { item: Record<string, unknown> } } }).props.pageProps.item;
      item.description = { original: "a".repeat(6000) };
    });

    const result = extractWallapop(doc, WALLAPOP_URL, NOW);

    expect(result.ok && result.listing.description.length).toBe(5000);
  });
});

describe("extractVinted", () => {
  it("reads JSON-LD, the rating and the photo count", () => {
    const result = extractVinted(fixture("vinted-item.html"), VINTED_URL);

    expect(result).toEqual({
      ok: true,
      listing: {
        platform: "vinted",
        listing_id: "2000000002",
        title: "Nike Dunk Low Panda",
        description: "Nuevas en caja.\nTe paso el enlace de pago por correo.",
        price_eur: 35,
        category: "Hombre Zapatillas",
        condition: "Muy bueno",
        seller: { ratings_count: 12, ratings_avg: 4.5 },
        shipping_available: true,
        image_count: 3,
      },
    });
  });

  it("falls back to JSON-LD for the condition", () => {
    const doc = fixture("vinted-item.html");
    doc.querySelector('[data-testid="item-attributes-status"]')?.remove();

    const result = extractVinted(doc, VINTED_URL);

    expect(result.ok && result.listing.condition).toBeNull();
  });

  it("leaves the seller empty when no rating is shown", () => {
    const doc = fixture("vinted-item.html");
    doc.querySelector(".web_ui__Rating__rating")?.remove();

    const result = extractVinted(doc, VINTED_URL);

    expect(result.ok && result.listing.seller).toEqual({});
  });

  it("asks to reload when the JSON-LD belongs to another item", () => {
    const otherUrl = new URL("https://www.vinted.es/items/2000000099-otra-cosa");

    expect(extractVinted(fixture("vinted-item.html"), otherUrl)).toEqual({
      ok: false,
      error: MESSAGES.stale,
    });
  });
});

describe("extractListing", () => {
  it("rejects pages that are not a listing", () => {
    expect(extractListing(document, new URL("https://es.wallapop.com/"), NOW)).toEqual({
      ok: false,
      error: MESSAGES.notListing,
    });
  });
});
