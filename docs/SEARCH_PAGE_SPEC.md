# PUBLIC EYE — Search (Cursor spec)

## Product distinction (non-negotiable framing)

**LexisNexis returns documents.** Their results are pages: “here are 44 articles about Tesla.”

**PUBLIC EYE search returns conflicts.** Results are **conflict bundles**: not a bibliography, but a map of how a topic is fought over — **by whom**, **how far apart** the coalitions are (volatility / divergence), **the irreconcilable gap**, coalition scale (outlets, countries), and whether the artifact is signed.

That single distinction shapes **everything**: default **sort** (volatility first, not recency alone), **facets** (volatility buckets, region signals, outlet-type counts on chains), **result cards** (two-anchor fight strip + GAP + coalition line, not snippets and metadata-only), and **empty state** (no matches → prompts toward analysis, not “try another database”).

LexisNexis is a **library**. PUBLIC EYE search is a **conflict map**.

---

## Build order

1. **Front page first** (see `docs/FRONT_PAGE_SPEC.md`): establishes visual language and `GET /v1/front-page`. Search **inherits** that language and adds the query layer.
2. Then search: migration → `search_service` → `/v1/search` + `/v1/search/suggest` → `search_page.py` → `GET /search` → header search on front + investigation pages.

---

## v1 search technology

- **PostgreSQL full-text search** only: `plainto_tsquery` over receipt payload fields + joined `coalition_maps` payload fields.
- **No** Elasticsearch, no new infra, no external search SaaS. Runs against existing `frame_receipts` (+ `coalition_maps` where present).
- When receipt volume is large (~10k+), revisit indexing and ranking; v1 optimizes for correctness and shipping.

---

## Indexed fields

| Source | Fields |
|--------|--------|
| `frame_receipts.payload` | `article_topic`, `article.title`, `narrative`, `query`, `named_entities` (as text) |
| `coalition_maps.payload` | `contested_claim`, `position_a.label`, `position_b.label`, `irreconcilable_gap` |

Migration: `apps/api/db/migrations/008_search_index.sql`  
Startup: `receipt_store.ensure_search_fts_indexes()`

---

## API

### `GET /v1/search`

Query params: `q`, optional `volatility_min`, `volatility_max`, `date_range` (`24h`|`7d`|`30d`|`90d`), `outlet_type`, `region` (comma-separated), `sort` (`volatility`|`date`), `limit`, `offset`.

Response shape: `query`, `total`, `results[]` (conflict bundle objects per nested spec in repo `search_service.build_search_result`), `facets` (`by_volatility`, `by_region`, `by_outlet_type`).

### `GET /v1/search/suggest`

`q` partial string → `suggestions[]` from topics, queries, contested claims (ILIKE, v1).

---

## HTML

- `GET /search?q=...` — server-rendered page: `apps/api/search_page.py` (`render_search_page`).
- Same warm paper `#F7F4EF`, Playfair volatility numerals, dark `#111` fight strips as front / investigation pages.

---

## Explicit non-goals (v1)

- Saved searches, history, accounts, boolean field parser, GDELT — defer.

---

## Acceptance: three-query test

Run against a DB seeded with real receipts + coalition maps (including at least one Middle East / Iran–Western style story, one Epstein / documents story ~66 divergence, and no “cats” content).

| Query | Expected |
|-------|----------|
| **Iran** | ≥1 conflict bundle with volatility **> 60**, two named anchor positions, **signed** receipt (per seeded data). |
| **cats** | **Empty** results + empty-state copy + prompts (analyze URL / front page). |
| **Epstein** | Bundle matching the Townhall / FBI-documents style analysis with divergence **~66** (tunable to seeded `divergence_score`). |

If all three behave, search v1 is **done**.

---

## Source notes

Detailed UI wire copy, filter bar labels, and JSON examples are kept aligned with implementation in:

- `apps/api/search_service.py`
- `apps/api/search_api.py`
- `apps/api/search_page.py`
- `apps/api/main.py` (`GET /search`)
