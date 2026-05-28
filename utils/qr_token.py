from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import os
import struct
import time

_TTL_SECONDS = int(os.getenv("CAMPFLOW_QR_TOKEN_TTL_DAYS", os.getenv("QR_TOKEN_TTL_DAYS", "90"))) * 86400
_CACHE: bytes | None = None
_V2_PREFIX = b"CF2"


def _key() -> bytes:
    global _CACHE
    if _CACHE is None:
        secret = os.getenv("CAMPFLOW_SECRET_KEY", "campflow-dev-secret-change-me")
        _CACHE = hashlib.sha256(b"campflow-qr-v1:" + secret.encode()).digest()
    return _CACHE


def generate_qr_token(service_id: int, employee_id: int | None = None, ttl: int | None = None) -> str:
    """Return a signed URL-safe token embedding service, optional employee and timestamps."""
    issued_at = int(time.time())
    expires = issued_at + (ttl if ttl is not None else _TTL_SECONDS)
    payload = _V2_PREFIX + struct.pack(">IIII", int(service_id), int(employee_id or 0), issued_at, expires)
    sig = _hmac.new(_key(), payload, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(payload + sig).rstrip(b"=").decode()


def verify_qr_token(token: str) -> dict | None:
    """Verify token signature and expiry. Returns token metadata or None."""
    try:
        pad = 4 - len(token) % 4
        data = base64.urlsafe_b64decode(token + ("=" * pad if pad != 4 else ""))
        if data.startswith(_V2_PREFIX):
            if len(data) != 35:
                return None
            payload, sig = data[:19], data[19:]
            expected = _hmac.new(_key(), payload, hashlib.sha256).digest()[:16]
            if not _hmac.compare_digest(sig, expected):
                return None
            service_id, employee_id, issued_at, expires = struct.unpack(">IIII", payload[3:])
            if int(time.time()) > expires:
                return None
            return {
                "service_id": int(service_id),
                "employee_id": int(employee_id) if employee_id else None,
                "issued_at": int(issued_at),
                "expires_at": int(expires),
                "version": 2,
            }

        # Legacy V1 tokens only embed service_id and expiry.
        if len(data) != 24:
            return None
        payload, sig = data[:8], data[8:]
        expected = _hmac.new(_key(), payload, hashlib.sha256).digest()[:16]
        if not _hmac.compare_digest(sig, expected):
            return None
        service_id, expires = struct.unpack(">II", payload)
        if int(time.time()) > expires:
            return None
        return {"service_id": int(service_id), "employee_id": None, "issued_at": None, "expires_at": int(expires), "version": 1}
    except Exception:
        return None
