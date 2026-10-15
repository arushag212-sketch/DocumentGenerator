"""In-memory rate limiting and account lockout tracking."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import HTTPException, Request, status

# In-memory sliding window rate limiter: key -> list of timestamps
_rate_limits: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """Enforce a sliding window rate limit for a key (IP or email)."""
    now = time.time()
    timestamps = _rate_limits[key]

    # Purge timestamps older than the window
    cutoff = now - window_seconds
    _rate_limits[key] = [t for t in timestamps if t > cutoff]

    if len(_rate_limits[key]) >= max_requests:
        retry_after = int(window_seconds - (now - _rate_limits[key][0])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Too many requests. Please wait {retry_after} seconds before retrying.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    _rate_limits[key].append(now)


def clear_rate_limits() -> None:
    """Clear all rate limit entries (useful for test resets)."""
    _rate_limits.clear()
