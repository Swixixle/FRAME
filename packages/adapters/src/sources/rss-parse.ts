/** Minimal RSS 2.0 snippet parser (no XML dependency). */

export type RssItem = {
  title: string;
  link: string;
  pubDate: string;
  description: string;
};

export function stripTags(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function unwrapCdata(s: string): string {
  const t = s.trim();
  if (t.startsWith("<![CDATA[")) {
    return t.replace(/^<!\[CDATA\[/, "").replace(/\]\]>\s*$/, "");
  }
  return t;
}

function extractTag(block: string, tag: string): string {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i");
  const m = block.match(re);
  if (!m?.[1]) return "";
  return unwrapCdata(m[1].trim());
}

export function parseRss2Items(xml: string): RssItem[] {
  const out: RssItem[] = [];
  const itemRe = /<item\b[^>]*>([\s\S]*?)<\/item>/gi;
  let m: RegExpExecArray | null;
  while ((m = itemRe.exec(xml)) !== null) {
    const block = m[1] ?? "";
    const title = extractTag(block, "title");
    let link = extractTag(block, "link");
    if (!link) {
      const guid = extractTag(block, "guid");
      if (guid.startsWith("http")) link = guid;
    }
    let pubDate = extractTag(block, "pubDate");
    if (!pubDate) pubDate = extractTag(block, "dc:date") || extractTag(block, "date");
    const descRaw = extractTag(block, "description") || extractTag(block, "content:encoded");
    const description = stripTags(descRaw);
    if (title && link) {
      out.push({ title, link, pubDate, description });
    }
  }
  return out;
}

export function rssPubDateToIso(pubDate: string): string {
  const t = pubDate.trim();
  if (!t) return "unknown";
  const ms = Date.parse(t);
  if (!Number.isFinite(ms)) return "unknown";
  return new Date(ms).toISOString().slice(0, 10);
}

const STOP = new Set(["the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for"]);

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Entity mention in title or description: full phrase or all significant tokens as whole words. */
export function entityMentionedInRss(name: string, title: string, description: string): boolean {
  const combined = `${title} ${description}`.toLowerCase();
  const phrase = name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (phrase.length >= 3 && combined.includes(phrase)) return true;
  const tokens = phrase
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length >= 2 && !STOP.has(w));
  if (tokens.length === 0) return false;
  return tokens.every((w) => new RegExp(`\\b${escapeRegExp(w)}\\b`, "i").test(combined));
}
