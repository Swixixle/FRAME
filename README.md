# Frame

**Cryptographic public record verification. Every claim sourced, signed, and verifiable.**

---

## What it is

Frame is a fact-checking infrastructure tool. You give it a name, a claim, or a piece of media. It searches public records — campaign finance filings, lobbying disclosures, nonprofit financials, biographical registries — pulls back real data, and signs the result cryptographically so the record can't be quietly altered later.

It isn't a verdict machine. It doesn't tell you what to think. It gives you a signed, timestamped receipt that says: here is what the public record shows, here is where it came from, and here is proof that this record hasn't been changed since it was issued.

---

## What it does right now

**Search public figures by name.** Type "Ted Cruz" — Frame finds him in the FEC database, pulls career campaign finance totals, signs the result, and returns a verifiable receipt. No manual candidate ID needed.

**Cross-reference money and lobbying.** Combined mode pulls FEC contributions and Senate LDA lobbying disclosures together, generates a narrative, and signs the whole thing.

**Nonprofit financials.** IRS 990 data via ProPublica. Type an organization name and EIN, get assets, revenue, and filings — signed.

**Public figure biography.** Wikidata adapter returns occupations, employers, and party affiliations for any public figure in the registry.

**Media fingerprinting.** Upload any image or file. Frame generates a SHA-256 hash and a signed timestamp receipt. If the file changes later, the signature breaks. AI-generated image detection is wired in (requires Hive API key).

**Receipt verification.** Any signed Frame receipt can be independently verified against the public key. No trust required.

---

## Live demo

[https://frame-2yxu.onrender.com/demo](https://frame-2yxu.onrender.com/demo)

Try: type **Ted Cruz** in FEC mode. Or **Gates Foundation** with EIN 562618866 in 990 mode.

---

## Data sources

| Adapter | Source | What it returns |
|---|---|---|
| FEC | api.open.fec.gov | Campaign finance totals, candidate IDs |
| LDA | Senate lobbying disclosures | Lobbying clients, firms, dollar amounts |
| 990 | ProPublica Nonprofit Explorer | Nonprofit assets, revenue, filings |
| Wikidata | Wikidata public registry | Biography, affiliations, employers |
| Media | Uploaded file | SHA-256 hash, AI detection score, signed receipt |

---

## How signing works

Every receipt is signed with **Ed25519** using **JCS (RFC 8785) canonicalization** — not JSON.stringify. This means the signature is deterministic regardless of key ordering, whitespace, or serialization differences. The public key is included in every receipt. Verification requires no account, no API key, and no trust in Frame.

---

## Stack

- Python FastAPI (backend, Render)
- Node.js subprocess (signing layer)
- Ed25519 + JCS canonicalization
- Render environment for key storage (base64-encoded)

## Environment variables (API / Render)

| Variable | Purpose |
|----------|---------|
| `FRAME_PRIVATE_KEY` | Ed25519 PEM for signing receipts |
| `FRAME_KEY_FORMAT` | `pem` or `base64` (Render often uses base64) |
| `FEC_API_KEY` | OpenFEC (`DEMO_KEY` works with low limits) |
| `ANTHROPIC_API_KEY` | Claude vision for media OCR / claim extraction |
| `CONGRESS_API_KEY` | [api.congress.gov](https://api.congress.gov) — **required** for Congress bill search in Gap 3 routing (free signup) |
| `HIVE_API_KEY` | Optional AI-generated image detection |

**Gap 3:** `POST /v1/analyze-media` runs claim routing → public-record adapters → attaches `adapterResults` per claim. **`POST /v1/analyze-and-verify`** does the full pipeline and returns a signed receipt + `receiptUrl` in one request (used by the macOS capture script and browser extension).

---

## Status

Active development. Core pipeline is live and tested. Media UI in progress. See `docs/CONTEXT.md` for full technical state and roadmap.

---

## What's next

- Image upload UI on the demo page
- Hive API key for live AI detection scores
- News API adapter (Guardian, NYT) for cross-referencing public figures with documented reporting
- Fuzzy name matching in FEC search
- Perceptual hashing (videohash) for viral content fingerprinting
- Custom domain

---

## The mission

Epistemic infrastructure. Not an attack tool — a public record tool. Works for lies and truths equally. Every claim gets the same treatment: sourced, signed, tamper-evident, verifiable by anyone.

---

*Built by Alex ([@Swixixle](https://github.com/Swixixle))*
