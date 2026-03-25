import Anthropic from "@anthropic-ai/sdk";

/** Frame receipt prose only (not Rabbit Hole / surface Layer 1). */
export const FRAME_RECEIPT_NARRATIVE_MODEL = "claude-sonnet-4-20250514";

export const FRAME_RECEIPT_NARRATIVE_SYSTEM = `You are a research analyst writing for investigative journalists and policy editors. 
You have been given structured data from primary sources — FEC filings, lobbying disclosures, 
SEC records, congressional votes, IRS 990s, or court records. 

Write a receipt narrative with exactly four sections:

FINDINGS: 2-3 sentences. State what the sources directly confirm — specific figures, 
dates, parties, and amounts in plain language. Do not hedge what the data actually shows.

CONTEXT: 2-3 sentences. Explain what these figures mean relative to normal baselines, 
comparable actors, or historical patterns. If you do not have comparative data, say so 
explicitly and state what comparison would be meaningful.

GAPS: 1-2 sentences. Identify what the sources do not show, could not show, or where 
records are absent. Name the specific database or filing type that would contain the 
missing information if it existed.

SIGNIFICANCE: 1-2 sentences. State plainly why this matters for public accountability. 
Write this as something an editor could publish directly. Do not use hedging language 
like "may suggest" or "could indicate" — if the data is ambiguous, say it is ambiguous 
and why.

Do not use bullet points. Do not summarize. Do not repeat the input back. 
Write as if a reader's understanding of institutional accountability depends on getting this right.`;

export type FecNarrativeInput = {
  candidateName: string;
  candidateId: string;
  hasCycleTotals: boolean;
  allCycleTotals: Array<{
    cycle: number;
    receipts: number;
    pacContributions: number;
    individualContributions: number;
    electionYear: number;
  }>;
};

/** Pull SIGNIFICANCE section body; empty if missing. */
export function extractSignificanceFromProse(full: string): string {
  const t = full.trim();
  if (!t) return "";
  const m = t.match(/SIGNIFICANCE:\s*([\s\S]+?)$/im);
  if (m) return m[1]!.replace(/\s+/g, " ").trim();
  return "";
}

export function firstSentence(text: string): string {
  const t = text.trim();
  if (!t) return "";
  const m = t.match(/^[^.!?]+[.!?](?=\s|$)/);
  if (m) return m[0]!.trim();
  const idx = t.search(/[.!?](?:\s|$)/);
  if (idx === -1) return t.slice(0, 280).trim();
  return t.slice(0, idx + 1).trim();
}

export async function generateFecReceiptNarrative(
  input: FecNarrativeInput,
): Promise<{ prose: string; significance: string }> {
  const key = process.env.ANTHROPIC_API_KEY?.trim();
  if (!key) {
    throw new Error("ANTHROPIC_API_KEY not set");
  }

  const client = new Anthropic({ apiKey: key });
  const user = `Structured records from the FEC OpenFEC API (public). Use only this JSON for quantities and identifiers in FINDINGS. Do not invent amounts, cycles, or donors.

${JSON.stringify(input, null, 2)}

Write the receipt narrative with four sections. Put each section header on its own line exactly as: FINDINGS: then CONTEXT: then GAPS: then SIGNIFICANCE: (with the colon). After each header, write the prose for that section. Do not use bullet points.`;

  const msg = await client.messages.create({
    model: FRAME_RECEIPT_NARRATIVE_MODEL,
    max_tokens: 2048,
    system: FRAME_RECEIPT_NARRATIVE_SYSTEM,
    messages: [{ role: "user", content: user }],
  });

  const block = msg.content[0];
  if (!block || block.type !== "text") {
    throw new Error("Anthropic returned no text block for receipt narrative");
  }

  let prose = block.text.trim();
  if (prose.startsWith("```")) {
    prose = prose.replace(/^```(?:\w+)?\s*/i, "").replace(/\s*```\s*$/, "");
  }

  let significance = extractSignificanceFromProse(prose);
  if (!significance) {
    significance = firstSentence(prose);
  }

  return { prose, significance };
}
