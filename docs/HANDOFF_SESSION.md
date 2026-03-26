# Session handoff — deep receipt, judicial network, Congress.gov (2026-03)

**Read first:** [`CONTEXT.md`](./CONTEXT.md) (living product + env + endpoints).

## What shipped

- **`POST /v1/deep-receipt`** can include **`historical_sources.judicial_network`** for queries matching campaign finance / Citizens United / PAC / First Amendment–class terms (see `apps/api/adapters/judicial_disclosures.py`).
- **Layer B** (`packages/sources/src/three-layer-narrative.ts`): model is instructed to add **two** `ThreadEntry` rows in **`layer_b.mutations`**, `source_type: "judicial_vote"`, using **`judicial_network.opinion_url`** — **five majority** + **four dissent** justices by **full name**, **Anthony Kennedy** as majority opinion author, **John Paul Stevens** as dissent author.
- **Signing:** `apps/api/deep_receipt_api.py` uses JCS + Ed25519; Layer C disclaimer is inside the signed body. **Post-signing** fields must not be added for semantic claims (removed ad-hoc `wealth_delta` pattern).
- **`POST /v1/congress-votes`:** `search_legislation` + `get_campaign_finance_votes()` → `legislation`, `campaign_finance_bills`.
- **`POST /v1/judicial-network`:** returns roster + `opinion_url` or empty wrapper with `note`.
- **`POST /v1/financial-disclosures`:** House/Senate index helpers only (not in deep-receipt gather).

## Key files

| Area | Path |
|------|------|
| Congress API | `apps/api/adapters/congress_votes.py` |
| SCOTUS roster / network | `apps/api/adapters/judicial_disclosures.py` |
| Financial indices | `apps/api/adapters/financial_disclosures.py` |
| Routes | `apps/api/main.py` |
| Deep receipt gather | `apps/api/deep_receipt_api.py` |
| Claude instructions | `packages/sources/src/three-layer-narrative.ts` |

**Deploy:** Render `buildCommand` runs `npm run build` so `packages/sources/dist` matches `src` (dist is gitignored).

## Verify in production

```bash
curl -sS --max-time 300 -X POST https://frame-2yxu.onrender.com/v1/deep-receipt \
  -H "Content-Type: application/json" \
  -d '{"query":"Citizens United campaign finance"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('signed', d.get('signed')); print(json.dumps(d['layer_b']['mutations'], indent=2))"
```

Expect **`judicial_vote`** entries naming all **nine** justices; **`source_url`** = CourtListener Citizens United opinion.

## Env (all referenced in production)

`ANTHROPIC_API_KEY`, `FRAME_PRIVATE_KEY`, `FRAME_PUBLIC_KEY`, `FRAME_KEY_FORMAT`, `FEC_API_KEY`, `CONGRESS_API_KEY`, `COURTLISTENER_API_KEY`, `GOVINFO_API_KEY`, `ASSEMBLYAI_API_KEY`, `SEC_EDGAR_USER_AGENT`, `FRAME_REPO_ROOT`.

## Sensible next work

- Enrich `legislation` with **vote roll calls** per bill (`get_bill_votes`) where API returns data.
- Harden **`financial_disclosures`** parsers against HTML/JSON drift; optional async job for deep-receipt.
- **FEC × Congress** crosswalk remains a product gap (named in `CONTEXT.md` known gaps).

---

*Replace or append this file when the next milestone lands so cold starts pick up the latest contract.*
