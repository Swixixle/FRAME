# Signing reference

Every PUBLIC EYE receipt is signed with Ed25519. Here's the complete technical specification so you can verify independently.

---

## Algorithm

- **Signature:** Ed25519 (RFC 8032)
- **Canonicalization:** JCS — JSON Canonicalization Scheme (RFC 8785)
- **Hash:** SHA-256
- **Key encoding:** PKCS#8 DER, base64

---

## Signing process

```
receipt_payload (dict)
    → remove: signature, public_key, receipt_url
    → JCS canonicalize → UTF-8 bytes
    → SHA-256 → hex digest string
    → encode hex string as UTF-8 bytes
    → Ed25519 sign → base64 signature
```

Step by step:

**1. Build the signing body**
```python
signing_body = {k: v for k, v in receipt.items()
                if k not in ("signature", "public_key", "receipt_url")}
```

**2. Canonicalize with JCS**
```python
from apps.api.jcs_canonicalize import jcs_dumps
canonical = jcs_dumps(signing_body)  # deterministic UTF-8 string
```

JCS rules:
- Object keys sorted by UTF-16 code unit order
- No whitespace outside string values
- Numbers serialized without trailing zeros
- Unicode escapes only for control characters

**3. Hash**
```python
import hashlib
digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
# digest is a 64-character lowercase hex string
```

**4. Sign**
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64

sig_bytes = private_key.sign(digest.encode("utf-8"))
signature = base64.b64encode(sig_bytes).decode()
```

Note: we sign the **hex digest string**, not the raw hash bytes. This means the message passed to Ed25519 is the ASCII/UTF-8 representation of the SHA-256 hex digest.

---

## Verification process

```
receipt_payload (dict)
    → remove: signature, public_key, receipt_url
    → JCS canonicalize → UTF-8 bytes
    → SHA-256 → hex digest string
    → compare to stored content_hash
    → Ed25519 verify(signature, hex_digest_as_utf8_bytes, public_key)
```

**Python:**
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import base64, hashlib, json

def verify_receipt(receipt: dict) -> bool:
    sig_b64     = receipt.get("signature", "")
    pub_key_b64 = receipt.get("public_key", "")
    stored_hash = receipt.get("content_hash", "")

    # Reconstruct signing body
    body = {k: v for k, v in receipt.items()
            if k not in ("signature", "public_key", "receipt_url")}

    # Canonicalize and hash
    from jcs_canonicalize import jcs_dumps
    canonical = jcs_dumps(body)
    computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if computed_hash != stored_hash:
        return False  # payload was altered

    # Load public key
    pub_der = base64.b64decode(pub_key_b64)
    pub_key = serialization.load_der_public_key(pub_der)

    # Verify
    try:
        pub_key.verify(
            base64.b64decode(sig_b64),
            computed_hash.encode("utf-8")
        )
        return True
    except InvalidSignature:
        return False
```

---

## Receipt fields

| Field | Signed | Notes |
|-------|--------|-------|
| `receipt_id` | ✓ | UUID |
| `receipt_type` | ✓ | e.g. `article_analysis` |
| `signed` | ✓ | boolean |
| `generated_at` | ✓ | ISO 8601 timestamp |
| `narrative` | ✓ | main analysis text |
| `confirmed` | ✓ | cross-corroborated claims |
| `what_nobody_is_covering` | ✓ | coverage gaps |
| `global_perspectives` | ✓ | outlet cluster analysis |
| `schema_version` | ✓ | semantic version string |
| `signature` | ✗ | excluded from signing |
| `public_key` | ✗ | excluded from signing |
| `receipt_url` | ✗ | excluded from signing |

---

## Key management

The same keypair signs all receipts. The public key is:
- Embedded in every receipt as `public_key`
- Available at `GET /v1/status` as `public_key`
- Verifiable against any receipt independently

Key rotation is not yet implemented. When it is, receipts will carry a `key_id` field indicating which keypair signed them, and old public keys will remain published for historical verification.

---

## Schema versioning

Receipts carry a `schema_version` field (e.g. `"1.0.0"`). This is included in the signing body. When the receipt schema changes:

- **Patch (1.0.x):** metadata changes only, no structural change. Old and new receipts verify the same way.
- **Minor (1.x.0):** new fields added. Old verifiers can still verify old receipts. New fields are included in the hash.
- **Major (x.0.0):** breaking change to the signing structure. Requires a new verification code path. Old receipts remain verifiable using the archived major-version verifier.

Receipts without `schema_version` are pre-1.0 and are still accepted by the verifier with a warning.

---

## Pure Python JCS

`apps/api/jcs_canonicalize.py` is a self-contained RFC 8785 implementation with no dependencies. It includes a self-test suite against the RFC appendix B test vectors. Run it directly to verify:

```bash
python3 apps/api/jcs_canonicalize.py
# All tests passed.
```
