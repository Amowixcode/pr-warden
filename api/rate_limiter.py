from __future__ import annotations

import time

from fastapi import HTTPException

from config.settings import settings

_call_timestamps: list[float] = []


def check_review_rate_limit() -> None:
    """Global in-memory rate limit on /review — a basic cost-abuse safety net.

    Per-process only (an in-memory list, not shared across workers/instances) — sufficient for
    a single-instance deployment; not a substitute for real distributed rate limiting at scale.
    """
    now = time.monotonic()
    cutoff = now - settings.review_rate_limit_window_seconds
    _call_timestamps[:] = [t for t in _call_timestamps if t > cutoff]
    if len(_call_timestamps) >= settings.review_rate_limit_max_calls:
        raise HTTPException(status_code=429, detail="rate limit exceeded — try again later")
    _call_timestamps.append(now)
