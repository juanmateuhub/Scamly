// Development only: same API call and rendering as the popup, fed from the URL hash
// (`#<url-encoded listing JSON>`), so the panel can be checked without loading the extension.

import { renderAnalysis, renderError, renderLoading } from "../src/panel/render";
import "../src/panel/panel.css";
import { analyze, ApiError } from "../src/shared/api";
import type { ListingPayload } from "../src/shared/types";

const SAMPLE: ListingPayload = {
  platform: "wallapop",
  listing_id: "preview-1",
  title: "PS5 nueva precintada",
  description: "Me voy del país, solo Bizum, escríbeme por WhatsApp",
  price_eur: 180,
  category: "Consolas",
  condition: "Como nuevo",
  seller: { account_age_days: 3, ratings_count: 0, sales_count: 0 },
  shipping_available: false,
  image_count: 2,
};

async function main(): Promise<void> {
  const root = document.getElementById("app");
  if (!root) return;
  const hash = decodeURIComponent(location.hash.slice(1));
  const listing = hash ? (JSON.parse(hash) as ListingPayload) : SAMPLE;
  renderLoading(root);
  try {
    renderAnalysis(root, await analyze(listing));
  } catch (error) {
    renderError(root, error instanceof ApiError ? error.message : String(error));
  }
}

void main();
