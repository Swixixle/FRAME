import type { ActorEvent } from "@frame/types";
import type { ActorSourceCategory } from "@frame/types";
import { ConfidenceTier } from "@frame/types";
import {
  entityMentionedInRss,
  parseRss2Items,
  rssPubDateToIso,
} from "./rss-parse.js";

const UA = "FrameActorLayer/1.0 (https://github.com/Swixixle/FRAME)";
const SOURCE_NAME = "Mysterious Universe";
const SOURCE_CATEGORY: ActorSourceCategory = "paranormal_community";

/** /feed/ returns HTML 404; production feeds are on feeds.* */
const FEED_URLS = [
  "https://feeds.mysteriousuniverse.org/feed",
  "https://feeds.mysteriousuniverse.org/feed/podcast",
  "https://mysteriousuniverse.org/feed/",
];

async function fetchMuItems(): Promise<ReturnType<typeof parseRss2Items>> {
  const merged: ReturnType<typeof parseRss2Items> = [];
  const seen = new Set<string>();
  for (const url of FEED_URLS) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": UA } });
      const text = await r.text();
      if (!r.ok || !text.includes("<rss") || !text.includes("<item")) continue;
      for (const it of parseRss2Items(text)) {
        if (seen.has(it.link)) continue;
        seen.add(it.link);
        merged.push(it);
      }
    } catch {
      /* try next */
    }
  }
  merged.sort((a, b) => rssPubDateToIso(b.pubDate).localeCompare(rssPubDateToIso(a.pubDate)));
  return merged;
}

/**
 * Latest RSS articles mentioning `name` — community paranormal source, single-source tier.
 */
export async function lookupMysteriousUniverse(name: string): Promise<ActorEvent[]> {
  const q = name.trim();
  if (q.length < 2) return [];

  const items = await fetchMuItems();
  if (items.length === 0) return [];
  const out: ActorEvent[] = [];
  for (const it of items) {
    if (!entityMentionedInRss(q, it.title, it.description)) continue;
    const date = rssPubDateToIso(it.pubDate);
    out.push({
      date,
      type: "paranormal_rss_article",
      description: `${it.title} — ${SOURCE_NAME} (community paranormal source; not an official record)`,
      source: it.link,
      confidence_tier: ConfidenceTier.SingleSource,
      source_category: SOURCE_CATEGORY,
    });
    if (out.length >= 3) break;
  }
  return out;
}
