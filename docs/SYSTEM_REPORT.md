# Frame — System Report

This document is a technical orientation for engineers joining the Frame repository. It reflects the codebase and documentation as of the repository state used to produce this report (`docs/CONTEXT.md`, `docs/PROOF.md`, `apps/api/main.py`, TypeScript packages, adapters, web UI, scripts, and deployment configuration).

**Last updated:** 2026-03-22 — refreshed for `packages/*/package.json` `exports` pointing at `dist/`, the `packages/sources/index.js` shim for `scripts/` relative imports, and local CLI `.env` behavior.

---

## 1. What Frame Is

The one-sentence version is that Frame is a cryptographic receipt system for claims about public figures and media: it turns observations from public records and file analysis into Ed25519-signed, JCS-canonical JSON that anyone can verify without trusting Frame’s servers.

The full version is that Frame is epistemic infrastructure, not an arbiter of truth. It separates evidence from interpretation by requiring every signed payload to carry neutral claims, cited narrative sentences pointing at `SourceRecord` rows, and a mandatory split `unknowns` block distinguishing operational limits (timeouts, missing API keys, rate limits—things that might resolve with better infrastructure) from epistemic limits (what public records cannot establish—intent, causation, boundaries of disclosure regimes). Every claim carries `implication_risk` and, when that risk is `high`, a deterministic `implication_note` drawn from `IMPLICATION_NOTES` in `packages/types/src/implication-notes.ts`, not from an LLM. The mission is described in `docs/CONTEXT.md`: cryptographic fact-checking with citations and no judgment, working equally for statements that align with the record and those that do not.

---

## 2. What Is Live Right Now — Endpoints

The FastAPI application lives in `apps/api/main.py`. Static web assets under `apps/web/` are mounted at `/web` when present, and key pages are also served at top-level routes for convenience.

The root endpoint `GET /` returns a small JSON object with `status`, `service`, and a pointer to `/health` for clients that probe `/` instead of `/health`. The `GET /health` and `GET /health/` endpoints return `{"status":"ok","service":"frame-api"}` as liveness checks.

The demo single-page application is served by `GET /demo`, implemented as `FileResponse` to `apps/web/index.html` with no-store cache headers. The pitch deck is `GET /pitch`, serving `apps/web/pitch.html` the same way.

`GET /v1/schema-baselines` aggregates baseline status for five monitored sources (`fec`, `lda`, `propublica_990`, `wikidata`, `meta_ad_library`) by reading JSON files in `apps/api/baselines/` via `load_baseline` from `schema_monitor.py`. It returns a top-level `baselines` object keyed by source, truncated hashes, capture and verification timestamps, field counts, genesis flags, and optional `schema_changed` markers, plus `baselines_dir`, `schema_monitor_version`, and `generated_at`.

`GET /v1/adapters` returns the declared `SourceAdapterKind` strings used in the type system and a short note that Gap 3 routing sends OCR-derived claims to specific adapters.

`GET /v1/fec-search?name=` calls OpenFEC’s candidate search with `FEC_API_KEY` (defaulting to `DEMO_KEY`) and returns up to five candidate rows with `candidateId`, `name`, `office`, `state`, `party`, and `electionYears`.

`POST /v1/generate-receipt` accepts JSON `{"candidateId": "<FEC id>"}` and runs `scripts/generate-receipt.ts` via `npx tsx` under `_generate_fec_receipt_sync`, which builds and signs a live FEC receipt through the TypeScript pipeline in `packages/sources`, then `_with_receipt_url` persists the SQLite receipt row and adds `receiptUrl`.

`POST /v1/generate-lobbying-receipt`, `POST /v1/generate-combined-receipt`, `POST /v1/generate-990-receipt`, and `POST /v1/generate-wikidata-receipt` each invoke the corresponding script under `scripts/` (`generate-lobbying-receipt.ts`, `generate-combined-receipt.ts`, `generate-990-receipt.ts`, `generate-wikidata-receipt.ts`) with the same subprocess pattern: repo root as `cwd`, environment passed through, JSON on stdout parsed into a signed receipt and passed through `_with_receipt_url`.

`POST /v1/generate-ad-library-receipt` accepts `AdLibraryRequest` (`name`, optional `country`, `limit`) and uses `query_ad_library` in `apps/api/adapters/meta_ad_library.py` plus `_generate_ad_library_receipt_internal`, which builds a Frame-shaped payload and signs it via `_sign_frame_payload` (Node `scripts/sign-payload.ts`).

