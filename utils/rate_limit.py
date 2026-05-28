from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def is_rate_limited(key: str, max_requests: int, window_seconds: int) -> bool:
    """Return True if key exceeded max_requests within window_seconds (sliding window)."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        valid = [t for t in _buckets[key] if t > cutoff]
        if len(valid) >= max_requests:
            _buckets[key] = valid
            return True
        valid.append(now)
        _buckets[key] = valid
        return False
