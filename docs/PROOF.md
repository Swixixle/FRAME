# Frame — Build Proof

This document captures verified proof of the core pipeline as of March 19-20 2026.

## FEC name search (live)

```bash
curl "https://frame-2yxu.onrender.com/v1/fec-search?name=Ted%20Cruz"
```

Returns: S2TX00312 (Senate), P60006111 (Presidential) with office, state, party, and election years from live OpenFEC.

End-to-end: typing "Ted Cruz" in the demo resolves candidate, pulls ~$174M career totals, signs, and verifies.

## Media pipeline (live)

```bash
# Step 1 — upload file, get hash
POST /v1/analyze-media

# Returns:
# fileHash: 4e5b10df0bc2faa503f911a4db7ae01730ab7b549af1d86003970ac1b001415b
# detection: { detector: "none", note: "set HIVE_API_KEY for live scores" }

# Step 2 — sign the analysis
POST /v1/sign-media-analysis

# Returns: full Ed25519-signed Frame receipt with schemaVersion, receiptId, claims, sources, signature, publicKey
```

## Cryptographic core (unit tests)

```
✓ packages/signing/__tests__/manchin.test.ts (5 tests)
Test Files  1 passed (1)
Tests  5 passed (5)
```

## Cache-Control (live headers)

```
GET https://frame-2yxu.onrender.com/demo
cache-control: no-cache, no-store, must-revalidate
```

## Git log (session commits)

| Commit | Summary |
|---|---|
| 37b535f | FEC name search + UI auto-resolve |
| ae13feb | Cache-Control on /demo |
| 71a2631 | Media analyze + sign-media-analysis script |
| fe13d1e | python-multipart for uploads |
| 6cf4d74 | CONTEXT.md media pipeline |