The async job API is `POST /v1/jobs` and the alias `POST /v1/intake`. Both validate that either `source_url` or `receipt_type` is set, create an in-memory `Job` via `create_job` in `job_store.py`, enqueue `_run_job` as a FastAPI background task, and return `job_id`, `status`, `description`, and `poll_url`. `GET /v1/jobs/{job_id}` returns `job.to_dict()` or 404 if unknown. `_run_job` handles `source_url` by awaiting `_handle_source_url_job` (fetch, Hive, OCR, payload assembly, signing); otherwise it dispatches on `receipt_type` to the same logical flows as the synchronous routes (`fec`, `lobbying`, `990`, `wikidata`, `combined`, `ad_library`). The `media` receipt type returns a placeholder object explaining that the full media pipeline is not wired as an async-only job. Failures call `mark_failed` with HTTP exception detail or string exception text; success calls `mark_complete` with the receipt and elapsed milliseconds.

`GET /v1/ledger` reads the SQLite `phash_ledger` table (up to 100 rows) for perceptual hash ledger inspection. `GET /v1/receipt/{receipt_id}` returns the stored JSON payload for a signed receipt from the `receipts` table. `GET /receipt/{receipt_id}` returns HTML from `apps/web/receipt.html` for a human shareable view that loads JSON from the JSON route client-side.

Entity ledger endpoints: `GET /v1/entity/{name}` and `GET /v1/entity/{name}/summary` aggregate rows from `entity_receipts` populated by `_index_entity_receipts` after certain signed flows; `GET /v1/entities` lists known entities. `GET /entity/{name}` serves `apps/web/entity.html` for a styled entity page.

`POST /v1/analyze-media` accepts uploaded file bytes and runs the media analysis pipeline in `adapters_media` and related helpers in `main.py`: hashing, optional Hive and OCR, claim extraction, optional `route_claim` from `apps/api/router.py`, and a structured body suitable for signing. `POST /v1/sign-media-analysis` takes a `MediaAnalysisRequest` and runs `_sign_media_analysis_core`, which calls `scripts/sign-media-analysis.ts` with `npx tsx`. `POST /v1/analyze-and-verify` reads the file, builds the analysis response, validates into `MediaAnalysisRequest`, signs, and finalizes with `_finalize_media_sign` including entity indexing.

`POST /v1/analyze-podcast` and `POST /v1/analyze-and-verify-podcast` use `adapters_podcast.py` for download, Whisper transcription, optional Anthropic claim extraction, and the same signing path as media.

`POST /v1/jcs-sha256` exposes `sha256_hex_jcs` for debugging parity with TypeScript JCS. `POST /v1/verify-receipt` accepts a Pydantic `SignedReceipt`, replicates the content-hash check and Ed25519 verification using `jcs_canonicalize` (Node `scripts/jcs-stringify.mjs`) and `cryptography`’s Ed25519 public key loader, and returns `{"ok": bool, "reasons": [...]}`.

---

## 3. The Receipt Schema

The canonical TypeScript definitions live in `packages/types/src/index.ts`. A `FrameReceiptPayload` is the preimage for signing: `schemaVersion` is fixed at `"1.0.0"`; `receiptId` uniquely identifies the receipt; `createdAt` is an ISO 8601 timestamp; `claims` is an array of `ClaimRecord` objects; `sources` is an array of `SourceRecord` objects; `narrative` is an array of `NarrativeSentence` objects each with `text` and `sourceId` (every sentence must cite a source row); `unknowns` is an `UnknownsBlock` with `operational` and `epistemic` arrays of `UnknownItem` (`text` plus `resolution_possible`); `contentHash` is the SHA-256 hex digest of the JCS-canonical body excluding `contentHash`, `signature`, and `publicKey`; optional `signerPublicKey` may appear for UX. `FrameSignedReceipt` extends this with `signature` (base64 Ed25519) and `publicKey` (base64 SPKI DER).

`ClaimRecord` carries `id`, `statement`, optional `assertedAt`, `type` (`observed` | `inferred` | `unknown`), `implication_risk` (`low` | `medium` | `high`), and `implication_note` when risk is `high`—enforced by `buildClaim` in TypeScript and by Pydantic validators on `ClaimRecord` in `main.py` for verification. `SourceRecord` carries `id`, `adapter` (`SourceAdapterKind`), `url`, `title`, `retrievedAt`, optional `externalRef`, and optional `metadata` for structured adapter-specific fields. The schema exists so that receipts are stable, machine-verifiable, and safe to render without smuggling editorial judgment inside “neutral” fields: unknowns and implication boundaries are first-class.

---

## 4. The Signing Pipeline

End-to-end, signing is defined in TypeScript in `packages/signing/index.ts` and invoked in production either through standalone scripts (`scripts/generate-receipt.ts` and siblings, `scripts/sign-payload.ts`, `scripts/sign-media-analysis.ts`) or duplicated in Python verification on `POST /v1/verify-receipt`.

