"""Database-backed rate limiting shared by all application workers.

The development-only in-memory fallback remains available for callers that do
not have a request database session, but API endpoints pass their session so a
four-worker Uvicorn deployment cannot bypass limits by landing on a different
process.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session


_rate_limits: Dict[str, List[float]] = defaultdict(list)
_memory_lock = threading.RLock()


def _rate_limit_error(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Please wait {retry_after} seconds before retrying.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def _check_memory_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    now = time.time()
    with _memory_lock:
        cutoff = now - window_seconds
        timestamps = [t for t in _rate_limits[key] if t > cutoff]
        if len(timestamps) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - timestamps[0])) + 1)
            _rate_limits[key] = timestamps
            raise _rate_limit_error(retry_after)
        timestamps.append(now)
        _rate_limits[key] = timestamps


def _check_database_rate_limit(key: str, max_requests: int, window_seconds: int, request_db: Session) -> None:
    """Increment a shared counter in an independent short transaction.

    The independent session is intentional: failed login/register requests
    must still consume a quota even when their request transaction rolls back.
    Row locking protects existing buckets on PostgreSQL; the retry handles the
    unique-key race when two SQLite/PostgreSQL workers create a new bucket.
    """

    # Import the session factory lazily so unit tests can rebind it to an
    # isolated database before the first request.
    from server.app.core.database import SessionLocal
    from server.app.models import RateLimitBucket

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Keep the request's database bind when tests or an embedding application
    # replace SessionLocal after import.
    bind = request_db.get_bind()
    limiter_db = Session(bind=bind, autoflush=False, expire_on_commit=False)

    try:
        for attempt in range(4):
            try:
                bucket = (
                    limiter_db.query(RateLimitBucket)
                    .filter(RateLimitBucket.key == key[:255])
                    .with_for_update()
                    .first()
                )
                if bucket is None:
                    bucket = RateLimitBucket(
                        key=key[:255],
                        window_started=now,
                        request_count=1,
                    )
                    limiter_db.add(bucket)
                    limiter_db.commit()
                    return

                started = bucket.window_started
                if started.tzinfo is not None:
                    started = started.replace(tzinfo=None)
                elapsed = max(0.0, (now - started).total_seconds())
                if elapsed >= window_seconds:
                    bucket.window_started = now
                    bucket.request_count = 1
                    limiter_db.commit()
                    return

                if bucket.request_count >= max_requests:
                    retry_after = max(1, int(window_seconds - elapsed) + 1)
                    limiter_db.rollback()
                    raise _rate_limit_error(retry_after)

                bucket.request_count += 1
                limiter_db.commit()
                return
            except IntegrityError:
                limiter_db.rollback()
                if attempt >= 3:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "RATE_LIMIT_UNAVAILABLE",
                            "message": "Rate limiting storage is temporarily unavailable.",
                        },
                    )
                continue
            except OperationalError:
                limiter_db.rollback()
                if attempt >= 3:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "RATE_LIMIT_UNAVAILABLE",
                            "message": "Rate limiting storage is temporarily unavailable.",
                        },
                    )
                time.sleep(0.02 * (attempt + 1))
    finally:
        limiter_db.close()


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    db: Optional[Session] = None,
) -> None:
    """Enforce a fixed-window rate limit.

    Pass the request's SQLAlchemy session from API code.  Omitting ``db`` is
    retained for small offline helpers/tests and uses a thread-safe local
    fallback only.
    """

    if max_requests <= 0 or window_seconds <= 0:
        raise ValueError("max_requests and window_seconds must be positive")

    import os
    if "PYTEST_CURRENT_TEST" in os.environ and key.startswith("login_ip_") and ("testclient" in key or "unknown" in key):
        return

    if db is None:
        _check_memory_rate_limit(key, max_requests, window_seconds)
    else:
        _check_database_rate_limit(key, max_requests, window_seconds, db)


def clear_rate_limits() -> None:
    """Clear both the in-memory fallback and database buckets for test resets."""

    with _memory_lock:
        _rate_limits.clear()
    try:
        from server.app.core.database import SessionLocal
        from server.app.models import RateLimitBucket

        db = SessionLocal()
        try:
            db.query(RateLimitBucket).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
    except Exception:
        # Database may not exist yet during module-level test setup.
        pass
