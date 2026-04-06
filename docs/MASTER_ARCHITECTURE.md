# PUBLIC EYE — Master architecture (FRAME monorepo)

**Repository identity:** The GitHub repo and docs often say “FRAME”; the **product surface** shipped as **PUBLIC EYE**. Same codebase, same API, same receipts. This document uses **PUBLIC EYE** for the user-facing article pipeline and **FRAME** where it matches historical internal naming (receipt types, env vars, routes).

**How to read this doc:** The opening sections (§1–13) are **descriptive** — what exists. Sections **Epistemic status of this document**, **Architectural invariants**, **Failure model**, and **Known debt and design rationale** (below §13) are **prescriptive and meta** — what must hold, what breaks, what we owe, and what we still owe.

---

## 1. What this is

**PUBLIC EYE / FRAME** is **epistemic infrastructure**: it turns **URLs**, **claims**, **public records**, and **LLM-assisted analysis** into **structured artifacts** that are **cryptographically signed** (where keys are configured) so downstream systems cannot silently strip caveats, gaps, or model-generated sections that are included in the **signing payload**.

It is **not** primarily a verdict engine (“true/false”). It is a **record machine**: what sources support, what they do not, what is inferred, friction between framings, and where to look next—**with a tamper-evident seal over the defined semantic slice**.

---

## 2. What this is not (sharp boundaries)

1. **Not a single-purpose demo.** The repo ships **multiple products** (see §4). Treating it as “only the article analyzer” misses FEC/SEC/deep receipts, Rabbit Hole, dossiers, jobs, and lens pipelines.

2. **Not “everything in JSON is evidence.”** Only the **JCS-canonical signing body** for each receipt type is what the signature attests to. **UI-only fields**, **IDs**, **echo scores not copied into the slice**, and **on-demand endpoints that do not mutate the stored receipt** are **not** proven by Ed25519 unless explicitly listed in §7.2.

3. **Not guaranteed always-on on the smallest Render tier.** Cold starts, timeouts, and partial receipts are **operational reality**; the pipeline is designed to return **partial but honest** outputs (e.g. missing comparative coverage) rather than fake completeness.

---

## 3. The four products sharing this codebase

| Product | User-facing idea | Primary entry |
|--------|-------------------|---------------|
| **PUBLIC EYE** | Paste a **news URL** → investigation page: coverage, framing split, volatility, signed `article_analysis` receipt | `POST /v1/analyze-article`, `GET /i/{receipt_id}` |
| **FRAME (records)** | **FEC / SEC / legal / deep** receipts from entities and queries; three-layer **deep receipt** with explicit inference layer | `POST /v1/generate-receipt`, `POST /v1/deep-receipt`, adapters in `apps/api/adapters/` |
| **Rabbit Hole** | **Narrative** genealogy (rumor, legend, myth): surface → spread → origin → actor → pattern | `POST /v1/surface` … `POST /v1/report`, TS adapters in `packages/adapters` |
| **Dossier / enrichment** | Long-running **entity dossiers** (`DossierSchema`), enrichment paths by entity type, worker-backed jobs | `apps/api/dossier/`, `worker.py` + Redis |

All four share: **FastAPI** orchestration, **Postgres** storage for receipts where applicable, **Anthropic** for many LLM steps, and **Ed25519 + JCS** for signing paths.

---

## 4. Monorepo map

```
FRAME/   (PUBLIC EYE repo)
├── apps/api/                 # FastAPI — main.py (routes + orchestration), adapters, investigation HTML
├── apps/web/                 # React/Vite — verifier and other UI surfaces
├── apps/macos/, apps/extension/
├── packages/
│   ├── signing/              # TS — Ed25519 helpers
│   ├── sources/              # FEC, narratives (TS)
│   ├── adapters/             # Rabbit Hole rings (TS)
│   ├── types/, entity/, narrative/, pattern-lib/, actor-ledger/, dispute-log/
├── scripts/                  # jcs-stringify.mjs, utilities
├── docs/                     # CONTEXT.md, HANDOFF, this file, etc.
├── render.yaml               # Render: frame-api web + cron + worker
└── README.md                 # PUBLIC EYE product story
```

