/**
 * Map API receipt JSON → PUBLIC EYE investigation display model.
 */

function receiptIdOf(r) {
  return r?.receipt_id || r?.report_id || r?.deep_receipt_id || "";
}

function claimsVerified(r) {
  return Array.isArray(r?.claims_verified) ? r.claims_verified : [];
}

export function buildInvestigationView(receipt) {
  if (!receipt) return null;

  const syn = receipt.synthesis || {};
  const gp = receipt.global_perspectives || receipt.global_perspectives_result || syn.global_perspectives;
  const articles = receipt.articles || [];

  let headline =
    syn.what_is_happening ||
    receipt.article_topic ||
    (receipt.article && receipt.article.title) ||
    receipt.query ||
    receipt.document?.publication ||
    "What is happening?";

  headline = String(headline).trim() || "What is happening?";

  /** @type {{ confirmed: string[], disputed: string[], missing: string[] }} */
  const bullets = { confirmed: [], disputed: [], missing: [] };

  if (Array.isArray(syn.key_facts)) {
    bullets.confirmed.push(
      ...syn.key_facts.map((f) => (typeof f === "object" && f?.fact ? f.fact : String(f))).slice(0, 5),
    );
  }
  if (Array.isArray(syn.contested_facts)) {
    for (const c of syn.contested_facts) {
      if (!c || typeof c !== "object") continue;
      const line = c.fact ? `${c.fact}` : "";
      if (line) bullets.disputed.push(line);
    }
  }
  if (Array.isArray(syn.what_nobody_is_saying)) {
    bullets.missing.push(...syn.what_nobody_is_saying.map(String));
  }

  const claims = claimsVerified(receipt);
  if (claims.length && bullets.confirmed.length === 0) {
    const found = claims.filter((c) =>
      (c.verifications || []).some((v) => v.status === "found"),
    );
    bullets.confirmed.push(
      ...found.slice(0, 4).map((c) => c.claim || c.subject || "").filter(Boolean),
    );
    const partial = claims.filter((c) => {
      const vs = c.verifications || [];
      const hasFound = vs.some((v) => v.status === "found");
      const hasNot = vs.some((v) => v.status === "not_found" || v.status === "error");
      return hasFound && hasNot;
    });
    if (partial.length) {
      bullets.disputed.push(
        ...partial.slice(0, 2).map((c) => c.claim || "").filter(Boolean),
      );
    }
  }

  if (bullets.missing.length === 0 && receipt.extraction_error) {
    bullets.missing.push(String(receipt.extraction_error));
  }
  if (bullets.confirmed.length === 0) {
    bullets.confirmed.push("We are still mapping what the public record supports for this story.");
  }
  if (bullets.disputed.length === 0) {
    bullets.disputed.push("No major contested claims surfaced in this pass — see sources for nuance.");
  }
  if (bullets.missing.length === 0) {
    bullets.missing.push("What outlets chose not to emphasize or left unsourced.");
  }

  const ecosystems = gp?.ecosystems || [];
  const blindSpots = syn.what_nobody_is_saying?.length
    ? syn.what_nobody_is_saying
    : gp?.absent_from_all || [];

  const sourceCount =
    typeof receipt.articles_found === "number"
      ? receipt.articles_found
      : articles.length || (claims.length ? 1 : 0);

  return {
    receipt,
    receiptId: receiptIdOf(receipt),
    headline,
    bullets,
    globalPerspectives: gp && (ecosystems.length || gp.claim) ? gp : null,
    blindSpots: Array.isArray(blindSpots) ? blindSpots.map(String) : [],
    signed: Boolean(receipt.signed),
    generatedAt: receipt.generated_at || null,
    receiptType: receipt.receipt_type || "unknown",
    sourceCount,
    permalinkPath: `/i/${receiptIdOf(receipt)}`,
  };
}

export function cardSummaryFromReceipt(receipt) {
  const v = buildInvestigationView(receipt);
  if (!v) return { title: "Investigation", takeaway: "", sourceCount: 0, signed: false };
  return {
    title: v.headline.slice(0, 120) + (v.headline.length > 120 ? "…" : ""),
    takeaway: (receipt.article && receipt.article.title) || receipt.query || v.headline,
    sourceCount: v.sourceCount,
    signed: v.signed,
  };
}
