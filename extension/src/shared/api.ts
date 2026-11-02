import type { Analysis, ListingPayload } from "./types";

export const API_URL = "http://localhost:8000";
const TIMEOUT_MS = 15_000;

export class ApiError extends Error {}

const HTTP_MESSAGES: Record<number, string> = {
  422: "El servidor ha rechazado los datos del anuncio.",
  429: "Demasiadas consultas seguidas. Espera un minuto.",
};

export async function analyze(
  listing: ListingPayload,
  fetchImpl: typeof fetch = fetch,
): Promise<Analysis> {
  let response: Response;
  try {
    response = await fetchImpl(`${API_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(listing),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    throw new ApiError(
      "No se puede conectar con el servidor de Scamly. ¿Está arrancado en localhost:8000?",
    );
  }
  if (!response.ok) {
    throw new ApiError(HTTP_MESSAGES[response.status] ?? "El servidor ha devuelto un error.");
  }
  return (await response.json()) as Analysis;
}