**Deploy (typical):** `render.yaml` — build installs Node + Python + native deps; start `cd apps/api && uvicorn main:app`. **Worker:** `python worker.py` (ARQ + Redis). **Cron:** hits drift endpoint with shared secret.

---

## 5. Signing — exact algorithm and the rule every engineer must internalize

### 5.1 Algorithm (article analysis)

Implementation: `apps/api/report_api.py` → `build_article_analysis_signing_body` + `attach_article_analysis_signing`; canonicalization: `apps/api/jcs_canonicalize.py` (`jcs_dumps`, RFC 8785); signing: `apps/api/frame_crypto.py` → `sign_frame_digest_hex`.

1. Build **`signing_body`** — a **subset** of the full receipt (see §7.2).
2. **`canonical = jcs_dumps(signing_body)`** — deterministic JSON string.
3. **`content_hash = SHA-256(canonical)`** (hex).
4. **`signature = Ed25519_sign(private_key, content_hash.encode("utf-8"))`** — stored as base64 (see `sign_frame_digest_hex` for the exact wire format used with the hex string).
5. Response includes **`content_hash`**, **`signature`**, **`public_key`**, **`signed: true`** (when keys load).

Other receipt types (five-ring report, deep receipt, etc.) use their own **`build_*_signing_body`** equivalents — same **JCS → SHA-256 → sign** pattern, different semantic slices.

### 5.2 The rule

**If a field is not in the signing body for that receipt type, it is decoration or context for the UI—not cryptographic evidence.**

Examples for **`article_analysis`**:

- **Inside the hash (when present on the payload and copied into the slice):** `article`, `article_topic`, `claims_verified` (including **`revisions`** nested on claims when stored there), `coverage_result`, `source_provenance`, `global_perspectives`, **`contextual_brief`**, coalition-related keys **only if** they appear on the top-level receipt object **and** are listed in `build_article_analysis_signing_body` (e.g. `volatility_score`, `anchor_positions`, `what_nobody_is_covering`, `sources`, `schema_version`).
- **Often present on the stored object but not part of the article signing slice unless added to the builder:** e.g. **`echo_chamber`** is **not** included in `build_article_analysis_signing_body` as of this document—treat as **UX/analytics**, not signed fact.
- **Never signed (separate concerns):** **`GET /v1/dig-deeper/{receipt_id}`** — on-demand JSON; **read-only**; does **not** write the receipt; **not** in the signing pipeline.

**Before adding a field you care about:** extend **`build_article_analysis_signing_body`** (and any verifier docs) or accept that it is not sealed.

---

## 6. Article pipeline — end-to-end (current)

This is the **actual** `POST /v1/analyze-article` path in `main.py` (not a simplified legacy diagram).

```mermaid
flowchart TD
  A[HTTP POST /v1/analyze-article] --> B[fetch_article]
  B --> C[extract_claims — title + text]
  C --> D[For each claim up to 15]
  D --> E[route_article_claim + build_query_for_adapter]
  E --> F[Adapter calls: surface / fec defer / congress defer / courtlistener rules / actor_ledger ...]
  F --> G{institutional or biographical + subject heuristics?}
  G -->|yes, budget| H[find_claim_revisions — max 4 checks]
  G -->|no| I[Skip revisions]
  H --> J[Attach revisions to claim row]
  I --> J
  J --> K[claims_verified + sources_checked]
  K --> L[expand_sources + comparative coverage waterfall]
  L --> M[coverage_result + source_provenance + optional sources + echo_chamber]
  M --> N[run_global_perspectives + coverage_context]
  N --> O[generate_contextual_brief]
  O --> P[attach_article_analysis_signing]
  P --> Q[store_receipt]
  Q --> R[Return signed payload]

  S[GET /i/receipt_id HTML] --> T[load_stored_receipt]
  T --> U[get_coalition_map]
  U --> V[render_investigation_page — contextual_brief HTML]

  W[GET /v1/dig-deeper/receipt_id] --> X[Reload receipt — no DB write]
  X --> Y[Claude + NewsAPI + CourtListener heuristics]
```

