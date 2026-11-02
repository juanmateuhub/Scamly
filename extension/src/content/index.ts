// Injected into the active tab only when the user clicks the icon (activeTab + scripting).
// It reads the open listing and runs one search for the same product from the user's own tab;
// the results go back to the popup, which sends titles and prices to the local backend.

import type { ExtractResult } from "../shared/types";
import { collectListing } from "./extract";

declare global {
  var __scamlyExtract: (() => Promise<ExtractResult>) | undefined;
}

globalThis.__scamlyExtract = () =>
  collectListing(document, new URL(location.href), new Date(), fetch.bind(globalThis));
