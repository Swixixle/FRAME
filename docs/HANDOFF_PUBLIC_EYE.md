# PUBLIC EYE / FRAME — handoff note (do not delete)

Single place for the next session to load context. Update this file when behavior or contracts change.

## Architecture boundaries

- **`comparative_coverage.py`**: Waterfall only — GDELT → NewsAPI → finalize / query expansion. **No** absence logic, no outlet parent-domain plumbing for absence.
- **`absence_signal.py`**: Absence signal computation lives here; `main` wires it after comparative coverage.

## Receipt contract (signed / persisted)

- **`coverage_core_entities`** on the stored receipt is **canonical** (what was signed). **`entity_persistence`** reads **`receipt["coverage_core_entities"]` only** — not `coverage_full["query_terms"]["core_entities"]`, so upstream query-term changes do not desync persistence from the receipt.

## `entity_evidence_log` semantics

- **Journalist** entities: log **`beat_coverage`** (plus `fec_donation`, `quote` where applicable).
- **Outlet** entities: log **`advertiser_relationship`**.
- Contradiction / filtering work later should key off **`evidence_type`**; do not collapse these two.

## Claim audit spine

- **`claim_audit_engine.py`** is a **stub** so `main.py` imports succeed. It must export whatever `main` imports (`AUDIT_RUBRIC_VERSION`, `CLAIM_EXTRACTION_VERSION`, `PARSER_EXTRACTION_VERSION`, `build_claim_audits_for_results`, `build_article_omission_analysis`, `build_audit_unknowns`, `compute_article_disposition`, `build_source_ledger`, `build_audit_summary_one_liner`). Full rubric is TODO.
- Startup import failures are usually **missing venv deps**, not this module — use `apps/api` venv + `requirements.txt`.

## Entity API routes (avoid duplicate paths)

- **Postgres investigation profile**: `GET /v1/entity/{slug}` and alias **`GET /api/entity/{slug}`**.
- **Missing profile row**: respond **200** with **`{"status":"pending","entity_slug":"..."}`**, not 404 — background persist may lag.
- **When row exists**: include **`"status":"ready"`** on the JSON body.
- **Evidence / contradictions**: `GET /v1/entity/{slug}/evidence`, `GET /v1/entity/{slug}/contradictions` (contradictions may still 404 if no profile — confirm if you want pending semantics there too).
- **Postgres list**: `GET /v1/entities` (profiles).
- **SQLite behavioral ledger** (`entity_receipts`): **`GET /v1/entity-ledger/{name}`**, **`GET /v1/entity-ledger/{name}/summary`**, **`GET /v1/entity-ledgers`** — do **not** reintroduce a second `GET /v1/entity/{name}` or duplicate `GET /v1/entities` on SQLite; `entity.html` uses `/v1/entity-ledger/`.

## Web: SOURCES & ACTORS

- **`fetchEntityProfile`**: tries **`/api/entity/{slug}`** then **`/v1/entity/{slug}`**; handles **`status: "pending"`**.
- **`SourcesAndActors.jsx`**: polls while pending; **skeleton** (not empty/error) when profile not ready.
- **Vite dev**: proxy **`/v1`** and **`/api`** to the API port.

## Follow-ups / unknowns (verify when touching receipts)

- Whether **`coverage_core_entities`** and entity slugs must be included in **signing body** (`report_api` / article analysis hash) if they must be tamper-evident on the receipt.
- Full implementations: narrative synthesizer, integrity scorer, contradiction engine, PolitiFact/MBFC/FactCheck.org breadth per spec.

## Cursor agents

Parent session transcripts: see Cursor agent-transcripts folder (cite parent uuid only per product rules).
