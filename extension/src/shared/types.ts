// Mirrors the backend contract (see "Contrato de la API" in CLAUDE.md).

export const PLATFORMS = ["wallapop", "vinted"] as const;

export type Platform = (typeof PLATFORMS)[number];

export function isPlatform(value: string): value is Platform {
  return (PLATFORMS as readonly string[]).includes(value);
}

export const MAX_TEXT_LENGTH = 5000;

export interface Seller {
  account_age_days?: number;
  ratings_count?: number;
  ratings_avg?: number;
  sales_count?: number;
}

export interface ListingPayload {
  platform: Platform;
  listing_id: string;
  title: string;
  description: string;
  price_eur: number;
  category: string | null;
  seller: Seller;
  shipping_available: boolean;
  image_count: number;
}

export type RiskLevel = "verde" | "amarillo" | "rojo";

export interface Reason {
  signal: string;
  points: number;
  intensity: number;
  confidence: number;
  message: string;
  evidence: string;
}

export interface Analysis {
  risk_score: number;
  level: RiskLevel;
  confidence: number;
  reasons: Reason[];
  unavailable_signals: string[];
  text_analysis: "llm" | "basico";
  analyzed_at: string;
  version: string;
}

export type ExtractResult = { ok: true; listing: ListingPayload } | { ok: false; error: string };
