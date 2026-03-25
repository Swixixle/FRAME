# Rabbit Hole — product context

Rabbit Hole is the consumer-facing depth-map product in this repository. It shares the cryptographic receipt spine and `POST /v1/verify-receipt` with Frame. The entry point differs: six stacked layers, narrative-first submit flow, pattern library, dispute log, and actor ledger — all oriented toward a **navigational map** of what the public record does and does not support at retrieval time.

**Companion doc:** `docs/CONTEXT.md` (Frame core, media receipts, jobs, env). **Start every session with the Session Start Checklist in CONTEXT.md.**

---

## Tone & voice

Rabbit Hole shows what the cited record states and what it does not state. It does not issue verdicts, moral judgments, or recommendations about what you should do or believe. Every surfaced line ties to a source id or to an explicit unknown; if something is missing from the record, the interface says so. This is not legal advice, medical advice, personal advice, or proof of anyone’s intent.

---

## Architecture (implemented)

| Area | Role |
|------|------|
| **`apps/api/depth_map.py`** | Declares six layers for `GET /v1/depth-map` (Layer 6 sealed until jurisdiction adapters exist). |
| **`apps/api/surface_adapter.py`** | Layer 1 — Anthropic-assisted surface extraction (`POST /v1/surface`). |
| **`apps/api/spread_api.py`** | Layer 2 — spread heuristics (`POST /v1/spread`). |
| **`apps/api/origin_api.py`** | Layer 3 — origin / first-instance heuristics (`POST /v1/origin`). |
| **`apps/api/actor_layer_api.py`** | Layer 4 **full stack** — runs `scripts/run-actor-layer.mjs` (Node): Internet Archive, Chronicling America, JSTOR check, RSS-style adapters, Wikidata / Wikipedia refs, etc., merged with `packages/actor-ledger/ledger.json`. |
| **`apps/api/actor_layer_fast.py`** | Layer 4 **fast path** — ledger word-boundary match only, no outbound HTTP; used inside **`POST /v1/report`** Ring 4 so reports stay fast on slow hosts (e.g. Render). |
| **`apps/api/pattern_api.py`** | Layer 5 — pattern match against signed library (`POST /v1/pattern-match`). |
| **`apps/api/report_api.py`** | Five-ring report: runs layers 1–5 in parallel (8s cap per ring), merges `sources_checked`, unknowns, citations. |
| **`apps/api/actor_ledger_api.py`** | CRUD-style access to append-only actor ledger backing `GET/POST /v1/actor/...`. |
| **`apps/api/dispute_api.py`** | Append-only dispute log for pattern entries. |
| **`packages/adapters`** | TypeScript depth helpers (`surface`, `spread`, `origin`, `actor`, `pattern`, `jurisdiction`) consumed by the Node actor script. |
| **`packages/actor-ledger`** | `ledger.json` + types — canonical actor rows, events, aliases. |
| **`packages/pattern-lib`** | Signed pattern catalog (`patterns.json`, `dist/`). |
| **`packages/dispute-log`** | Dispute persistence shape + `disputes.json`. |
| **`packages/types`** | Shared types including depth map, actor layer result, `sources_checked` with **`deferred`** status for Report Ring 4. |
| **`apps/web`** | Vite + React: **`DepthMap.jsx`** orchestrates submit → processing → receipt; **`SubmitView`**, **`ProcessingView`**, **`ReceiptView`**, **`WindGust`**, **`Procession`**, claims/entity subcomponents, **`sources_checked`** manifest with tier badges (**found** / **deferred** / **timeout** / **error** / **not_found**). |

**Two Layer 4 entry points (important):**

- **`POST /v1/actor-layer`** — full external corroboration (slow; many HTTP calls). Use when depth matters more than latency.
- **`POST /v1/report`** Ring 4 — **fast ledger-only**; archive/RSS/Wikidata rows in `sources_checked` are **`status: "deferred"`** with detail pointing callers at **`POST /v1/actor-layer`**.

---

## API endpoints (Rabbit Hole–centric)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/v1/depth-map` | Six layers metadata. |
| GET | `/v1/surface/slenderman` | Inoculation baseline; no API key. |
| POST | `/v1/surface` | Layer 1; requires `ANTHROPIC_API_KEY` for live model calls. |
| POST | `/v1/spread` | Layer 2. |
| POST | `/v1/origin` | Layer 3. |
| POST | `/v1/actor-layer` | Layer 4 full (Node subprocess). |
| POST | `/v1/report` | Layers 1–5 + merged manifest (Ring 4 fast path). |
| POST | `/v1/pattern-match` | Layer 5. |
| GET | `/v1/pattern-lib` | Library + transparency fields (e.g. unsigned count). |
| POST | `/v1/dispute` | Append dispute. |
| GET | `/v1/dispute/{pattern_id}` | List disputes for pattern. |
| GET | `/v1/actor/{slug}` | Actor ledger row. |
| GET | `/v1/actor/{slug}/events` | Event list. |
| POST | `/v1/actor/{slug}/events` | Append event (see API validation). |
| POST | `/v1/verify-receipt` | Shared verification (Frame + Rabbit Hole receipts). |

