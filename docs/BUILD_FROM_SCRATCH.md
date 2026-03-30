# Building PUBLIC EYE from scratch

This is a practical guide. It assumes you have a machine, a terminal, and the env vars. It does not assume you have context on why things are the way they are.

---

## What you're building

A FastAPI backend that:
- Accepts article URLs and analyzes them
- Generates signed receipts stored in Postgres
- Builds coalition maps of how global outlets frame the same story
- Serves server-rendered investigation pages
- Exposes a public verifier

A Vite/React frontend that (currently) shows recent investigations and handles the analyze flow.

---

## Prerequisites

- Node.js ≥ 20
- Python 3.11+
- PostgreSQL (local or hosted)
- Redis (optional — only needed for background enrichment)
- Git

---

## Step 1: Clone and install

```bash
git clone https://github.com/Swixixle/PUBLIC-EYE.git
cd PUBLIC-EYE

# Install Node dependencies and compile TypeScript packages
npm ci
npm run build

# Install Python dependencies
pip install -r apps/api/requirements.txt
```

`npm run build` compiles the TypeScript packages (`packages/types`, `packages/sources`, `packages/signing`) into `dist/` directories. The API depends on these compiled outputs for signing. Don't skip this.

---

## Step 2: Generate keys

If you're setting up fresh, you need an Ed25519 keypair:

```bash
# Generate a private key (PKCS#8 DER, base64 encoded)
python3 - <<'EOF'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64

key = Ed25519PrivateKey.generate()

priv = key.private_bytes(
    serialization.Encoding.DER,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()
)
pub = key.public_key().public_bytes(
    serialization.Encoding.DER,
    serialization.PublicFormat.SubjectPublicKeyInfo
)

print("FRAME_PRIVATE_KEY=" + base64.b64encode(priv).decode())
print("FRAME_PUBLIC_KEY="  + base64.b64encode(pub).decode())
EOF
```

Save both values. You cannot recover the private key later.

---

## Step 3: Configure environment

```bash
cp apps/api/.env.example apps/api/.env
```

Edit `apps/api/.env`:

```bash
# Signing (required)
FRAME_PRIVATE_KEY=<base64 private key from above>
FRAME_PUBLIC_KEY=<base64 public key from above>
FRAME_KEY_FORMAT=base64

# Database (required)
DATABASE_URL=postgresql://user:password@localhost:5432/publiceye

# LLM (required for analysis)
ANTHROPIC_API_KEY=sk-ant-...

# Optional LLM fallbacks
GROQ_API_KEY=gsk_...
LLM_PROVIDER=auto

# Optional data sources
FEC_API_KEY=
CONGRESS_API_KEY=
COURTLISTENER_API_KEY=
ASSEMBLYAI_API_KEY=
SEC_EDGAR_USER_AGENT=your-name@email.com
```

---

## Step 4: Set up the database

Create the database:

```bash
createdb publiceye
```

Tables are created automatically on startup. The API calls `ensure_table()` and `ensure_coalition_maps_table()` when it starts. If you want to run migrations manually:

```bash
psql $DATABASE_URL < apps/api/db/migrations/001_receipts.sql
psql $DATABASE_URL < apps/api/db/migrations/004_coalition_maps.sql
```

---

## Step 5: Start the API

```bash
cd apps/api
uvicorn main:app --reload --port 8000
```

You should see `Application startup complete.` in the logs. If you see an `ImportError`, something in step 1 or 2 is missing. Check `grep -n "^from\|^import" main.py | head -30` for the first bad import.

Health check:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/v1/status
```

`/v1/status` should show `ANTHROPIC_API_KEY: "set"` and `FRAME_PRIVATE_KEY: "set"`.

---

## Step 6: Run your first analysis

```bash
curl -sS -X POST http://localhost:8000/v1/analyze-article \
  -H "Content-Type: application/json" \
  -d '{"url":"https://apnews.com/article/cuba-trump-russia-oil-shipment-b6845987728e28d5d762992840ca6b69"}' \
  | python3 -m json.tool | head -20
```

This takes 60–120 seconds the first time. You get back a `report_id` / `receipt_id`.

Then fetch the investigation page:
```bash
open http://localhost:8000/i/<receipt_id>
```

---

## Step 7: Trigger coalition map

The coalition map runs async after the main analysis:

```bash
curl -sS -X POST http://localhost:8000/v1/coalition-map \
  -H "Content-Type: application/json" \
  -d '{"receipt_id":"<your-receipt-id>"}'

# Wait ~30 seconds then poll:
curl http://localhost:8000/v1/coalition-map/<receipt_id> | python3 -m json.tool
```

---

## Step 8: Start the frontend (optional)

```bash
cd apps/web
npm run dev
```

Frontend at `http://localhost:5173`. Set `VITE_API_BASE` in `apps/web/.env` if your API is not at the default port.

---

## Deploying to Render

1. Fork or push to your GitHub
2. Create a new Web Service on Render, connect the repo
3. Root directory: `apps/api`
4. Build command: `cd /opt/render/project/src && npm ci && npm run build && pip install -r apps/api/requirements.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add all env vars from Step 3 in Render → Environment
7. Add `DATABASE_URL` pointing at a Render Postgres instance

The `render.yaml` in the repo root automates most of this.

---

## Common problems

**`ImportError` on startup**  
Something is imported in `main.py` that doesn't exist. Read the traceback carefully — it'll name the exact file and function. Either the file is missing, or a function was renamed. Fix the import and redeploy.

**`Application startup complete` but routes return 404**  
The route might not be registered. Check `curl http://localhost:8000/openapi.json | python3 -m json.tool | grep "/your-route"`.

**Coalition map returns "Receipt has no global perspectives"**  
The receipt was generated before global perspectives were added to the `analyze-article` pipeline. Generate a new receipt. Old receipts without `global_perspectives` cannot get coalition maps.

**Verify receipt returns `ok: false`**  
One of two things: (a) the receipt was signed with the old Node JCS subprocess and the Python JCS produces a different hash for edge-case float values — this affects only pre-migration receipts; (b) the `public_key` or `signature` fields have different names than the verifier expects. Check the actual field names with `curl /r/{id} | python3 -c "import sys,json; print(list(json.load(sys.stdin).keys()))"`.

**Font looks stretched on the investigation page**  
CSS `font-family` has unescaped quotes inside a Python f-string. Fix: use `font-family:Syne,sans-serif` not `font-family:"Syne",sans-serif` inside the Python string.

---

## Architecture notes

**Why one big `main.py`?**  
It grew that way. It works. The plan is to extract heavy routes into separate routers as the codebase matures. For now, `grep "@app\." main.py` is how you find anything.

**Why server-rendered investigation pages instead of React?**  
The investigation page needs to be a permanent document — shareable, archivable, renderable without a JS runtime. Server-rendered HTML from Python is simpler, faster, and more durable for that use case.

**Why JCS?**  
RFC 8785 produces a deterministic canonical form of any JSON object regardless of key order or serializer. This means the same payload produces the same hash on any machine, which is necessary for signatures to be verifiable by third parties. Without canonicalization, whitespace and key order differences would break verification.

**Why Ed25519?**  
Fast, small keys, no padding oracle attacks, well-supported in Python's `cryptography` library and in browsers via WebCrypto. The public key is embedded in every receipt so anyone can verify without contacting us.