The `canonicalize` npm package (RFC 8785 JCS) is required via `createRequire` in `packages/signing/index.ts` as `jcsCanonicalize`. `computeContentHash` builds a copy of the payload omitting `contentHash`, `signature`, and `publicKey`, JCS-canonicalizes it, and SHA-256 hashes it. `signReceipt` optionally assigns `contentHash`, injects `publicKey` as base64 SPKI DER from the private key, then `signingDigest` hashes the JCS form of the payload with only `signature` removed (so the digest includes `contentHash` and `publicKey`). The Ed25519 signature from Node’s `crypto.sign` is base64-encoded into `signature`.

Python’s `jcs_canonicalize` in `main.py` runs `node scripts/jcs-stringify.mjs` with `cwd` set to `_repo_root()` so the same JSON canonicalization library is used as in TypeScript. `_sign_frame_payload` runs `npx tsx scripts/sign-payload.ts`, which reads JSON from stdin, loads `FRAME_PRIVATE_KEY` using `FRAME_KEY_FORMAT` (`pem` or `base64`), calls `signReceipt` from `packages/signing`, and prints the signed JSON. `verify_receipt` in `main.py` recomputes `contentHash` and verifies the signature against the digest of the signing body.

Files involved: `packages/signing/index.ts` (core algorithms), `packages/types` (payload shapes), `scripts/jcs-stringify.mjs` (Python parity), `scripts/sign-payload.ts` (stdin/out signing for Python callers), `scripts/generate-*.ts` (per-domain receipt builders that call signing), `scripts/sign-media-analysis.ts` (media analysis JSON to signed receipt), and `main.py` (`jcs_canonicalize`, `_sign_frame_payload`, `_sign_media_analysis_core`, `verify_receipt`).

### Node packages and script resolution (`dist` and the `packages/sources` shim)

`packages/types` and `packages/sources` compile from `packages/*/src/` into `packages/*/dist/` via each package’s `tsconfig.json` and the root `npm run build` (`tsc -b tsconfig.build.json`, which references `packages/types`, `packages/sources`, and `packages/signing`). Each of `packages/types/package.json` and `packages/sources/package.json` sets `main`, `types`, and `exports["."].import` / `types` to `./dist/index.js` and `./dist/index.d.ts`, so bare imports like `import type { FrameReceiptPayload } from "@frame/types"` in `scripts/sign-payload.ts` resolve to the emitted JavaScript after build.

The receipt CLI scripts (`scripts/generate-receipt.ts`, `generate-lobbying-receipt.ts`, `generate-combined-receipt.ts`, `generate-990-receipt.ts`, `generate-wikidata-receipt.ts`) use **relative** specifiers: `import { ... } from "../packages/sources/index.js"`. Node and `tsx` resolve that as a **file path** under the repo; `package.json` `exports` does not rewrite those paths. Source now lives under `packages/sources/src/index.ts`, so the compiled module is `packages/sources/dist/index.js`. To avoid changing every script, the repo includes **`packages/sources/index.js`**, an ESM file that `export * from "./dist/index.js"`. Without this shim (and without `npm run build` populating `dist/`), those imports fail with `ERR_MODULE_NOT_FOUND` for `.../packages/sources/index.js`. On Render, the build step must complete before uvicorn runs subprocesses that invoke these scripts.

**Local CLI note:** these scripts read `process.env` only; they do **not** automatically load `apps/api/.env`. From the **repository root**, run `set -a && source apps/api/.env && set +a` (or export `FRAME_PRIVATE_KEY`, `FRAME_PUBLIC_KEY`, and optional `FEC_API_KEY`) before `npx tsx scripts/generate-receipt.ts <candidateId>`.

---

## 5. Every Adapter

The TypeScript adapters in `packages/sources/src/index.ts` implement the `SourceAdapter` async function type: given a `SourceQuery`, return `SourceAdapterResult` with `sources`, optional `errors`, optional `metadata`. Live builders include FEC campaign finance (`fetchFecContext`, `buildLiveFecReceipt`), Senate LDA (`fetchLobbyingContext`, `buildLiveLobbyingReceipt`, `buildLobbyingCrossReference`), IRS 990 via ProPublica Nonprofit Explorer (`fetch990Context`, `buildLive990Receipt`), Wikidata (`fetchWikidataContext`, `buildWikidataReceipt`), and combined politician flows. These hit OpenFEC, `lda.senate.gov`, ProPublica’s API, and Wikidata’s `wbsearchentities` / entity APIs. Limitations are encoded as operational and epistemic unknowns: rate limits, partial search results, ambiguity of names, and the fact that disclosed filings do not prove intent or wrongdoing.