Frame-only routes (FEC, media, jobs, podcasts, etc.) live on the same FastAPI app; see `docs/CONTEXT.md` and `apps/api/main.py`.

---

## Adapters touching Layer 4 (full actor-layer stack)

Invoked from TypeScript (`packages/adapters/src/actor.ts`) / Node runner — not all may fire on every narrative. Report Ring 4 **does not** call these; it defers them.

- Internet Archive  
- Chronicling America  
- JSTOR (availability check)  
- RSS / site-style sources: e.g. Mysterious Universe, Anomalist, Cryptomundo, Coast to Coast, Singular Fortean, Fortean Times  
- Wikidata / Wikipedia refs / web inference (resolver paths as implemented in repo)

Exact adapter strings appear in `actor_layer_fast._DEFERRED_ADAPTERS` and in the Node layer output `sources_checked`.

---

## What’s built (March 25, 2026 snapshot)

- Depth map contract and API; Slenderman static baseline.  
- Surface / spread / origin / pattern Python adapters wired to HTTP.  
- Actor ledger JSON + API; seeded entries (e.g. folklore / cryptid rows as in repo).  
- Full actor-layer Node pipeline + **`POST /v1/actor-layer`**.  
- Five-ring **`POST /v1/report`** with parallel execution, merged `sources_checked`, citation strip on pattern hits.  
- Report Ring 4 **Python fast path** (no Node, no extra HTTP) + **`deferred`** provenance for external adapters.  
- Pattern library + disputes append flow + public listing.  
- Web UI: Rabbit Hole branding, depth progression, receipt / manifest panel, deferred badges.  
- TypeScript workspace builds (`npm run build`) including `deferred` in source-check types.

---

## Known gaps

- **Layer 6** — comparative jurisdiction / international adapters not built; depth map shows sealed floor.  
- **Actor ledger signing** — events appended; HALO-style signed sealed ledger pipeline still to formalize if required for receipts.  
- **Dispute moderation** — no `PATCH` / status workflow for disputes.  
- **`POST /v1/report` vs `POST /v1/actor-layer`** — operators must know Ring 4 is ledger-first; deep corroboration is opt-in via actor-layer.  
- **Slenderman prefill** — baseline exists as GET; UI may still want one-click load on first paint.  
- **Salience / Layer Zero** — rule-based until larger corpus (see CONTEXT).  
- **Anthropic / Render** — surface quality and latency depend on `ANTHROPIC_API_KEY` and cold start.

---

## Session notes — March 25, 2026

Build order (handoff):

1. **Types** — `ActorLayerResult`, `sources_checked`, **`deferred`** status, JSTOR and related source kinds as needed.  
2. **`packages/adapters`** — depth modules and actor parallel stack (archives, news archives, RSS, Wikidata-facing paths).  
3. **Node** — `scripts/run-actor-layer.mjs` orchestrates TS actor layer against `ledger.json`.  
4. **`POST /v1/actor-layer`** — FastAPI → `run_actor_layer` (subprocess).  
5. **`POST /v1/spread`**, **`POST /v1/origin`** — Python heuristics for layers 2–3.  
6. **`POST /v1/report`** — `report_api.build_extended_report_async`: gather surface, spread, origin, **actor fast**, pattern; merge unknowns + global `sources_checked`; ring-local citations.  
7. **Render / latency** — Ring 4 subprocess + many outbound HTTP calls caused timeouts; **`actor_layer_fast.run_actor_layer_fast`** added; report Ring 4 uses it; external adapters marked **`deferred`** with pointer to **`POST /v1/actor-layer`**.  
8. **UI** — DepthMap manifest: **`sources_checked`** table, **`deferred`** CSS/badge class.  
9. **Git** — landed on `main` with message(s) including Ring 4 fast-path fix; docs updated this session.

---

## Redundancy policy

If this file disagrees with `docs/CONTEXT.md` on **Frame core** (FEC, media, jobs, keys), trust **CONTEXT.md**. This file owns **Rabbit Hole depth stack**, **dual Layer 4 behavior**, and **web depth-map UX**.
