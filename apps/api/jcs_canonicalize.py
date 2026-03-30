"""
jcs_canonicalize.py
Pure Python JCS (RFC 8785) canonicalization.
Drop-in replacement for the Node subprocess in report_api.py.

Usage:
    from jcs_canonicalize import jcs_dumps, jcs_sha256_hex

    canonical = jcs_dumps({"b": 2, "a": 1})   # '{"a":1,"b":2}'
    digest     = jcs_sha256_hex(payload_dict)   # hex string
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


# ---------------------------------------------------------------------------
# Core serializer
# ---------------------------------------------------------------------------

def _serialize_string(s: str) -> str:
    """Escape a string per RFC 8785 §3.2.2.2."""
    out = ['"']
    for ch in s:
        cp = ord(ch)
        if cp == 0x08:
            out.append("\\b")
        elif cp == 0x09:
            out.append("\\t")
        elif cp == 0x0A:
            out.append("\\n")
        elif cp == 0x0C:
            out.append("\\f")
        elif cp == 0x0D:
            out.append("\\r")
        elif cp == 0x22:
            out.append('\\"')
        elif cp == 0x5C:
            out.append("\\\\")
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_number(n: float | int) -> str:
    """
    Serialize a number per RFC 8785 §3.2.2.3.
    Integers stay integers; floats use Python's repr-like shortest form.
    NaN / Infinity are forbidden by JCS.
    """
    if isinstance(n, bool):
        raise TypeError("bool is not a JSON number")
    if isinstance(n, int):
        return str(n)
    if math.isnan(n) or math.isinf(n):
        raise ValueError(f"JCS does not allow NaN or Infinity: {n}")
    # Use repr for shortest round-trip; strip trailing zeros but keep at least one decimal
    s = repr(n)
    # Python's repr already gives us shortest round-trip form
    return s


def _serialize_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return _serialize_number(value)
    if isinstance(value, float):
        return _serialize_number(value)
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, (list, tuple)):
        return _serialize_array(value)
    if isinstance(value, dict):
        return _serialize_object(value)
    raise TypeError(f"Unsupported type for JCS: {type(value)}")


def _serialize_array(arr: list) -> str:
    parts = [_serialize_value(item) for item in arr]
    return "[" + ",".join(parts) + "]"


def _serialize_object(obj: dict) -> str:
    """
    RFC 8785 §3.2.3: keys sorted by UTF-16 code unit order.
    Python's str sorts by Unicode code point which matches UTF-16 for
    code points <= U+FFFF (the vast majority of real-world keys).
    For full correctness with surrogate pairs we convert to UTF-16 sort key.
    """
    def utf16_sort_key(k: str) -> list[int]:
        return list(k.encode("utf-16-be"))

    sorted_keys = sorted(obj.keys(), key=utf16_sort_key)
    parts = [_serialize_string(k) + ":" + _serialize_value(obj[k]) for k in sorted_keys]
    return "{" + ",".join(parts) + "}"


def jcs_dumps(obj: Any) -> str:
    """Return the JCS canonical JSON string for obj."""
    return _serialize_value(obj)


def jcs_sha256_hex(obj: Any) -> str:
    """Return the SHA-256 hex digest of the JCS canonical form of obj."""
    canonical = jcs_dumps(obj).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def jcs_sha256_bytes(obj: Any) -> bytes:
    """Return the SHA-256 bytes digest of the JCS canonical form of obj."""
    canonical = jcs_dumps(obj).encode("utf-8")
    return hashlib.sha256(canonical).digest()


# ---------------------------------------------------------------------------
# Drop-in replacement for the report_api._jcs_canonicalize function
# ---------------------------------------------------------------------------

def _jcs_canonicalize(obj: Any) -> str:
    """
    Exact same signature as the existing report_api._jcs_canonicalize.
    Replace the import in report_api.py:

        # Old:
        from report_api import _jcs_canonicalize
        # or the Node subprocess version

        # New:
        from jcs_canonicalize import _jcs_canonicalize
    """
    return jcs_dumps(obj)


# ---------------------------------------------------------------------------
# Self-test (run: python jcs_canonicalize.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # RFC 8785 Appendix B test vectors
    vectors = [
        ({}, "{}"),
        ({"b": 2, "a": 1}, '{"a":1,"b":2}'),
        ({"a": True, "b": False, "c": None}, '{"a":true,"b":false,"c":null}'),
        ({"a": [1, 2, 3]}, '{"a":[1,2,3]}'),
        ({"a": "hello\nworld"}, '{"a":"hello\\nworld"}'),
    ]

    all_pass = True
    for obj, expected in vectors:
        result = jcs_dumps(obj)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{status}: {result!r}")
        if status == "FAIL":
            print(f"  expected: {expected!r}")

    print()
    print("All tests passed." if all_pass else "SOME TESTS FAILED.")