Python-side HTTP helpers for Gap 3 live in `apps/api/adapters_media.py`: `fetch_fec_by_name`, and related functions for IRS 990, LDA, Congress.gov, and Wikidata—called synchronously from async routes via `asyncio.to_thread` where needed. Congress bill search requires `CONGRESS_API_KEY` in the environment.

`apps/api/adapters/meta_ad_library.py` implements `query_ad_library` against Meta’s Graph API `ads_archive` endpoint when `META_AD_LIBRARY_TOKEN` is set. Without the token it returns a structured `status: unavailable` object and operational unknown text; with the token it returns normalized ads, spend ranges, and epistemic caveats about political/issue ad disclosure limits. Meta’s spend ranges and incomplete coverage are documented in receipt unknowns.

`apps/api/adapters/fetch_adapter.py` defines `FetchAdapter`, `FetchResult`, `ChainOfCustodyBlock`, and exceptions `AdapterUnavailableError` and `FetchError`. `YtDlpAdapter` in `ytdlp_adapter.py` uses `yt-dlp` for social hosts listed in `SOCIAL_DOMAINS`, downloads to a temp directory, computes SHA-256, and fills `ChainOfCustodyBlock` with timestamp, URL, HTTP status, response headers, TLS verification, resolved server IP, and `fetch_adapter_version`. `DirectHttpAdapter` in `direct_http_adapter.py` uses `httpx` for direct HTTP GETs up to 50MB, same chain-of-custody fields. `apps/api/adapters/router.py` selects `YtDlpAdapter` when the URL matches social domains, else `DirectHttpAdapter` for http(s) URLs.

`apps/api/adapters_podcast.py` downloads audio with `yt-dlp`, trims with ffmpeg, transcribes with Whisper (`FRAME_WHISPER_MODEL`, default `base`), and may call Anthropic for claim extraction when `ANTHROPIC_API_KEY` is set—subject to `FRAME_PODCAST_MAX_SECONDS` (default 30 minutes) and temp directories under `FRAME_PODCAST_TMP`.

---

## 6. The Job System

`job_store.py` holds a module-level dictionary `_jobs` mapping `job_id` strings to `Job` instances. `Job` fields include `status`, `description`, timestamps, optional `receipt`, optional `error`, and optional `processing_time_ms`. `create_job` generates ids like `job_<uuid hex>`. `mark_processing` sets status to `processing` and records `started_at`. `mark_complete` sets `complete`, stores the receipt, `completed_at`, and computes `processing_time_ms` from the monotonic start millisecond passed in. `mark_failed` sets `failed` and stores an error string.

The state machine is: `pending` immediately after creation, then `processing` when `_run_job` begins, then either `complete` with a receipt object or `failed` with an error string. There is no retry or dead-letter queue. `HTTPException` from synchronous adapter logic becomes a JSON-string detail via `_http_exception_detail`; generic exceptions become string errors. On server restart the dictionary is empty—no persistence.

---

## 7. The FetchAdapter

The interface contract is in `fetch_adapter.py`: an abstract `fetch` method returning `FetchResult` and a `can_handle` predicate. `FetchResult` includes `file_bytes`, `source_url`, `content_type`, `file_extension`, `sha256_hash`, `chain_of_custody` (`ChainOfCustodyBlock`), optional `temp_file_path`, and a `metadata` dict. `ChainOfCustodyBlock` captures `retrieval_timestamp` (ISO UTC), `source_url`, `http_status`, `response_headers`, `tls_verified`, `server_ip`, and `fetch_adapter_version` so that media receipts can state exactly how bytes were obtained.

The two implementations are `YtDlpAdapter` for social media domains and `DirectHttpAdapter` for generic HTTPS URLs. The router function `get_adapter_for_url` in `adapters/router.py` prefers yt-dlp when `can_handle` is true, otherwise direct HTTP. In `_handle_source_url_job` inside `main.py`, the chosen adapter is invoked, bytes are hashed, Hive and OCR run in parallel with timeouts, claims and unknowns are assembled, and the payload is signed with `scripts/sign-payload.ts`. Chain of custody is copied into the receipt metadata under `meta.chain_of_custody` alongside platform metadata, Hive detection, and OCR results.

---

## 8. The Schema Monitor

