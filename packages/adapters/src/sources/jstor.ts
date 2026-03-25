import type { ActorEvent } from "@frame/types";
import { ConfidenceTier } from "@frame/types";
import type { ActorSourceCategory } from "@frame/types";

const UA = "FrameActorLayer/1.0 (https://github.com/Swixixle/FRAME)";
const TIER = ConfidenceTier.SingleSource;
const CATEGORY: ActorSourceCategory = "academic";

/**
 * JSTOR metadata search (open-access filter). The public endpoint often returns HTML (SPA shell);
 * when JSON is returned, map hits to events; otherwise no events (manifest still records `not_found`).
 */
export async function lookupJstorOpenAccess(name: string): Promise<ActorEvent[]> {
  const q = name.trim();
  if (q.length < 2) return [];
  const url =
    `https://www.jstor.org/api/metadata/journal/search?query=${encodeURIComponent(q)}&access=free`;
  try {
    const r = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "application/json, text/plain;q=0.9,*/*;q=0.8" },
    });
    const text = await r.text();
    const head = text.trimStart().slice(0, 1);
    if (!r.ok || head !== "{" && head !== "[") {
      return [];
    }
    const data = JSON.parse(text) as {
      results?: Array<{ title?: string; url?: string; doi?: string }>;
      items?: Array<{ title?: string; url?: string; doi?: string }>;
    };
    const rows = data.results ?? data.items ?? [];
    if (!Array.isArray(rows) || rows.length === 0) return [];
    const out: ActorEvent[] = [];
    for (const row of rows.slice(0, 5)) {
      const title = (row.title ?? "").trim();
      const link = (row.url ?? "").trim();
      if (!title && !link) continue;
      out.push({
        date: "unknown",
        type: "jstor_open_access",
        description: title || link,
        source: link || url,
        confidence_tier: TIER,
        source_category: CATEGORY,
      });
    }
    return out;
  } catch {
    return [];
  }
}
