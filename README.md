# PUBLIC EYE

You paste a news article URL. PUBLIC EYE tells you what the record actually says, which outlets are fighting over it and why, what's being left out, and produces a cryptographically signed receipt so none of it can be quietly altered later.

**Live:** https://frame-2yxu.onrender.com  
**Verify any receipt:** https://frame-2yxu.onrender.com/verify  
**Example investigation:** https://frame-2yxu.onrender.com/i/8449d4ca-9b30-4ef5-90e5-a9ada6635e91

---

## What it actually does

1. **Fetches and reads** the article at the URL you give it
2. **Searches** a range of global sources for coverage of the same story
3. **Maps the framing gap** — which outlets are most opposed and why, down to what each side emphasizes vs. buries
4. **Scores the divergence** — 0 means everyone agrees on the basics; 100 means parallel realities with no shared premise
5. **Names the irreconcilable gap** — the one thing that cannot be simultaneously true across both framings
6. **Lists what nobody is covering** — the angles absent from all sources found
7. **Signs the whole thing** with Ed25519 so the output is tamper-evident and independently verifiable

The stance throughout is: receipts, not verdicts. The tool surfaces what the record shows and what it doesn't show. It doesn't tell you who's right.

---

## The investigation page

Every analysis produces a permalink at `/i/{receipt_id}`. That page shows:

- The article headline
- A **VOLATILITY** score (colored pill: green = calm, amber = contested, red = parallel realities)
- **Where the story splits** — the irreconcilable gap sentence, always visible
- Two anchor positions side by side with their emphasis/minimization tags
- **Who's on each side** — collapsible chain of outlets by country, with state/private/public badges
- What both sides agree happened
- What no one is really talking about
- Verification section at the bottom: receipt ID, Ed25519 signature, signing key, links to raw JSON and the verifier

---

## The verifier

`/verify?id={receipt_id}` — anyone can confirm a receipt hasn't been altered since it was generated. No login required. Explains the verification method in plain English. Links to raw JSON for offline verification with `openssl`.

---

## Stack

**API:** Python, FastAPI, Postgres (receipts + coalition maps), Ed25519 + JCS signing  
**Frontend:** Vite + React (Netlify) — currently being replaced by server-rendered pages  
**Investigation pages:** Server-rendered HTML from the API, no JS framework required  
**LLM:** Anthropic Claude for analysis and coalition mapping, with fallback to Groq/Gemini/OpenAI  
**Deployed:** Render (API), Netlify (web frontend)

---

## Repo layout

```
apps/
  api/              FastAPI app — all routes, signing, receipt storage, investigation HTML
  web/              Vite + React frontend (Netlify)

packages/
  types/            TypeScript receipt shapes
  sources/          FEC, LDA, 990, Wikidata data builders
  signing/          JCS + Ed25519 sign/verify
  narrative/        Governance and entity modeling

scripts/            CLI tools: signing, JCS, generation
docs/               System documentation
```

---

## Running it locally

**Requirements:** Node ≥ 20, Python 3.11+, Postgres

```bash
# 1. Install everything
npm ci && npm run build
pip install -r apps/api/requirements.txt

# 2. Configure environment
cp apps/api/.env.example apps/api/.env
# Fill in: FRAME_PRIVATE_KEY, FRAME_PUBLIC_KEY, DATABASE_URL, ANTHROPIC_API_KEY

# 3. Start the API
cd apps/api
uvicorn main:app --reload --port 8000

# 4. Start the web frontend (separate terminal)
cd apps/web
npm run dev
```

The API will be at `http://localhost:8000`. The Vite dev server at `http://localhost:5173`.

---

## Environment variables

**Required to run at all:**
```
FRAME_PRIVATE_KEY       Ed25519 private key (base64 PKCS#8 DER)
FRAME_PUBLIC_KEY        Matching public key
FRAME_KEY_FORMAT        Set to: base64
DATABASE_URL            PostgreSQL connection string
ANTHROPIC_API_KEY       For analysis and coalition mapping
```

**Optional but useful:**
```
REDIS_URL               Enables background enrichment queue (ARQ)
GROQ_API_KEY            LLM fallback #1 (fast, free tier available)
GOOGLE_API_KEY          LLM fallback #2
OPENAI_API_KEY          LLM fallback #3
LLM_PROVIDER            Force a provider: anthropic | groq | google | openai | auto
FEC_API_KEY             Federal Election Commission data
CONGRESS_API_KEY        Congressional records
COURTLISTENER_API_KEY   Court documents
ASSEMBLYAI_API_KEY      Audio transcription
SEC_EDGAR_USER_AGENT    SEC filings
```

---

## Key API endpoints

```
POST /v1/analyze-article        Analyze an article URL, returns receipt
GET  /r/{receipt_id}            Get a receipt as JSON
GET  /i/{receipt_id}            Server-rendered investigation page
GET  /verify                    Public verifier page
POST /v1/verify-receipt         Programmatic verification
POST /v1/coalition-map          Trigger coalition map generation (async)
GET  /v1/coalition-map/{id}     Get coalition map (poll after POST)
GET  /v1/receipts/recent        Recent receipts
GET  /v1/status                 Health + public key
GET  /openapi.json              Full API spec (81 endpoints)
```

---

## How signing works

Every receipt goes through this before being stored:

1. Build the semantic payload (claims, sources, narrative, perspectives)
2. Canonicalize with RFC 8785 JCS — deterministic key ordering, no whitespace variation
3. SHA-256 the canonical string → `content_hash`
4. Sign the hex digest with Ed25519 → `signature`
5. Store `public_key`, `signature`, and `content_hash` alongside the receipt

To verify: fetch the receipt, recompute the JCS hash, check the signature against the embedded public key. If it passes, the receipt hasn't been touched. If it fails, something changed after signing.

Pure Python JCS implementation is in `apps/api/jcs_canonicalize.py` — no Node subprocess required.

---

## Tests

```bash
# TypeScript (signing, JCS, narrative fixtures)
npm test

# End-to-end against a running API
npm run e2e

# Or manually:
bash scripts/e2e-test.sh http://localhost:8000
```

See `packages/signing/__tests__/` for the signing unit tests.  
See `docs/PROOF.md` for curl-based verification walkthroughs.

---

## Deployment

Deployed via `render.yaml`. The API service runs:

```
cd apps/api && uvicorn main:app --host 0.0.0.0 --port $PORT
```

Build command installs Node packages, compiles TypeScript, then installs Python deps.

Set all required environment variables in Render → service → Environment before deploying.

The Vite frontend deploys separately to Netlify via `netlify.toml`. Set `VITE_API_BASE_URL` to your API URL at build time.

---

## What this is not

- Not a fact-checker. It doesn't say who's right.
- Not a bias meter. It maps divergence, not political lean.
- Not a search engine. It analyzes specific articles and stories.
- Not a claim oracle. Every output includes explicit unknowns.

---

## License

MIT
