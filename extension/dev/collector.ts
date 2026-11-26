// Dev tool, never shipped in the extension: collects real listings for the evaluation dataset
// with the extension's own extractor. Pasted into a Wallapop or Vinted tab (DevTools console or
// browser automation), it loads each listing in a hidden same-origin iframe, one at a time with
// a pause, and downloads the results as JSON. scripts/import_real.py anonymizes and stores them.

import { collectListing } from "../src/content/extract";
import type { ExtractResult } from "../src/shared/types";

type Collected = ExtractResult & { url: string };

declare global {
  var __scamlyCollect: ((urls: string[], delayMs?: number) => Promise<string>) | undefined;
}

const READY = 'script#__NEXT_DATA__, script[type="application/ld+json"]';
const LOAD_TIMEOUT_MS = 20_000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function loadInFrame(url: string): Promise<{ frame: HTMLIFrameElement; doc: Document }> {
  const frame = document.createElement("iframe");
  frame.style.cssText = "position:fixed;width:1280px;height:900px;left:-10000px;top:0";
  frame.src = url;
  document.body.append(frame);
  // Vinted renders its JSON-LD in the browser, so wait for the data, not just the load event.
  for (let waited = 0; waited < LOAD_TIMEOUT_MS; waited += 500) {
    await sleep(500);
    const doc = frame.contentDocument;
    if (doc?.querySelector(READY) && doc.readyState === "complete") {
      await sleep(1000); // late widgets such as the seller rating
      return { frame, doc };
    }
  }
  frame.remove();
  throw new Error("timeout");
}

async function collectOne(url: string): Promise<Collected> {
  try {
    const { frame, doc } = await loadInFrame(url);
    try {
      return { url, ...(await collectListing(doc, new URL(url), new Date(), fetch.bind(globalThis))) };
    } finally {
      frame.remove();
    }
  } catch (error) {
    return { url, ok: false, error: String(error) };
  }
}

function download(results: Collected[]): string {
  const name = `scamly-real-${location.hostname.replace("www.", "")}-${Date.now()}.json`;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([JSON.stringify(results)], { type: "application/json" }));
  link.download = name;
  link.click();
  return name;
}

globalThis.__scamlyCollect = async (urls, delayMs = 3000) => {
  const results: Collected[] = [];
  for (const url of urls) {
    results.push(await collectOne(url));
    await sleep(delayMs);
  }
  const ok = results.filter((r) => r.ok).length;
  return `${download(results)}: ${ok} ok, ${results.length - ok} errors`;
};
