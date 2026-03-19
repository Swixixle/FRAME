# Frame

Transparency receipts for political claims: **signed**, **source-linked** narrative using **JCS (RFC 8785)** — not `JSON.stringify`.

## Quickstart

```bash
npm install
npm test
npm run build
npm run generate-keys
```

### Python API

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Requires **Node** on `PATH` so JCS matches TypeScript (`scripts/jcs-stringify.mjs`).

### Web demo

Open `apps/web/index.html` in a browser (or serve the folder). Optional query: `?api=http://127.0.0.1:8000`.

## Monorepo packages

| Package            | Role                                       |
| ------------------ | ------------------------------------------ |
| `@frame/types`     | Shared TypeScript types                    |
| `@frame/signing`   | Ed25519 + `canonicalize` hashing           |
| `@frame/narrative` | Banned words, domain whitelist, validation |
| `@frame/entity`    | Disambiguation + confidence floor          |
| `@frame/sources`   | External data adapters                     |

## Rules

See `.github/copilot-instructions.md`.
