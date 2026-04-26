"""FastAPI middleware for per-cookie ``Settings`` overrides (Wave 2.8).

The middleware reads the ``rag_engine_uid`` cookie, fetches the user's
``user_preferences.settings`` blob, and pushes it into the
:mod:`app.config` ``ContextVar`` for the duration of the request.  Hot-path
callers that pull ``get_settings()`` after this point see the overlay
applied.

The preference lookup is best-effort: a database hiccup or a missing row
must never prevent a request from being served. Likewise, anonymous
visitors without a cookie just see the global defaults.
"""

from __future__ import annotations

from typing import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import reset_settings_overrides, set_settings_overrides

logger = structlog.get_logger(__name__)


class UserPreferenceOverrideMiddleware(BaseHTTPMiddleware):
    """Apply per-cookie config overrides to the request scope."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        token = None
        try:
            uid = request.cookies.get("rag_engine_uid")
        except Exception:  # ``request.cookies`` parses the header — be defensive.
            uid = None

        if uid:
            try:
                # Lazy import: avoid circulars and skip the DB roundtrip
                # entirely for environments without a relational store.
                from app.db.relational import get_user_preferences

                prefs = await get_user_preferences(uid)
                overrides = prefs.get("settings") or {}
                if overrides:
                    token = set_settings_overrides(overrides)
            except Exception as exc:  # pragma: no cover — middleware must never fail open.
                logger.debug("preferences.middleware_error", error=str(exc))

        try:
            return await call_next(request)
        finally:
            if token is not None:
                reset_settings_overrides(token)