**Drift (separate schedule):**

- **`POST /v1/schedule-drift/{receipt_id}`** — register URL for re-analysis.
- **`GET /v1/cron/drift`** — Render cron + secret header; processes **drift_schedule**.
- **`POST /v1/drift/run/{receipt_id}`** / **`GET /v1/drift/{receipt_id}`** — manual snapshot and read stored drift rows.
- Core: **`_run_drift_snapshot_core`** → **`compute_drift`**, **`insert_drift_snapshot`**.

---

## 7. Article receipt: what gets signed (reference)

Exact builder: **`report_api.build_article_analysis_signing_body`**.

Includes (subject to presence):  
`receipt_type`, `article`, `article_topic`, `named_entities`, `claims_extracted`, **`claims_verified`** (this is where **revision tracking** lives), `sources_checked`, `extraction_error`, `generated_at`, `source_provenance`, **`perspectives_grounded`**, `coverage_result`, **`global_perspectives`**, **`contextual_brief`**, conditional coalition-related keys (`volatility_score`, …), optional `sources`, `schema_version`.

**Not exhaustive for “full JSON”:** the returned object may include **`report_id`**, **`echo_chamber`**, etc.; verify **`build_article_analysis_signing_body`** before assuming they are hashed.

---

## 8. Drift tracking (summary)

- **Purpose:** Re-run comparative coverage + perspectives later; **diff** old vs new receipt via **`drift_engine.compute_drift`**; persist snapshots for timeline UI.
- **Infra:** Postgres tables via **`receipt_store.ensure_drift_tables`** and related helpers.
- **Ops:** Cron URL and **`CRON_SECRET`** documented in **`render.yaml`**.

---

## 9. External data sources (reference)

| Source | Typical use |
|--------|-------------|
| **GDELT** | Comparative article coverage (staged waterfall) |
| **NewsAPI** | Fallback coverage |
| **OpenFEC** | Campaign finance / candidates |
| **Congress.gov** | Legislation, votes |
| **CourtListener** | Opinions, dockets, citation-style lookups |
| **GovInfo** | Congressional Record, FR, statutes |
| **SEC EDGAR** | Filings, entity search |
| **ProPublica / IRS 990** | Nonprofit (dossier paths) |
| **Anthropic** | Claim extraction, perspectives, contextual brief, dig deeper JSON, narratives |

Adapter code lives primarily under **`apps/api/adapters/`** (Python). Rabbit Hole adds **TypeScript** sources under **`packages/adapters`**.

---

## 10. Environment variables (by priority)

### P0 — Service up; signing

| Variable | Role |
|----------|------|
| `FRAME_PRIVATE_KEY` | Ed25519 private key |
| `FRAME_PUBLIC_KEY` | Ed25519 public key |
| `FRAME_KEY_FORMAT` | e.g. `base64` |

Without P0 signing keys, receipts may return **`signed: false`** depending on code path.

### P1 — Core LLM

| Variable | Role |
|----------|------|
| `ANTHROPIC_API_KEY` | Claim extraction, global perspectives, contextual brief, dig deeper, dossier narratives |

### P2 — Article coverage and news

| Variable | Role |
|----------|------|
| `NEWSAPI_KEY` | Coverage fallback |

### P3 — Public records (feature-dependent)

| Variable | Role |
|----------|------|
| `FEC_API_KEY` | OpenFEC |
| `CONGRESS_API_KEY` | Congress.gov |
| `COURTLISTENER_API_KEY` | CourtListener |
| `GOVINFO_API_KEY` | GovInfo |
| `SEC_EDGAR_USER_AGENT` | SEC policy |

### P4 — Infra / jobs

| Variable | Role |
|----------|------|
| `DATABASE_URL` | Postgres |
| `REDIS_URL` | Worker queue |
| `CRON_SECRET` | Protects `/v1/cron/drift` |
| `FRAME_REPO_ROOT` | Resolve scripts from deploy cwd |

See also **`docs/CONTEXT.md`** for a longer table and Rabbit Hole–specific keys.

---

## 11. Deployment notes (Render)