`schema_monitor.py` implements structural fingerprinting for external JSON. `_extract_schema` walks nested dicts and lists, emitting tuples of `path`, `node_type`, `scalar_type`, and `cardinality` with field names normalized via `_normalize_field_name`. `fingerprint_schema` computes `full_schema_hash` (SHA-256 of sorted path lines) and `critical_fields_hash` from the per-source field sets defined in `CRITICAL_FIELDS` (for example FEC candidate money fields, LDA registrant fields, 990 financial fields, Wikidata entity fields, Meta ad fields). `capture_baseline` stores a JSON document under `apps/api/baselines/baseline_{source_id}.json` via `save_baseline`, which on first write records genesis; on subsequent runs with unchanged full hash updates `last_verified_at`; on hash change appends version history and sets `schema_changed`. `compare_to_baseline` can diff a new response against stored tuples and classify severity (critical fields removed vs added fields), returning a dict that explicitly states Rule Change Receipt logic is not implemented—this is the drift hook for future work.

At startup, `capture_schema_baselines` in `main.py` runs `asyncio.gather` on `_capture_fec_baseline`, `_capture_lda_baseline`, `_capture_990_baseline`, `_capture_wikidata_baseline`, and `_capture_meta_ad_library_baseline`, each of which fetches a minimal real sample and passes it to `capture_baseline` from `schema_monitor.py`. Failures are logged per source without blocking startup. After baselines, `_verify_signing_pipeline` runs a minimal signed payload through `_sign_frame_payload` to confirm Node signing works.

---

## 9. The Media Pipeline

Upload path: `POST /v1/analyze-media` receives `UploadFile`, reads bytes, and delegates to helpers that compute SHA-256 hashes, optional perceptual hash via imagehash, optional Hive moderation via `HIVE_API_KEY`, and OCR via Tesseract through `adapters_media` helpers such as `_run_ocr` and `_run_hive_detection`. Claims may be extracted using Anthropic when `ANTHROPIC_API_KEY` is configured. `route_claim` from `apps/api/router.py` maps each extracted claim to adapter specs; `dispatch_adapter` in `adapters_media` runs the appropriate Python fetch and merges `adapterResults` into the payload for signing.

URL path: `POST /v1/jobs` with `source_url` triggers `_handle_source_url_job`, which uses `get_adapter_for_url`, downloads bytes, then follows the same Hive/OCR/claim/unknowns path as uploads, signs with `sign-payload.ts`, and completes the job. `POST /v1/analyze-and-verify` combines upload analysis + media signing + entity ledger in one request.

`GET /v1/ledger` and `_add_to_phash_ledger` / `_check_phash_ledger` implement the perceptual hash ledger in SQLite (`FRAME_DB_PATH` defaults to `/tmp/frame_ledger.db`), including near-duplicate detection with Hamming distance when `imagehash` is available.

---

## 10. The Demo UI

`apps/web/index.html` is a large single-page layout with navigation tabs implemented as buttons `showMainPanel('records' | 'media' | 'podcast')`. The default visible panel is **Public records**: search inputs for FEC, lobbying, 990, Wikidata, Meta Ad Library, and combined flows, wired to the public API endpoints with `fetch` and a configurable `API_BASE`. The **Media** tab provides a drag-and-drop zone and file input for images and video, an optional URL field, mode toggles including ad spend, and an **Analyze** button that calls `analyzeMediaTab()`: either `POST /v1/jobs` with `source_url` and polling, or `POST /v1/analyze-media` followed by `POST /v1/sign-media-analysis` for uploads, then renders the receipt card sections in order: WHAT WAS CHECKED, FILE FINGERPRINT, AI DETECTION (conditional), TEXT FOUND IN FILE (conditional), CHAIN OF CUSTODY, WHAT WE DON'T KNOW, SOURCES CONSULTED, VERIFY. The **Podcast / Video** tab posts to `analyze-podcast` or combined verify endpoints depending on the UI wiring.

Below the tabs, the page includes a **Verified Receipt** output area for the public-records flows, **Evidence** and **Primary Sources** sections, a **Sample Receipt** block using `demo-payload.json`, and **Verify Any Receipt** paste JSON to `POST /v1/verify-receipt`. When the user hits **Analyze** on media, the client either polls jobs for URL jobs or runs the synchronous upload+sign path; the receipt card is populated from the JSON response fields.

---

## 11. The Pitch Deck

