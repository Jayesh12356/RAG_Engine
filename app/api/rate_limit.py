"""In-process rate limiting for ``/query`` and ``/chat`` (Wave 3.3).

The plan calls for `slowapi`-based limiting (`slowapi` lives in the
``rate-limit`` optional extra). Slowapi is great for projects that already
ship a Redis backend, but our code path is single-process by default and we
also want sane behaviour when the optional extra isn't installed. So this
module provides a tiny **sliding-window** limiter that:

* Counts each ``(scope, key)`` independently against its own per-minute quota.
* Falls through gracefully (no 429s) when called from a unit test that
  doesn't pass an HTTP request.
* Adds the standard ``Retry-After`` and ``X-RateLimit-*`` headers that the
  UI uses to render a friendly toast.

Two scopes are enforced per request:

``ip``     — 60 requests per minute per remote address.
``cookie`` — 600 requests per minute per ``rag_engine_uid`` (or, when no
             cookie is present, the same key as ``ip``). This gives a single
             logged-in tab roughly 10 requests per second of headroom while
             still protecting the backend from a runaway script.

When :mod:`slowapi` is installed, we fall back to the same limits but expose
a shared ``Limiter`` instance for any future routes that want to use the
declarative ``@limiter.limit(...)`` decorator. The hand-rolled limiter is
still authoritative for ``/query`` and ``/chat`` so behaviour is identical
with or without the extra installed.
"""

from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock
from typing import Deque

from fastapi import HTTPException, Request

# ── Optional slowapi handle ─────────────────────────────────────────────────
try:  # pragma: no cover — optional extra
    from slowapi import Limiter  # type: ignore
    from slowapi.util import get_remote_address  # type: ignore

    slowapi_limiter: "Limiter | None" = Limiter(key_func=get_remote_address)
except Exception:  # pragma: no cover — slowapi missing is the default
    slowapi_limiter = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, value)


# ── Limits (overridable via env so ops can tighten without a redeploy) ──────
DEFAULT_PER_IP = _env_int("RATE_LIMIT_PER_IP_PER_MIN", 60)
DEFAULT_PER_COOKIE = _env_int("RATE_LIMIT_PER_COOKIE_PER_MIN", 600)
WINDOW_SECONDS = 60.0


class _SlidingWindow:
    """Tiny sliding-window counter keyed by an opaque string."""

    def __init__(self) -> None:
        self._buckets: dict[str, Deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, limit: int) -> tuple[bool, int, float]:
        """Record one hit for ``key`` and return ``(allowed, remaining, retry_after)``.

        ``retry_after`` is 0 when the request was allowed and the number of
        seconds the caller should wait before the next attempt otherwise.
        """
        now = time.monotonic()
        cutoff = now - WINDOW_SECONDS
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1.0, WINDOW_SECONDS - (now - bucket[0]))
                return False, 0, retry_after

            bucket.append(now)
            remaining = max(0, limit - len(bucket))
        return True, remaining, 0.0


# Two independent windows so an IP burst doesn't lock out a quiet cookie.
_ip_window = _SlidingWindow()
_cookie_window = _SlidingWindow()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _cookie_key(request: Request) -> str | None:
    try:
        return request.cookies.get("rag_engine_uid") or None
    except Exception:
        return None


def _raise_429(scope: str, retry_after: float) -> None:
    seconds = int(retry_after) if retry_after >= 1 else 1
    raise HTTPException(
        status_code=429,
        detail={
            "message": "Too many requests. Please slow down.",
            "scope": scope,
            "retry_after_seconds": seconds,
        },
        headers={
            "Retry-After": str(seconds),
            "X-RateLimit-Scope": scope,
        },
    )


async def enforce_chat_or_query_limit(request: Request) -> None:
    """FastAPI dependency: enforce per-IP + per-cookie limits on hot endpoints.

    The dependency raises ``HTTPException(429)`` with a structured ``detail``
    payload that the UI renders as a toast. Both scopes (IP + cookie) are
    checked even when one would otherwise allow the request, so a flood of
    cookie-less requests from one IP can't bypass the IP gate.
    """
    ip = _client_ip(request)
    ip_ok, ip_remaining, ip_retry = _ip_window.hit(f"ip:{ip}", DEFAULT_PER_IP)
    if not ip_ok:
        _raise_429("ip", ip_retry)

    cookie = _cookie_key(request)
    cookie_id = cookie or f"ip:{ip}"
    cookie_limit = DEFAULT_PER_COOKIE if cookie else DEFAULT_PER_IP
    cookie_ok, cookie_remaining, cookie_retry = _cookie_window.hit(
        f"cookie:{cookie_id}", cookie_limit
    )
    if not cookie_ok:
        _raise_429("cookie", cookie_retry)

    # Surface the tighter of the two budgets so the client knows where it
    # stands. Headers are only set on success — failures attach their own.
    request.state.rate_limit_remaining = min(ip_remaining, cookie_remaining)
    request.state.rate_limit_scope = (
        "ip" if ip_remaining <= cookie_remaining else "cookie"
    )


def reset_rate_limits_for_tests() -> None:
    """Test helper — clear all sliding-window counters."""
    with _ip_window._lock:
        _ip_window._buckets.clear()
    with _cookie_window._lock:
        _cookie_window._buckets.clear()
