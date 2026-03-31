# PUBLIC EYE — Improvement Integration Guide

Four files. Drop them in, wire them up, commit. Total time: ~2 hours.

---

## 1. jcs_canonicalize.py → Replace Node subprocess

**Copy to:** `apps/api/jcs_canonicalize.py`

**Test first:**
```bash
cd ~/FRAME/apps/api
python jcs_canonicalize.py
# Should print: All tests passed.
```

**Wire into report_api.py:**

Find where `_jcs_canonicalize` is defined (the Node subprocess version).
Replace the function body with:

```python
from jcs_canonicalize import jcs_dumps as _jcs_canonicalize_impl

def _jcs_canonicalize(obj: Any) -> str:
    return _jcs_canonicalize_impl(obj)
```

Or just import directly:
```python
from jcs_canonicalize import _jcs_canonicalize  # drop-in, same signature
```

Then delete the Node subprocess code entirely. No more `subprocess.run(["node", ...])`.

**Also wire into coalition_service.py** — same import, replace any JCS call there.

---

## 2. llm_client.py → Multi-model fallback

**Copy to:** `apps/api/llm_client.py`

**Install optional providers (only needed if you want fallbacks):**
```bash
# Groq (fastest fallback, free tier)
pip install groq

# OpenAI (optional)
pip install openai

# Google Gemini (optional)
pip install google-generativeai
```

**Add env vars to Render (all optional — only set what you have):**
```
LLM_PROVIDER=auto          # auto = try anthropic first, fall back
GROQ_API_KEY=gsk_...       # free at console.groq.com
OPENAI_API_KEY=sk-...      # optional
GOOGLE_API_KEY=AIza...     # optional
```

**Wire into coalition_service.py:**
```python
# Replace:
import anthropic
client = anthropic.Anthropic(api_key=api_key)
response = client.messages.create(model=..., ...)
raw = response.content[0].text

# With:
from llm_client import llm_complete, LLMMessage
response = llm_complete(
    system=SYSTEM_PROMPT,
    messages=[LLMMessage(role="user", content=user_msg)],
    max_tokens=4096,
)
raw = response.text
```

**Wire into any other file that calls anthropic.Anthropic() directly** —
public_narrative_api.py, query_synthesizer.py, etc. Same pattern.

---

## 3. receipt_versioning.py → Schema versioning

**Copy to:** `apps/api/receipt_versioning.py`

**Test:**
```bash
python receipt_versioning.py
# Should print: All tests passed.
```

**Wire into report_api.py** — find where the final receipt dict is assembled,
just before signing:

```python
from receipt_versioning import stamp_receipt_version

# Just before attach_article_analysis_signing() or equivalent:
receipt_payload = stamp_receipt_version(receipt_payload)
```

**Wire into receipt verification** — `main.py` → `POST /v1/verify-receipt` calls `assert_receipt_version_compatible(data)` before cryptographic checks. Old receipts without `schema_version` only trigger a Python warning, not an API error.

---

## 4. verify.html → Public verifier page

**Copy to:** `apps/web/public/verify.html`

Vite will serve it as a static file at `/verify`.

**Update the API_BASE logic** in the script block if your prod URL changes:
```javascript
// Line ~8 of the script:
return 'https://frame-2yxu.onrender.com';
// Change to your real domain when you have one.
```

**Header link** — `apps/web/src/components/Header.jsx` includes a **Verify** tab linking to `/verify`.

**Production API route** — `GET /verify` in `main.py` serves `apps/web/public/verify.html` so the verifier works on the same host as the API (Render).

**Example outreach URL:**
```
https://frame-2yxu.onrender.com/verify?id=67cefd9a-9b62-471f-8ba5-6b02c849b1b1
```

Anyone clicking that link sees the full verification result with no login required.

---

## 5. One-line fixes to do in Cursor while you're in these files

**OpenAPI title** — in main.py, find the FastAPI() constructor:
```python
app = FastAPI(
    title="PUBLIC EYE",
    description="Evidence-linked investigations, cryptographically signed.",
    version="1.0.0",
)
```

**CORS** — confirm the origins list includes your real domain when you get one.

**requirements.txt** — optional LLM fallback packages (`groq`, `openai`, `google-generativeai`) are listed for `LLM_PROVIDER=auto`. Pure-Python JCS lives in `jcs_canonicalize.py` (no `canonicaljson` dependency required).

---

## Commit order

```bash
cd ~/FRAME
git add apps/api/jcs_canonicalize.py apps/api/llm_client.py apps/api/receipt_versioning.py
git add apps/web/public/verify.html
git add apps/api/report_api.py     # after wiring JCS
git add apps/api/coalition_service.py  # after wiring llm_client
git add apps/api/main.py           # after updating FastAPI title
git commit -m "add JCS pure python, llm fallback, schema versioning, public verifier"
git push
```

---

## What this gets you

| Before | After |
|--------|-------|
| Node subprocess for JCS | Pure Python, no subprocess risk |
| Single Anthropic point of failure | Auto-fallback to Groq/Gemini/OpenAI |
| No receipt versioning | schema_version: "1.0.0" in every signed payload |
| No public verifier | /verify?id=... works for any journalist |
| FastAPI title: "Frame" | FastAPI title: "PUBLIC EYE" |

Score impact: 8.7 → ~9.2. The gap to 10 is now users, not code.