From **`render.yaml`** and comments:

- **Web service** may use a **starter** plan; **cold starts** on low tiers add latency.
- **Cron** depends on **`FRAME_CRON_DRIFT_URL`** and **`CRON_SECRET`** alignment.
- **Worker** requires **`REDIS_URL`**.
- **Postgres free tier** expiry and **Redis** sizing warnings appear in **`render.yaml`** — treat as operational risk, not documentation noise.

---

## 12. Onboarding (five steps)

1. Read **`README.md`** (PUBLIC EYE behavior and known failure modes).
2. Read **`docs/CONTEXT.md`** (philosophy, endpoints, adapter list).
3. **`curl /health`** against the deployed API; clone repo and run API locally per README.
4. Trace **`POST /v1/analyze-article`** in **`main.py`** through **`attach_article_analysis_signing`** and open **`investigation_page.render_investigation_page`** for HTML.
5. **Memorize the signing rule (§5.2):** before changing UX or adding fields, check **`build_article_analysis_signing_body`** — **if it is not in the signing body, it is not evidence under the signature.**

---

## 13. Related docs

- **`docs/CONTEXT.md`** — extended context, Citizens United milestone, Rabbit Hole.
- **`docs/HANDOFF_SESSION.md`**, **`docs/RABBIT_HOLE_CONTEXT.md`** — session-specific depth.
- **`.cursorrules`** — dossier stack contract for entity enrichment.

---

## Epistemic status of this document

This architecture doc mixes **facts about the repo** with **engineering judgment**. Labels below apply to major claims.

| Label | Meaning |
|--------|--------|
| **Observed in code** | Verified by reading `main.py`, `report_api.py`, `receipt_store.py`, and related modules; filenames and behavior refer to current implementation. |
| **Inferred from patterns** | Product intent inferred from structure, prompts, and naming (e.g. “epistemic discipline” in contextual brief) where no single `assert` exists in code. |
| **Intended but not fully enforced** | Stated norms (e.g. parity between Python JCS and Node `jcs-stringify`) that **should** hold for verifiers but are not continuously tested in CI as of this writing. |

If a statement has no label, treat it as **observed in code** when it names a file or function; otherwise ask or verify.

---

## Architectural invariants (non-negotiables)

These are **prescriptive**: if violated **silently**, the product’s trust model erodes without an obvious outage.

1. **Signing slice is the attestation.** For `article_analysis`, only fields included in **`build_article_analysis_signing_body`** participate in **`content_hash`**. Anything else is UI or bookkeeping, not what the signature proves (see §5.2).

2. **Seal fails closed.** `attach_article_analysis_signing` must **never** return **`signed: true`** without a computed hash and signature. On exception, the implementation returns **`signed: false`**, **`signing_error`**, and **no** `content_hash`/`signature` — the HTTP response still returns a receipt body so the run is not lost, but **cryptographic proof is absent** (see Failure model).

3. **Uncertainty belongs in the hash or it is not sealed.** Disclaimers and model-generated blocks that are meant to be tamper-evident must be **inside the signing body** for that receipt type. Appending caveats **only** in HTML or in non-hashed JSON is **not** the same guarantee.

4. **FACT and INFERRED are not fused in contextual brief output.** The contextual-brief generator and renderer are written so that **typed** lines (FACT vs INFERRED vs contradiction rows) are **separate** — not the same sentence mixing attested datum and interpretation. (Prompt + HTML structure; **inferred from patterns**.)

5. **Partial beats fabricated.** If coverage, an adapter, or an LLM step fails or is empty, the pipeline should emit **explicit empties, nulls, or notes** — not invented sources, quotes, or coverage.

6. **Stored receipt is the source of truth for `/i/{id}`.** The investigation page reads the **payload** returned by `get_receipt` / stored JSON. If the brief is missing there, the UI cannot show it regardless of what was returned once on the wire.

7. **Dig deeper does not mutate the receipt.** `GET /v1/dig-deeper/{receipt_id}` is **read-only** with respect to the stored investigation payload; it cannot retroactively change what was signed.

8. **Drift is additive diagnostics.** Drift snapshots compare **later** runs to **stored** receipts; they do not rewrite the original signed payload.

