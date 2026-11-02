import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { collectListing } from "../src/content/extract";
import { fetchVintedComparables } from "../src/content/vinted";
import { fetchWallapopComparables, wallapopSearch } from "../src/content/wallapop";

const FIXTURES = join(import.meta.dirname, "fixtures");
const WALLAPOP_URL = new URL("https://es.wallapop.com/item/ps5-nueva-precintada-1000000001");
const NOW = new Date(Date.UTC(2025, 10, 5, 12));

function html(name: string): Document {
  return new DOMParser().parseFromString(readFileSync(join(FIXTURES, name), "utf-8"), "text/html");
}

function jsonResponse(name: string): Response {
  return new Response(readFileSync(join(FIXTURES, name), "utf-8"), { status: 200 });
}

describe("wallapopSearch", () => {
  it("prefers the structured brand and model over the free-text title", () => {
    expect(wallapopSearch(html("wallapop-item.html"))).toEqual({ query: "Sony PS5", leafCategoryId: 9447 });
  });

  it("falls back to the title when there is no model", () => {
    const doc = html("wallapop-item.html");
    const script = doc.querySelector("#__NEXT_DATA__");
    const data = JSON.parse(script?.textContent ?? "{}");
    delete data.props.pageProps.item.typeAttributes;
    if (script) script.textContent = JSON.stringify(data);

    expect(wallapopSearch(doc)?.query).toBe("PS5 nueva precintada");
  });
});

describe("fetchWallapopComparables", () => {
  it("does one search and keeps priced listings of the same category, except the listing itself", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse("wallapop-search.json"));

    const result = await fetchWallapopComparables(
      { query: "Apple iPhone 17", leafCategoryId: 9447 },
      "own111",
      fetchMock,
    );

    expect(result).toEqual([
      { title: "iPhone 17 256GB", price_eur: 760 },
      { title: "iPhone 17 Pro 512gb", price_eur: 949.99 },
      { title: "iPhone 17 verde", price_eur: 680 },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(url.searchParams.get("keywords")).toBe("Apple iPhone 17");
    expect((init.headers as Record<string, string>)["X-DeviceOS"]).toBe("0");
    expect(init.credentials).toBe("omit");
  });
});

describe("fetchVintedComparables", () => {
  it("reads titles and Spanish-formatted prices from the search page", async () => {
    const page = readFileSync(join(FIXTURES, "vinted-search.html"), "utf-8");
    const fetchMock = vi.fn().mockResolvedValue(new Response(page, { status: 200 }));

    const result = await fetchVintedComparables(
      "Nike Dunk Low Panda",
      "2000000002",
      new URL("https://www.vinted.es/items/2000000002-own"),
      fetchMock,
    );

    expect(result).toEqual([
      { title: "Nike Dunk Low Panda 42", price_eur: 65 },
      { title: "Dunk Low Retro Panda", price_eur: 1050 },
    ]);
    const [url] = fetchMock.mock.calls[0] as [URL];
    expect(url.toString()).toBe("https://www.vinted.es/catalog?search_text=Nike+Dunk+Low+Panda");
  });
});

describe("collectListing", () => {
  it("adds comparables to the extracted listing", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse("wallapop-search.json"));

    const result = await collectListing(html("wallapop-item.html"), WALLAPOP_URL, NOW, fetchMock);

    // The open listing (abc123xyz) is not among the results, so all 4 priced same-category items stay.
    expect(result.ok && result.listing.comparables).toHaveLength(4);
  });

  it("still analyses the listing when the search fails", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("blocked"));

    const result = await collectListing(html("wallapop-item.html"), WALLAPOP_URL, NOW, fetchMock);

    expect(result.ok && result.listing.comparables).toEqual([]);
  });
});
