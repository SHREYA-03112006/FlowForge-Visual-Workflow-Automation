"""Outbound webhooks with HMAC-SHA256 signatures (helper for custom nodes / future use).

The receiver can verify authenticity with verify_signature():
    signature = HMAC_SHA256(secret, f"{timestamp}.{raw_body}")
sent as headers  X-Webhook-Timestamp  and  X-Webhook-Signature: sha256=<hex>.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from . import http_client

MAX_AGE_SECONDS = 300


def _body_bytes(payload: Any) -> bytes:
    # canonical JSON so sender and verifier agree on the exact bytes
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_payload(secret: str, body: bytes, timestamp: int | str) -> str:
    msg = f"{timestamp}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, timestamp: int | str, signature: str,
                     tolerance: int = MAX_AGE_SECONDS) -> bool:
    """Constant-time check; also rejects timestamps older/newer than `tolerance` seconds (replay protection)."""
    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            return False
    except (TypeError, ValueError):
        return False
    expected = sign_payload(secret, body, timestamp)
    return hmac.compare_digest(expected, (signature or "").removeprefix("sha256="))


def post_webhook(url: str, payload: Any, secret: str | None = None, headers: dict | None = None,
                 timeout: float = 10.0) -> dict:
    """POST `payload` as JSON (signed when `secret` is given). Returns the http_client response dict."""
    body = _body_bytes(payload)
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    if secret:
        ts = int(time.time())
        hdrs["X-Webhook-Timestamp"] = str(ts)
        hdrs["X-Webhook-Signature"] = "sha256=" + sign_payload(secret, body, ts)
    return http_client.request("POST", url, headers=hdrs, timeout=timeout, data=body)
