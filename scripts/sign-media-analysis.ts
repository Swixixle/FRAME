import type { FrameReceiptPayload } from "@frame/types";
import { createPrivateKey, randomUUID } from "node:crypto";
import { signReceipt } from "../packages/signing/index.js";

const input = JSON.parse(
  await new Promise<string>((resolve) => {
    let data = "";
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
  }),
) as {
  fileHash: string;
  fileName: string;
  fileSize: number;
  contentType: string;
  detection: {
    detector?: string;
    ai_generated_score?: number | null;
    error?: string;
    note?: string;
    classes?: unknown[];
  };
  timestamp: string;
  claimText?: string | null;
};

function getPrivateKeyPem(): string {
  const format = process.env.FRAME_KEY_FORMAT ?? "pem";
  const raw = process.env.FRAME_PRIVATE_KEY ?? "";
  if (!raw) throw new Error("Missing FRAME_PRIVATE_KEY");
  if (format === "base64") {
    const decoded = Buffer.from(raw.trim(), "base64").toString("utf8");
    return decoded.replace(/\\n/g, "\n");
  }
  return raw.replace(/\\n/g, "\n").replace(/^["']|["']$/g, "").trim();
}

const privateKey = createPrivateKey(getPrivateKeyPem());

const aiScore = input.detection?.ai_generated_score;
const detectorName = input.detection?.detector ?? "unknown";
const hasDetection = aiScore != null;

const narrativeText = hasDetection
  ? `At ${input.timestamp}, this media file (SHA-256: ${input.fileHash}) was analyzed by ${detectorName}. AI-generated content probability: ${(Number(aiScore) * 100).toFixed(1)}%.`
  : `At ${input.timestamp}, this media file (SHA-256: ${input.fileHash}) was received and hashed. No AI detection was performed.`;

const claimText = input.claimText
  ? `Media analysis: "${input.claimText}" — file hash ${input.fileHash.slice(0, 16)}...`
  : `Media file integrity receipt — SHA-256: ${input.fileHash.slice(0, 16)}...`;

const sourceId = `media-${input.fileHash.slice(0, 16)}`;

const payload: FrameReceiptPayload = {
  schemaVersion: "1.0.0",
  receiptId: randomUUID(),
  createdAt: input.timestamp,
  claims: [
    {
      id: "claim-1",
      statement: claimText,
      assertedAt: input.timestamp,
    },
  ],
  sources: [
    {
      id: sourceId,
      adapter: "manual",
      url: `sha256:${input.fileHash}`,
      title: `Media file: ${input.fileName} (${input.contentType})`,
      retrievedAt: input.timestamp,
      externalRef: input.fileHash,
      metadata: {
        fileHash: input.fileHash,
        fileName: input.fileName,
        fileSize: input.fileSize,
        contentType: input.contentType,
        detection: input.detection ?? {},
      } as unknown as NonNullable<FrameReceiptPayload["sources"][number]["metadata"]>,
    },
  ],
  narrative: [
    { text: narrativeText, sourceId },
    ...(input.claimText
      ? [
          {
            text: `Extracted claim: "${input.claimText}"`,
            sourceId,
          },
        ]
      : []),
  ],
  contentHash: "",
};

const signed = signReceipt(payload, { privateKey });
process.stdout.write(`${JSON.stringify(signed)}\n`);
