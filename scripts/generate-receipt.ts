/**
 * Build a live FEC receipt for a candidate and sign it with FRAME_PRIVATE_KEY from apps/api/.env.
 * Used by the Frame API (Python subprocess). Prints one JSON object to stdout.
 *
 * Usage: npx tsx scripts/generate-receipt.ts <candidateId>
 */
import { createPrivateKey, createPublicKey } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildLiveFecReceipt } from "../packages/sources/index.js";
import { signReceipt, verifyReceipt } from "../packages/signing/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const ENV_PATH = path.join(REPO_ROOT, "apps", "api", ".env");

/** Minimal .env parser: KEY=value or KEY="JSON-encoded string" (PEMs use JSON.stringify newlines). */
function loadEnvFile(filePath: string): void {
  const raw = readFileSync(filePath, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = JSON.parse(val) as string;
    }
    process.env[key] = val;
  }
}

function pemFromEnv(name: string): string {
  const v = process.env[name];
  if (!v || v.trim() === "") {
    throw new Error(`Missing ${name} in ${ENV_PATH}`);
  }
  return v.replace(/\\n/g, "\n").trim();
}

const candidateId = process.argv[2]?.trim() ?? "";
if (!candidateId) {
  console.error("Usage: npx tsx scripts/generate-receipt.ts <candidateId>");
  process.exit(1);
}

loadEnvFile(ENV_PATH);

const fecKey = process.env.FEC_API_KEY?.trim() ?? "DEMO_KEY";
const privatePem = pemFromEnv("FRAME_PRIVATE_KEY");
const publicPem = pemFromEnv("FRAME_PUBLIC_KEY");

const privateKey = createPrivateKey(privatePem);
const envDer = createPublicKey(publicPem).export({
  type: "spki",
  format: "der",
}) as Buffer;
const derivedDer = createPublicKey(privateKey).export({
  type: "spki",
  format: "der",
}) as Buffer;
if (!envDer.equals(derivedDer)) {
  throw new Error(
    "FRAME_PUBLIC_KEY does not match FRAME_PRIVATE_KEY (SPKI DER mismatch).",
  );
}

const payload = await buildLiveFecReceipt(candidateId, fecKey);
const signed = signReceipt(payload, { privateKey });

const v = verifyReceipt(signed);
if (!v.ok) {
  throw new Error(`Self-verify failed: ${v.reasons.join("; ")}`);
}

process.stdout.write(`${JSON.stringify(signed)}\n`);
