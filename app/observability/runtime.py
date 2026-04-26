"""Runtime introspection helpers for the health endpoint (Wave 3.6).

Exposes lightweight, non-blocking signals so the status page can show
operational depth without scraping logs:

* :func:`process_uptime_seconds` — wall-clock seconds since the FastAPI
  process imported this module.
* :func:`db_pool_stats` — async engine connection pool snapshot.
* :func:`vector_index_size` — count of indexed points in the configured
  Qdrant collection (best-effort).
* :func:`ingestion_queue_depth` — number of in-flight ingest tasks.

Every helper is defensive: if the underlying subsystem is unavailable
(demo mode, network blip, optional dependency missing) it returns
``None`` so the health endpoint can degrade gracefully instead of 500ing.
"""
from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_PROCESS_START_MONOTONIC: float = time.monotonic()


def process_uptime_seconds() -> float:
    """Seconds since the application module first loaded."""
    return max(0.0, time.monotonic() - _PROCESS_START_MONOTONIC)


def db_pool_stats() -> dict[str, int | None] | None:
    """Return a snapshot of the SQLAlchemy async engine pool, if available."""
    try:
        from app.db.relational import get_engine
    except Exception as exc:
        logger.debug("runtime.db_pool.import_failed", error=str(exc))
        return None
    try:
        engine = get_engine()
    except Exception as exc:
        logger.debug("runtime.db_pool.engine_failed", error=str(exc))
        return None
    pool = getattr(engine, "pool", None)
    if pool is None:
        return None

    def _safe_int(method: str) -> int | None:
        fn = getattr(pool, method, None)
        if not callable(fn):
            return None
        try:
            return int(fn())
        except Exception:
            return None

    return {
        "size": _safe_int("size"),
        "checked_in": _safe_int("checkedin"),
        "checked_out": _safe_int("checkedout"),
        "overflow": _safe_int("overflow"),
    }


async def vector_index_size() -> int | None:
    """Return the configured Qdrant collection's ``points_count`` if reachable."""
    try:
        from app.config import get_settings
        from app.db.vector_store import get_vector_store
    except Exception as exc:
        logger.debug("runtime.vector_index.import_failed", error=str(exc))
        return None

    try:
        settings = get_settings()
        store: Any = get_vector_store()
    except Exception as exc:
        logger.debug("runtime.vector_index.store_failed", error=str(exc))
        return None

    collection = settings.vector_collection

    # Try a few common interfaces in order — keeps us decoupled from any
    # particular vector backend wrapper. Each branch tolerates missing
    # methods so demo / in-memory stores simply return None.
    count_fn = getattr(store, "count", None)
    if callable(count_fn):
        try:
            value = count_fn(collection)
            if hasattr(value, "__await__"):
                value = await value  # type: ignore[func-returns-value]
            return int(value) if value is not None else None
        except Exception as exc:
            logger.debug("runtime.vector_index.count_failed", error=str(exc))

    info_fn = getattr(store, "collection_info", None)
    if callable(info_fn):
        try:
            info = info_fn(collection)
            if hasattr(info, "__await__"):
                info = await info  # type: ignore[func-returns-value]
            if isinstance(info, dict):
                points = info.get("points_count") or info.get("points")
                if points is not None:
                    return int(points)
        except Exception as exc:
            logger.debug("runtime.vector_index.info_failed", error=str(exc))

    client = getattr(store, "client", None)
    if client is not None:
        try:
            info = client.get_collection(collection)
            # AsyncQdrantClient returns a coroutine; the sync client returns the
            # CollectionInfo directly. Handle both so we never leak a coroutine.
            if hasattr(info, "__await__"):
                info = await info  # type: ignore[func-returns-value]
            points = getattr(info, "points_count", None)
            if points is None and isinstance(info, dict):
                points = info.get("points_count") or info.get("points")
            if points is not None:
                return int(points)
        except Exception as exc:
            logger.debug("runtime.vector_index.client_failed", error=str(exc))

    return None


async def ingestion_queue_depth() -> int | None:
    """Return the number of currently in-flight ingestion tasks."""
    try:
        from sqlalchemy import select

        from app.db.relational import IngestionTaskModel, get_session_maker
    except Exception as exc:
        logger.debug("runtime.queue.import_failed", error=str(exc))
        return None

    try:
        session_maker = get_session_maker()
    except Exception as exc:
        logger.debug("runtime.queue.session_failed", error=str(exc))
        return None

    try:
        async with session_maker() as session:
            stmt = select(IngestionTaskModel.id).where(
                IngestionTaskModel.status.in_(("queued", "running"))
            )
            result = await session.execute(stmt)
            return len(list(result.scalars().all()))
    except Exception as exc:
        logger.debug("runtime.queue.query_failed", error=str(exc))
        return None