`apps/web/pitch.html` is a React 18 application loaded from CDN with Babel in-browser. The `FramePitch` component uses tab state 0–8 for nine sections. Tab 0 **Mission** states that Frame turns claims into signed receipts with neutral narrative, `unknowns`, and Ed25519 over JCS. Tab 1 **Problem** contrasts slow fact-checks with fast-spreading clips and explains separation of fetch, adapters, and signing. Tab 2 **Evidence chain** explains narrative `sourceId` citations, `implication_risk`, and deterministic `implication_note`, and embeds a monospace **ReceiptMockup** showing fake `contentHash` and signature lines. Tab 3 **Adapters** lists FEC, Senate LDA, IRS 990 via ProPublica, Wikidata, Congress normalized to `SourceRecord`, and mentions the OCR router. Tab 4 **Signing** describes SHA-256 of JCS body as `contentHash` and signing over the unsigned payload including `contentHash`, matching Python verification. Tab 5 **Async jobs** documents `POST /v1/jobs` and `POST /v1/intake` versus synchronous `/v1/generate-*`. Tab 6 **FetchAdapter** explains URL in → `FetchResult` with `ChainOfCustodyBlock`, naming `YtDlpAdapter` and `DirectHttpAdapter`. Tab 7 **Roundtable** renders the `RoundtableSection` accordion with four stakeholder cards (Journalism, Governance, Platforms, Researchers). Tab 8 **Roadmap** mentions persistent job store, Hive, entity ledger, embeddable receipt cards, and a stable signing core.

---

## 12. The Type System

`ImplicationRisk` is the union `"low" | "medium" | "high"` describing how strongly a reader might infer more than the cited record supports. `ClaimRecord` binds `id`, `statement`, optional `assertedAt`, `type`, `implication_risk`, and optional `implication_note` required when risk is high. `UnknownsBlock` splits `operational` and `epistemic` arrays; helpers `emptyUnknowns`, `opUnknown`, `epiUnknown`, and `mergeUnknowns` construct and merge items. `buildClaim` enforces the high-risk note requirement deterministically.

`IMPLICATION_NOTES` in `implication-notes.ts` maps `EvidenceCategory` (`campaign_finance`, `lobbying`, `paid_advertising`, `nonprofit_financials`, `media_hash`, `ai_detection`, `affiliation`, `cross_reference`) to single-sentence boundary strings. `getImplicationNote` returns the string for a category. These strings are the only allowed `implication_note` text for those categories when wired through governance code paths.

---

## 13. The Deployment

`render.yaml` declares a Render web service `frame-api` with `runtime: python` and `rootDir: .` so the repository root contains `node_modules` and `scripts`. The `buildCommand` exports `DEBIAN_FRONTEND=noninteractive`, runs `apt-get update -y`, installs `tesseract-ocr` and `ffmpeg`, `npm ci`, `npm run build` (TypeScript project references via `tsconfig.build.json`), then `pip install -r apps/api/requirements.txt`. The `startCommand` is `cd apps/api && uvicorn main:app --host 0.0.0.0 --port $PORT`. Environment variables declared in the file include `FRAME_REPO_ROOT` set to `/opt/render/project/src`, `FRAME_KEY_FORMAT` `base64`, and `FRAME_PRIVATE_KEY` / `FRAME_PUBLIC_KEY` as secrets.

The startup sequence on load runs `capture_schema_baselines` which logs `[startup] REPO_ROOT` from `_repo_root()`, `scripts/` and `node_modules/` existence, then `[schema_monitor]` lines per source, then `[schema_monitor] Baseline capture complete.`, then `_verify_signing_pipeline` which prints signing OK or failure details. If `_verify_signing_pipeline` fails, receipt generation paths that depend on `sign-payload.ts` will fail in production similarly.

---

## 14. Environment Variables

`FRAME_REPO_ROOT` overrides the inferred repo root from `main.py`’s path so `npx tsx` runs with `cwd` pointing at the checkout on Render; without it, if `cwd` were wrong, Node would not resolve `scripts/` or `node_modules`. `FRAME_PRIVATE_KEY` is required for signing in any script that calls `signReceipt` or `sign-payload.ts`; missing key throws in Node. `FRAME_KEY_FORMAT` should be `base64` when the private key is stored base64-encoded in Render; `sign-payload.ts` decodes to PEM. `FRAME_PUBLIC_KEY` is used by some scripts (e.g. `generate-receipt.ts` for embedding) when exporting public material. `FEC_API_KEY` defaults to `DEMO_KEY` but production should set a real key for reliable OpenFEC access. `META_AD_LIBRARY_TOKEN` enables live Meta Ad Library queries; without it, `query_ad_library` returns unavailable status and receipts document that gap. `HIVE_API_KEY` enables Hive AI scores; without it, detection returns `detector: none` style results. `ANTHROPIC_API_KEY` is required for Claude-based claim extraction in media and podcast flows when those code paths are used. `CONGRESS_API_KEY` is required for Congress.gov adapter calls in `adapters_media.py`. `FRAME_DB_PATH` overrides SQLite location for ledger and receipts. `FRAME_PUBLIC_BASE_URL` overrides the base used in `receiptUrl` generation. `FRAME_PODCAST_MAX_SECONDS`, `FRAME_PODCAST_TMP`, and `FRAME_WHISPER_MODEL` tune podcast processing. `META_AD_LIBRARY_TOKEN` is read in `meta_ad_library.py` via `os.getenv("META_AD_LIBRARY_TOKEN")` (some docs refer to the same integration as “Meta Ad Library token”). For **local** runs of `scripts/generate-*.ts`, remember that unlike uvicorn, the CLI does not load `apps/api/.env` unless you `source` it or export variables in the shell.

