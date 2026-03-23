/**
 * Demo: POST a Frame (Elon Musk claim), poll dossier.
 * Run API: `cd apps/api && uvicorn main:app --reload --port 8000`
 * Then: `npx tsx scripts/seed-frames-demo.ts`
 */
const API_BASE = process.env.API_BASE ?? "http://localhost:8000";

const body = {
  claim:
    "We are not buying political influence. I'm supporting candidates who I think are good for the country.",
  claimant_name: "Elon Musk",
  claimant_role: "CEO",
  claimant_organization: "Tesla / SpaceX / X Corp",
};

async function main() {
  const post = await fetch(`${API_BASE}/frames`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await post.text();
  if (!post.ok) {
    console.error("POST /frames failed", post.status, text);
    process.exit(1);
  }
  const frame = JSON.parse(text) as Record<string, unknown>;
  const frameId = frame.id as string;
  console.error("frame_id:", frameId);
  console.log(JSON.stringify(frame, null, 2));
  console.error("dossier URL:", `${API_BASE}/frames/${frameId}/dossier`);

  await new Promise((r) => setTimeout(r, 10_000));

  const frameRes = await fetch(`${API_BASE}/frames/${frameId}`);
  const frame2 = (await frameRes.json()) as Record<string, unknown>;
  console.error("enrichment_status (after wait):", frame2.enrichment_status);

  const dossierRes = await fetch(`${API_BASE}/frames/${frameId}/dossier`);
  const dossierText = await dossierRes.text();
  let dossier: Record<string, unknown>;
  try {
    dossier = JSON.parse(dossierText) as Record<string, unknown>;
  } catch {
    console.error("dossier response (raw):", dossierText);
    process.exit(1);
  }

  console.error("dossier status:", dossierRes.status);
  console.error("enrichment / keys:", Object.keys(dossier));

  if (dossier.status === "pending") {
    console.error("Still pending after 10s — poll again later.");
    return;
  }

  const summary = dossier.narrative_summary;
  if (typeof summary === "string" && summary.length > 0) {
    console.error("narrative_summary (first 500 chars):", summary.slice(0, 500));
  } else {
    console.error("narrative_summary:", summary);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
