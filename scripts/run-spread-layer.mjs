#!/usr/bin/env node
/**
 * stdin: JSON { "narrative": "..." }
 * stdout: JSON SpreadResult
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const { getSpreadLayer } = await import(join(root, "packages/adapters/dist/spread.js"));

const raw = readFileSync(0, "utf8");
const input = JSON.parse(raw);
const out = await getSpreadLayer(input);
process.stdout.write(JSON.stringify(out));
