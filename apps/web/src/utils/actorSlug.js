/** Ledger slug for GET /v1/actor/{slug} — lowercase, hyphenated, safe for URL path. */
export function actorNameToSlug(name) {
  if (!name || typeof name !== "string") return "unknown";
  const s = name
    .toLowerCase()
    .trim()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
  return s || "unknown";
}

/** Hyphenated slug plus fallback when the ledger row uses the name outside parentheses (e.g. aliases). */
export function actorSlugCandidates(name) {
  if (!name || typeof name !== "string") return ["unknown"];
  const trimmed = name.trim();
  const primary = actorNameToSlug(trimmed);
  const parenStripped = trimmed.replace(/\([^)]*\)/g, "").trim();
  const secondary =
    parenStripped && parenStripped !== trimmed ? actorNameToSlug(parenStripped) : null;
  const ordered =
    secondary && secondary !== primary ? [primary, secondary] : [primary];
  return [...new Set(ordered)];
}

/** After prefetch: every candidate slug has a boolean in `ledgerPresence`; pick first hit for href. */
export function actorLedgerResolved(name, ledgerPresence) {
  const candidates = actorSlugCandidates(name);
  const map = ledgerPresence || {};
  const checked = candidates.every((slug) =>
    Object.prototype.hasOwnProperty.call(map, slug),
  );
  const resolvedSlug = candidates.find((slug) => map[slug] === true) ?? null;
  return {
    checked,
    resolvedSlug,
    inLedger: resolvedSlug != null,
  };
}
