// Injected into the active tab only when the user clicks the icon (activeTab + scripting).
// It reads the open listing and exposes one function; it never sends data anywhere itself.

import type { ExtractResult } from "../shared/types";
import { extractListing } from "./extract";

declare global {
  var __scamlyExtract: (() => ExtractResult) | undefined;
}

globalThis.__scamlyExtract = () => extractListing(document, new URL(location.href), new Date());