9. **Verifier algorithm match.** Any **independent** verification of a receipt must use the **same** canonicalization (JCS) and **same** signing-body shape as `build_article_analysis_signing_body` for that type — otherwise “verification” is meaningless (**intended but not fully enforced** across all client implementations).

---

## Failure model

How the **article analysis** pipeline behaves when something breaks. **Default:** degrade gracefully; **exception:** cryptographic seal.

| Component / step | Typical failure | Effect on the receipt / response |
|------------------|-----------------|-----------------------------------|
| **fetch_article** | 422, timeout, parse error | **No receipt** — HTTP error. |
| **extract_claims** | LLM error or empty | **Receipt may still build** with `extraction_error` / empty claims. |
| **Per-claim adapters** (FEC, CourtListener, …) | Timeout, empty, deferred | **Claim row** shows `not_found` / `deferred` / `error` — **no global failure**. |
| **find_claim_revisions** | Timeout | **Revision list skipped** for that claim — logged. |
| **expand_sources / GDELT** | No coverage | **`coverage_result` reflects failure**; volatility/anchors may be null or placeholder notes. |
| **run_global_perspectives** | Exception | **Logged**; `global_perspectives` may be missing — **analysis continues**. |
| **generate_contextual_brief** | Empty dict or exception | **No `contextual_brief`** in payload — **analysis continues**; UI falls back to plain summary. |
| **`attach_article_analysis_signing`** | Key load, JCS, hash, sign error | **Receipt still returned** with **`signed: false`**, **`signing_error`** — **never** a fake `signed: true`. This is the **trust-layer** failure mode: **seal fails closed**, not HTTP hard fail. |
| **store_receipt** | DB error | **Logged**; caller may still return in-memory payload — **persistence risk** if ignored. |
| **Coalition map** (loaded at render) | Missing or async failure | **Page renders without** coalition slab — **receipt JSON unchanged**. |

**Distinction:** **Adapter/LLM** failures are **graceful degradation** of *content*. **Signing** failures are **graceful degradation** of *proof*: the user still gets a JSON payload, but **must not** treat it as cryptographically signed.

---

## Known debt and design rationale

### Known debt

| Debt | Notes |
|------|--------|
| **`main.py` (~6000+ lines)** | Single module holds most HTTP routes and orchestration. **Refactor path:** extract route groups (article, lens, receipts, Rabbit Hole, cron) into submodules or routers; keep **one** place that defines signing body per receipt type. |
| **JCS parity (Python vs TypeScript)** | Production hashing uses **`jcs_canonicalize.py`** in Python. Node **`scripts/jcs-stringify.mjs`** and TS packages may still exist for legacy paths. **Risk:** byte-level mismatch if someone verifies with the wrong canonicalizer. **Mitigation:** document canonical path; CI golden test comparing Python vs Node output for fixed payloads (**intended but not fully enforced**). |
| **Audio / long-form transcript pipeline** | README already notes uncertainty. End-to-end **article** path is the most exercised; **podcast / upload** tiers vary. |

### Design rationale (why X?)

| Question | Answer |
|----------|--------|
| **Why a monolith API?** | One deploy, one signing key story, shared Postgres and adapters. Splitting services before boundaries are stable would duplicate receipt contracts and signing. |
| **Why hybrid Python + Node build?** | Historical: TS packages for signing/adapters; Python for heavy I/O and LLM orchestration. **render.yaml** builds both. |
| **Why sign here (server)?** | Private key must not ship to browsers. **Verification** is public; **signing** is server-side only. |
| **Why receipts at all?** | Immutable, shareable **artifacts** with a defined semantic slice — not a session-only chat response. |
| **Why isn’t `echo_chamber` in the signing body?** | **Product decision / debt:** it is computed for display; it is **not** in `build_article_analysis_signing_body` today. **If** it must be sealed, add it to the builder and treat this as a **schema change** — not a silent tweak. |

---

*Last aligned to codebase: article analysis signing in `report_api.py`, analyze-article flow in `main.py`, drift and dig-deeper routes as described above.*
