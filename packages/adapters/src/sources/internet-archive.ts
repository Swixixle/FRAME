import type { ActorEvent } from "@frame/types";
import { ConfidenceTier } from "@frame/types";
import type { ActorSourceCategory } from "@frame/types";

const UA = "FrameActorLayer/1.0 (https://github.com/Swixixle/FRAME)";

const SOURCE_CATEGORY: ActorSourceCategory = "primary_historical";

function tierForYear(year: number): ConfidenceTier {
  if (!Number.isFinite(year)) return ConfidenceTier.SingleSource;
  if (year < 1900) return ConfidenceTier.OfficialPrimary;
  if (year <= 1950) return ConfidenceTier.CrossCorroborated;
  return ConfidenceTier.SingleSource;
}

function oneLineDescription(raw: unknown): string {
  if (raw == null) return "";
  const s = Array.isArray(raw) ? String(raw[0] ?? "") : String(raw);
  const t = s.replace(/\s+/g, " ").trim();
  if (!t) return "";
  const cut = t.indexOf(". ");
  return (cut > 0 ? t.slice(0, cut + 1) : t).slice(0, 400);
}

const STOP = new Set(["the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for"]);

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function nameTokens(name: string): string[] {
  return name
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length >= 2 && !STOP.has(w));
}

/**
 * Drop hits with no token/phrase overlap between the query name and Solr title + description
 * (full work text matching is too loose for cocktail names, etc.).
 */
export function relevanceFilterInternetArchiveHit(
  name: string,
  title: string,
  descriptionRaw: unknown,
): boolean {
  const desc = oneLineDescription(descriptionRaw);
  const combined = `${title} ${desc}`.toLowerCase();
  const phrase = name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (phrase.length >= 3 && combined.includes(phrase)) return true;
  const tokens = nameTokens(name);
  if (tokens.length === 0) return false;
  return tokens.every((w) => new RegExp(`\\b${escapeRegExp(w)}\\b`, "i").test(combined));
}

function docsToFilteredEvents(
  name: string,
  docs: Array<{
    identifier?: string;
    title?: string;
    year?: string | number;
    description?: string | string[];
  }>,
  max: number,
): ActorEvent[] {
  const q = name.trim();
  const out: ActorEvent[] = [];
  for (const d of docs) {
    const id = d.identifier?.trim();
    if (!id) continue;
    const title = (d.title ?? "").trim() || id;
    if (!relevanceFilterInternetArchiveHit(q, title, d.description)) continue;
    const yearNum =
      typeof d.year === "number" ? d.year : parseInt(String(d.year ?? ""), 10);
    const dateStr = Number.isFinite(yearNum) ? `${yearNum}-01-01` : "unknown";
    const desc = oneLineDescription(d.description) || title;
    out.push({
      date: dateStr,
      type: "internet_archive_text",
      description: desc,
      source: `https://archive.org/details/${encodeURIComponent(id)}`,
      confidence_tier: tierForYear(yearNum),
      source_category: SOURCE_CATEGORY,
    });
    if (out.length >= max) break;
  }
  return out;
}

async function fetchInternetArchiveDocs(solr: string): Promise<
  Array<{
    identifier?: string;
    title?: string;
    year?: string | number;
    description?: string | string[];
  }>
> {
  const url =
    `https://archive.org/advancedsearch.php?q=${encodeURIComponent(solr)}` +
    `&fl=identifier,title,year,description&output=json&rows=24&sort%5B%5D=year+desc`;
  const r = await fetch(url, { headers: { "User-Agent": UA } });
  if (!r.ok) return [];
  const data = (await r.json()) as {
    response?: {
      docs?: Array<{
        identifier?: string;
        title?: string;
        year?: string | number;
        description?: string | string[];
      }>;
    };
  };
  return data.response?.docs ?? [];
}

/**
 * Focused folklore / mythology search first; if no hits (e.g. some cryptid labels), fall back to
 * phrase + year only — relevance_filter still drops cocktails and unrelated uploads.
 */
export async function lookupInternetArchive(name: string): Promise<ActorEvent[]> {
  const q = name.trim();
  if (q.length < 2) return [];
  const escaped = q.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const folkloreBlock =
    `(folklore OR legend OR mythology OR history OR paranormal OR creature OR ghost)`;
  const yearBlock = `year:[1700 TO 1980]`;
  const primary = `mediatype:texts AND "${escaped}" AND ${folkloreBlock} AND ${yearBlock}`;
  try {
    let docs = await fetchInternetArchiveDocs(primary);
    let out = docsToFilteredEvents(q, docs, 3);
    if (out.length === 0) {
      const relaxed = `mediatype:texts AND "${escaped}" AND ${yearBlock}`;
      docs = await fetchInternetArchiveDocs(relaxed);
      out = docsToFilteredEvents(q, docs, 3);
    }
    return out;
  } catch {
    return [];
  }
}
