# Verifying a PUBLIC EYE receipt

Every investigation PUBLIC EYE produces is signed with Ed25519. Here's how to confirm a receipt is authentic — without trusting us.

---

## The short version

```bash
# Fetch the receipt
curl -s "https://frame-2yxu.onrender.com/r/8449d4ca-9b30-4ef5-90e5-a9ada6635e91" \
  | python3 -m json.tool | grep -E '"signed"|"signature"|"content_hash"|"public_key"'
```

If `signed` is `true`, the signature was valid at generation time. Use the steps below to verify it yourself right now.

---

## Full verification walkthrough

### Step 1: Fetch the receipt

```bash
RECEIPT_ID="8449d4ca-9b30-4ef5-90e5-a9ada6635e91"

curl -s "https://frame-2yxu.onrender.com/r/$RECEIPT_ID" > receipt.json
cat receipt.json | python3 -m json.tool | head -20
```

### Step 2: Use the API verifier

```bash
curl -sS -X POST "https://frame-2yxu.onrender.com/v1/verify-receipt" \
  -H "Content-Type: application/json" \
  -d @receipt.json \
  | python3 -m json.tool
```

Expected response:
```json
{
  "ok": true,
  "reasons": []
}
```

If `ok` is `false`, the `reasons` array says what failed.

### Step 3: Verify offline with Python (no trust required)

```python
import json, base64, hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

# Load the receipt
with open("receipt.json") as f:
    receipt = json.load(f)

# Extract signing fields
signature_b64 = receipt["signature"]
public_key_b64 = receipt["public_key"]
content_hash = receipt["content_hash"]

# Reconstruct the signing body (everything except signature, public_key, receipt_url)
signing_fields = {k: v for k, v in receipt.items()
                  if k not in ("signature", "public_key", "receipt_url")}

# Canonicalize (RFC 8785 JCS)
# pip install canonicaljson
import canonicaljson
canonical = canonicaljson.encode_canonical_json(signing_fields).decode()

# Compute hash
computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
assert computed_hash == content_hash, f"Hash mismatch: {computed_hash} != {content_hash}"

# Verify signature
pub_key_der = base64.b64decode(public_key_b64)
pub_key = Ed25519PublicKey.from_public_bytes(pub_key_der)  # or load_der_public_key

digest_msg = computed_hash.encode("utf-8")
sig_bytes = base64.b64decode(signature_b64)

pub_key.verify(sig_bytes, digest_msg)  # raises if invalid
print("✓ Signature valid. Receipt has not been altered.")
```

### Step 4: Verify with openssl

```bash
# Extract the public key
python3 -c "
import json, base64
r = json.load(open('receipt.json'))
open('pubkey.der', 'wb').write(base64.b64decode(r['public_key']))
"

# Convert DER to PEM
openssl pkey -inform DER -pubin -in pubkey.der -out pubkey.pem

# Get the content hash from the receipt
HASH=$(python3 -c "import json; print(json.load(open('receipt.json'))['content_hash'])")
echo -n "$HASH" > digest.txt

# Extract the signature
python3 -c "
import json, base64
r = json.load(open('receipt.json'))
open('sig.bin', 'wb').write(base64.b64decode(r['signature']))
"

# Verify
openssl pkeyutl -verify -pubin -inkey pubkey.pem \
  -sigfile sig.bin -in digest.txt -rawin

# Expected output: Signature Verified Successfully
```

---

## What the content hash covers

The hash covers everything in the receipt except three fields:

- `signature` — can't sign itself
- `public_key` — appended after signing
- `receipt_url` — assigned after storage, not part of the analysis

Everything else — the narrative, claims, sources, global perspectives, coalition data, timestamps — is included. If any of it changes, the hash changes, and the signature fails.

---

## Checking the public key

The same public key is used for all receipts. You can confirm it hasn't changed:

```bash
curl -s "https://frame-2yxu.onrender.com/v1/status" | python3 -m json.tool | grep public_key
```

Compare that to the `public_key` field in any receipt. They should match.

---

## What verification does not prove

- That the analysis is correct or complete
- That the sources cited actually say what the receipt claims
- That the article URL still resolves to the same content

Verification proves one thing: this receipt has not been altered since it was generated. The analysis quality is a separate question.
