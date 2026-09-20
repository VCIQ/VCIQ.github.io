"""Optional transport receipt guard; no writes, retries, or private state."""
from __future__ import annotations
import hashlib
import hmac
import os
import re

TOKEN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def validate_correlation(token: str, digest: str, operation: str, policy: str, batch: str) -> bool:
    if token == "" and digest == "":
        return False  # Legacy caller: original validation/write path is unchanged.
    if not TOKEN.fullmatch(token) or not DIGEST.fullmatch(digest):
        raise ValueError("dispatch_correlation_invalid")
    if operation != "apply" or policy not in ("strict", "skip") or len(batch.encode("utf-8")) > 45_000:
        raise ValueError("dispatch_correlation_invalid")
    expected = hashlib.sha256(f"v1\n{policy}\n{batch}".encode("utf-8")).hexdigest()
    if not hmac.compare_digest(expected, digest):
        raise ValueError("dispatch_correlation_mismatch")
    return True


if __name__ == "__main__":
    try:
        present = validate_correlation(*(os.environ.get(key, "") for key in (
            "DISPATCH_TOKEN", "DISPATCH_DIGEST", "OPERATION", "INVALID_POLICY", "BATCH_JSON"
        )))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print("Durable dispatch correlation v1 verified" if present else "Legacy request without transport correlation")
