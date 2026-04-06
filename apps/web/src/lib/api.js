import { getApiBase } from "../apiBase.js";

const base = () => getApiBase();

async function jsonOrThrow(res) {
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text || "Invalid response" };
  }
  if (!res.ok) {
    const d = data.detail;
    let msg;
    if (typeof d === "string") msg = d;
    else if (res.status >= 500)
      msg = "Server error. Try again in a moment.";
    else msg = "Request could not be completed. Check your input and try again.";
    throw new Error(msg);
  }
  return data;
}

export async function fetchRecentReceipts(limit = 20) {
  const res = await fetch(`${base()}/v1/receipts/recent?limit=${limit}`);
  const data = await jsonOrThrow(res);
  return data.receipts || [];
}

export async function fetchReceipt(receiptId) {
  const res = await fetch(`${base()}/r/${encodeURIComponent(receiptId)}`);
  if (res.status === 404) return null;
  return jsonOrThrow(res);
}

/**
 * Investigation entity profile (Postgres). Returns { status: "pending", entity_slug } until
 * background persistence has created a row; then { status: "ready", ...profile }.
 */
export async function fetchEntityProfile(slug) {
  const s = String(slug || "").trim();
  if (!s) return null;
  const tryPaths = [`${base()}/api/entity/${encodeURIComponent(s)}`, `${base()}/v1/entity/${encodeURIComponent(s)}`];
  let lastErr;
  for (const url of tryPaths) {
    const res = await fetch(url);
    const text = await res.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: text || "Invalid response" };
    }
    if (res.ok) return data;
    if (res.status === 404) {
      lastErr = new Error("Not found");
      continue;
    }
    const d = data.detail;
    let msg;
    if (typeof d === "string") msg = d;
    else if (res.status >= 500)
      msg = "Server error. Try again in a moment.";
    else msg = "Request could not be completed. Check your input and try again.";
    throw new Error(msg);
  }
  return { status: "pending", entity_slug: s };
}

export async function analyzeArticle(url) {
  const res = await fetch(`${base()}/v1/analyze-article`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return jsonOrThrow(res);
}

export function rawJsonUrl(receiptId) {
  return `${base()}/r/${encodeURIComponent(receiptId)}`;
}

/** @returns {Promise<object|null>} null if 404 */
export async function getCoalitionMap(receiptId) {
  const res = await fetch(`${base()}/v1/coalition-map/${encodeURIComponent(receiptId)}`);
  if (res.status === 404) return null;
  return jsonOrThrow(res);
}

/** Enqueue or return existing. @returns {Promise<object|null>} full map if 200, null if 202 queued */
/** @param {Record<string, unknown>} params */
export async function fetchProportionalityWithGeo(params) {
  const u = new URL(`${base()}/v1/proportionality`);
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue;
    u.searchParams.set(k, String(v));
  }
  const res = await fetch(u.toString());
  if (!res.ok) return null;
  const data = await res.json();
  return data?.proportionality ?? null;
}

export async function postCoalitionMap(receiptId) {
  const res = await fetch(`${base()}/v1/coalition-map`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ receipt_id: receiptId }),
  });
  if (res.status === 200) return await res.json();
  if (res.status === 202) return null;
  return jsonOrThrow(res);
}
