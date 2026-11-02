import { describe, expect, it } from "vitest";

import { isPlatform } from "../src/shared/types";

describe("isPlatform", () => {
  it("accepts supported platforms", () => {
    expect(isPlatform("wallapop")).toBe(true);
    expect(isPlatform("vinted")).toBe(true);
  });

  it("rejects unknown platforms", () => {
    expect(isPlatform("ebay")).toBe(false);
  });
});