---

## 15. Known Gaps

`docs/CONTEXT.md` lists: Hive key not configured; Meta user token expiry vs system user; salience rule-based fallback until corpus N=100; music dossier specced but not built; Rule Change Receipt generation not implemented; in-memory job store; browser extension called skeleton; custom domain not configured. `docs/PROOF.md` repeats Meta token, Hive, salience, music, schema monitoring without Rule Change Receipts, and ephemeral job store. Additional gaps surfaced in context include: `POST /v1/jobs` with `receipt_type: media` not wired to full pipeline; SQLite ledger reset on ephemeral disk; suggested primary URLs from Claude sometimes 404/403; Spotify app links unsupported for podcast adapter.

---

## 16. What Frame Is Not

From `docs/CONTEXT.md` and `README.md`: Frame is not a fact-checker in the sense of issuing verdicts; not an AI trust score; not a misinformation classifier; not a competitor to C2PA. It is a receipt system that proves what was observed and signed, for true and false claims alike.

---

## 17. The Maturity Ladder

**Frame Core (built):** Public records—FEC, LDA, 990s, Wikidata—for subject classes politicians, nonprofits, public figures. **Frame Media (in progress):** Media provenance—SHA-256, OCR, Whisper, Hive, yt-dlp—for social clips, screenshots, uploads. **Frame Network (not started):** Distribution tracking via perceptual hashing and ledger—partially implemented as SQLite phash ledger but documented as future Network tier until stable.

---

## 18. The Subject Class Map

The table in `docs/CONTEXT.md` states: **politician** (Core: FEC, LDA, Wikidata — Built); **nonprofit** (Core: 990, Wikidata — Built); **public_figure** (Core: Wikidata — Built); **social_media_clip** (Media: yt-dlp, SHA-256, OCR, Ad Library — Built); **screenshot** (Media: SHA-256, OCR, Ad Library — Built); **artist** (Music: AcoustID, Librosa, Rights — Specced); **recording** (Music: LibrosaAnalysis, SimilarSongs — Specced); **corporation** (Future: SEC EDGAR, PACER — Not started); **court_case** (Future: PACER — Not started).

---

## 19. The Test Suite

The Vitest suite in `packages/signing/__tests__/manchin.test.ts` contains five tests: JCS stability across key reordering; rejection of JSON.stringify as a hash substitute; `validateNarrative` passes on the Manchin fixture from `fixtures/manchin-payload.ts`; stable `contentHash` and successful `signReceipt`/`verifyReceipt` with a generated Ed25519 key; and failure of verification when narrative text is tampered after signing. The `bash` script `scripts/e2e-test.sh` exercises the deployed API: health, demo HTML, pitch HTML, FEC search, generate-receipt signature and unknowns, verify-receipt, lobbying, 990, Wikidata, ad library receipt, async job creation, 404 on unknown job, schema baselines JSON, and finally polls an FEC job until complete or timeout—fifteen checks total when production matches the repository.

---

## 20. Full File Tree (Source Files)

The following is a one-line purpose for each primary source file in the repository (excluding `node_modules`, Python `.venv`, and build artifacts). Paths are relative to the repo root.

