/**
 * API origin for PUBLIC EYE fetches.
 * Supports VITE_API_BASE (spec), VITE_API_BASE_URL (legacy), or prod default.
 * Dev: empty string → relative `/v1/*` via Vite proxy.
 */
const PROD_DEFAULT = "https://frame-2yxu.onrender.com";

export function getApiBase() {
  const a = import.meta.env.VITE_API_BASE;
  const b = import.meta.env.VITE_API_BASE_URL;
  for (const raw of [a, b]) {
    if (typeof raw === "string" && raw.trim()) {
      return raw.trim().replace(/\/$/, "");
    }
  }
  if (import.meta.env.PROD) return PROD_DEFAULT.replace(/\/$/, "");
  return "";
}
