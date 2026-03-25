import type { ActorEvent } from "@frame/types";
import type { ActorSourceCategory } from "@frame/types";
import { ConfidenceTier } from "@frame/types";
import {
  entityMentionedInRss,
  parseRss2Items,
  rssPubDateToIso,
} from "./rss-parse.js";

const UA = "FrameActorLayer/1.0 (https://github.com/Swixixle/FRAME)";
const SOURCE_NAME = "The Anomalist";
const SOURCE_CATEGORY: ActorSourceCategory = "paranormal_community";

const FEED_URLS = [
  "https://www.anomalist.com/feed/rss.xml",
  "https://anomalist.com/feed/rss.xml",
  "http://fetchrss.com/rss/6349952558d159296d0ef0c2634994e836de582f7528bc52.xml",
];

/**
 * Latest RSS articles mentioning `name` — community paranormal source, single-source tier.
 */
export async function lookupAnomalist(name: string): Promise<ActorEvent[]> {
  const q = name.trim();
  if (q.length < 2) return [];

  let xml = "";
  for (const url of FEED_URLS) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": UA } });
      const text = await r.text();
      if (r.ok && text.includes("<rss") && text.includes("<item")) {
        xml = text;
        break;
      }
    } catch {
      /* try next */
    }
  }
  if (!xml) return [];

  const items = parseRss2Items(xml);
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