`.github/copilot-instructions.md` — Editor guidance for GitHub Copilot. `.gitignore` — ignores for build outputs and secrets. `README.md` — public overview, curl examples, API table, stack. `package.json` — npm scripts (`build`, `test`, `e2e`, `proof:date`, etc.) and workspace config. `package-lock.json` — lockfile for npm. `render.yaml` — Render deployment build and start commands. `tsconfig.json` — solution references for editor tooling. `tsconfig.base.json` — shared TypeScript compiler defaults. `tsconfig.build.json` — project references for `packages/types`, `packages/sources`, `packages/signing`. `vitest.config.ts` — Vitest config with `@frame/types` path alias. `docs/CONTEXT.md` — long-form project context, roadmap, gaps. `docs/PROOF.md` — falsifiable curl proofs and architecture verification table. `docs/SYSTEM_REPORT.md` — this full-system technical report. `docs/DOMAIN.md` — custom domain checklist (referenced in README). `docs/HANDOFF.md` — handoff notes. `apps/api/main.py` — FastAPI application, all routes, media and podcast pipelines, signing integration, SQLite ledger, startup baselines. `apps/api/schema_monitor.py` — schema fingerprinting and baseline capture. `apps/api/job_store.py` — in-memory job store. `apps/api/implication_notes.py` — Python `IMPLICATION_NOTES` dict mirroring `packages/types` for API-side copy. `apps/api/router.py` — `route_claim` heuristics for OCR claims. `apps/api/adapters_media.py` — sync HTTP adapter callers for FEC, 990, LDA, Congress, Wikidata. `apps/api/adapters_podcast.py` — podcast download, Whisper, claim extraction. `apps/api/requirements.txt` — Python dependencies. `apps/api/baselines/baseline_*.json` — committed schema baseline snapshots per source. `apps/api/adapters/__init__.py` — package marker. `apps/api/adapters/fetch_adapter.py` — FetchAdapter contract and dataclasses. `apps/api/adapters/router.py` — `get_adapter_for_url`. `apps/api/adapters/ytdlp_adapter.py` — yt-dlp implementation. `apps/api/adapters/direct_http_adapter.py` — httpx direct download implementation. `apps/api/adapters/meta_ad_library.py` — Meta Graph API adapter. `apps/web/index.html` — main demo UI. `apps/web/pitch.html` — pitch deck SPA. `apps/web/receipt.html` — shareable receipt HTML shell. `apps/web/entity.html` — entity record page. `apps/web/demo-payload.json` — sample signed payload for demo. `apps/extension/manifest.json` — MV3 extension manifest. `apps/extension/popup.html` — extension popup UI. `apps/extension/README.md` — extension documentation. `apps/macos/README.md` — macOS capture documentation. `apps/macos/sync-embedded-script.sh` — sync script for embedded shell. `apps/macos/extras/swiftbar-example.sh` — SwiftBar example. `apps/macos/FrameCapture.app/Contents/Resources/frame-capture.sh` — bundled capture script. `packages/types/package.json` — `@frame/types` package metadata. `packages/types/tsconfig.json` — types project build config. `packages/types/src/index.ts` — shared TypeScript interfaces and helpers. `packages/types/src/implication-notes.ts` — `IMPLICATION_NOTES` and `getImplicationNote`. `packages/sources/package.json` — `@frame/sources` dependency on types. `packages/sources/tsconfig.json` — sources project config. `packages/sources/src/index.ts` — monolithic FEC/LDA/990/Wikidata adapter and receipt builders. `packages/sources/index.js` — ESM shim re-exporting `./dist/index.js` for `../packages/sources/index.js` imports from `scripts/`. `apps/api/.env.example` — committed template for local env variable names; real secrets stay in gitignored `apps/api/.env`. `packages/signing/package.json` — signing package metadata. `packages/signing/tsconfig.json` — signing project config. `packages/signing/index.ts` — JCS, content hash, sign, verify. `packages/signing/__tests__/manchin.test.ts` — five Vitest tests. `packages/signing/__tests__/fixtures/manchin-payload.ts` — Manchin fixture builder. `packages/narrative/package.json` — narrative package. `packages/narrative/tsconfig.json` — narrative config. `packages/narrative/governance.ts` — `validateNarrative` and governance rules. `packages/entity/package.json` — entity package. `packages/entity/tsconfig.json` — entity config. `packages/entity/index.ts` — entity types/helpers. `scripts/e2e-test.sh` — production e2e smoke script. `scripts/sign-payload.ts` — stdin/out signing for Python jobs. `scripts/sign-media-analysis.ts` — sign media analysis JSON. `scripts/jcs-stringify.mjs` — Node JCS helper for Python. `scripts/generate-receipt.ts` — CLI FEC receipt generation. `scripts/generate-lobbying-receipt.ts` — CLI LDA receipt. `scripts/generate-combined-receipt.ts` — CLI combined receipt. `scripts/generate-990-receipt.ts` — CLI 990 receipt. `scripts/generate-wikidata-receipt.ts` — CLI Wikidata receipt. `scripts/generate-keys.ts` — key generation utility. `scripts/seed-demo.ts` — seed demo payload. `scripts/regen-demo-payload.ts` — regenerate demo JSON. `scripts/test-fec.ts` — local FEC test helper. `scripts/frame-capture.sh` — macOS region capture to API. `frame-capture.sh` at repo `scripts/` is the canonical path referenced in docs.

---

*This report lives at `docs/SYSTEM_REPORT.md` and should be updated when architecture, package layout, or endpoints change materially.*
