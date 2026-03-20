# Frame — project context

**Last updated:** March 2026 (Session 2)

**Full handoff (architecture, Render, E2E, troubleshooting):** [`HANDOFF.md`](./HANDOFF.md)

## What Frame is (one paragraph)

Frame is a transparency tool that turns political claims into **cryptographically signed receipts**: each receipt ties neutral narrative sentences to concrete sources (money, votes, lobbying, filings) so readers can see **what the record shows** without editorial judgment baked into the cryptography. Hashing uses **JCS (RFC 8785)** via the `canonicalize` npm package (never `JSON.stringify` for signatures); signing is **Ed25519**.

## The three governance rules

1. **Every narrative sentence must have a `sourceId`** that exists in the `sources` array.
2. **No judgment adjectives** in narrative (e.g. corrupt, suspicious, troubling, criminal, fraudulent, unethical, scandal, etc.) — describe filings and data neutrally.
3. **JCS canonicalization** for all cryptographic hashing — use the **`canonicalize`** npm package; **never** `JSON.stringify` for hash/signature payloads.

## Current build status

- **Tests:** `npm test` — **5/5 passing** (Vitest; Manchin signing + governance checks).
- **TypeScript:** `npm run build` — project references build clean.
- **Repo:** Pushed to **GitHub** (`Swixixle/FRAME` / `main`).
- **Session 2 delivered:** `scripts/seed-demo.ts` signs the Manchin fixture with keys from `apps/api/.env` (not committed), writes `apps/web/demo-payload.json`, and the web demo loads that file over HTTP. FastAPI verify uses Node `scripts/jcs-stringify.mjs` for matching JCS.

## Next immediate tasks

1. **Demo / grant artifact:** One **working signed Frame** on the Manchin claim, **hosted publicly** (URL you can paste into the application).
2. **Deploy:** e.g. **Render** (or similar) for API + static `apps/web` (or combined approach) so the Brown submission has a live **demo URL**.
3. **Brown application package:** Submit alongside the written sections already drafted — the **running demo is part of the submission**.

## Brown Institute for Media Innovation (grant)

- **What:** Grant funding for media innovation projects.
- **Amount:** Up to **$150,000**.
- **Deadline:** **April 1, 2026** (confirm on official call; plan for time zone / portal cutoff).
- **Submit:** **brown.submittable.com**
- **Requirement:** A **demo URL** (public) is expected with the application — the Frame demo + signed Manchin receipt should satisfy that bar once deployed.

## Repo map (quick)

| Path | Role |
|------|------|
| `packages/types` | Shared TS types |
| `packages/signing` | Ed25519 + JCS signing |
| `packages/narrative` | Banned words, domain whitelist, narrative validation |
| `packages/entity` | Disambiguation + confidence floor |
| `packages/sources` | FEC, OpenSecrets, ProPublica, lobbying, EDGAR adapters (stubs) |
| `apps/api` | FastAPI verification (`/v1/verify-receipt`, JCS via Node) |
| `apps/web` | Static demo; loads `demo-payload.json` when served over HTTP |
| `scripts/seed-demo.ts` | Sign Manchin fixture → `apps/web/demo-payload.json` |
| `scripts/jcs-stringify.mjs` | JCS helper for Python (must match TS) |
| `.github/copilot-instructions.md` | Agent rules (same three governance rules) |

## Secrets (never commit)

- `apps/api/.env` — `FRAME_PRIVATE_KEY`, `FRAME_PUBLIC_KEY` (PEM, JSON-escaped in file).
- Regenerate with `npm run generate-keys` if needed; re-run `npx tsx scripts/seed-demo.ts` after changing keys.

---

*Memory in chat tools resets; this file does not. Update this doc when milestones or deadlines change.*
