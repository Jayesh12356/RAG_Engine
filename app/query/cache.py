"""Answer cache for the single-shot Q&A pipeline.

The cache memoises the final ``QueryResponse`` for a deterministic
``(question, top_k, service_category)`` tuple at the *current corpus
version*. Whenever a document is added or deleted the corpus version is
bumped and every prior key becomes stale (the lookup function rebuilds
the key with the new version, so the old entry simply ages out of the
LRU). This keeps invalidation O(1) without scanning entries.

The default backend is a process-local thread-safe LRU
(``MemoryAnswerCache``). Setting ``ANSWER_CACHE_BACKEND=redis`` swaps in
``RedisAnswerCache`` which serialises responses as JSON. The Redis
adapter is opt-in: it imports ``redis.asyncio`` lazily so deployments
without Redis avoid the dependency.

The cache only stores *non-refused* responses. Refusals are usually a
function of evidence gating that may flip back as the corpus grows, so
caching them would mask future improvements.
"""
from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, Protocol

import structlog

from app.config import get_settings
from app.models.query import QueryResponse

logger = structlog.get_logger(__name__)


# ── Corpus version singleton ──────────────────────────────────────────────


class _CorpusVersion:
    """Thread-safe monotonic counter that invalidates the answer cache.

    Bumped from the ingestion pipeline (after a successful upsert) and
    the document-delete route. The counter is process-local; in a
    multi-worker deployment with Redis caching the version key should
    move to Redis (``corpus_version`` key) and the bump path should
    ``INCR`` it. Workers without Redis still get correct *single
    process* behaviour.
    """

    def __init__(self) -> None:
        self._value = 1
        self._lock = threading.Lock()

    def value(self) -> int:
        with self._lock:
            return self._value

    def bump(self, *, reason: str = "") -> int:
        with self._lock:
            self._value += 1
            v = self._value
        logger.info("corpus_version_bumped", value=v, reason=reason or "n/a")
        return v


_corpus_version = _CorpusVersion()


def get_corpus_version() -> int:
    """Return the current corpus version (1-indexed)."""
    return _corpus_version.value()


def bump_corpus_version(reason: str = "") -> int:
    """Increment the corpus version. Call after successful ingest/delete."""
    return _corpus_version.bump(reason=reason)


def _reset_corpus_version_for_tests() -> None:
    """Reset the corpus version to 1. Tests only — do not call in prod."""
    _corpus_version._value = 1  # noqa: SLF001 — test helper


# ── Key helper ────────────────────────────────────────────────────────────


def make_cache_key(
    *,
    question: str,
    top_k: int,
    service_category: str | None,
    rerank_top_n: int | None = None,
    include_citations: bool | None = None,
) -> str:
    """Hash all inputs that influence the answer into a stable cache key.

    The ``corpus_version`` is folded in implicitly: keys built before a
    bump no longer match keys built after, so old entries are dead on
    arrival without explicit eviction.
    """
    payload = "|".join(
        [
            (question or "").strip().lower(),
            str(int(top_k or 0)),
            (service_category or "GENERAL").upper(),
            "rt=" + (str(int(rerank_top_n)) if rerank_top_n is not None else "auto"),
            "ic=" + ("1" if include_citations else "0" if include_citations is False else "auto"),
            "cv=" + str(get_corpus_version()),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Backends ──────────────────────────────────────────────────────────────


class AnswerCacheBackend(Protocol):
    """Minimal cache interface the pipelines depend on."""

    async def get(self, key: str) -> QueryResponse | None: ...
    async def set(self, key: str, response: QueryResponse, ttl: int | None = None) -> None: ...
    async def clear(self) -> None: ...


class MemoryAnswerCache:
    """LRU cache with TTL. Thread-safe enough for the asyncio event loop."""

    def __init__(self, maxsize: int = 256, ttl_sec: int = 600) -> None:
        self.maxsize = max(1, int(maxsize))
        self.ttl_sec = max(1, int(ttl_sec))
        self._store: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> QueryResponse | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            expires_at, payload = entry
            if expires_at < time.time():
                self._store.pop(key, None)
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
        try:
            return QueryResponse(**payload)
        except Exception as exc:
            logger.warning("answer_cache.deserialise_failed", error=str(exc))
            return None

    async def set(self, key: str, response: QueryResponse, ttl: int | None = None) -> None:
        ttl_eff = int(ttl if ttl is not None else self.ttl_sec)
        expires_at = time.time() + ttl_eff
        try:
            payload = response.model_dump()
        except Exception as exc:
            logger.warning("answer_cache.serialise_failed", error=str(exc))
            return
        with self._lock:
            self._store[key] = (expires_at, payload)
            self._store.move_to_end(key)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)

    async def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._store),
                "maxsize": self.maxsize,
                "hits": self.hits,
                "misses": self.misses,
            }


class RedisAnswerCache:
    """Redis-backed cache. Lazy-imported so it stays optional."""

    def __init__(self, url: str, ttl_sec: int = 600, prefix: str = "rag:answer:") -> None:
        self.url = url
        self.ttl_sec = max(1, int(ttl_sec))
        self.prefix = prefix
        self._client: Any | None = None
        self._lock = asyncio.Lock()

    async def _conn(self) -> Any:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is not None:
                return self._client
            try:
                import redis.asyncio as aioredis  # type: ignore[import-not-found]
            except Exception as exc:  # pragma: no cover — exercised only when redis is not installed
                logger.warning("answer_cache.redis_import_failed", error=str(exc))
                raise
            self._client = aioredis.from_url(self.url, decode_responses=True)
            return self._client

    async def get(self, key: str) -> QueryResponse | None:
        try:
            client = await self._conn()
            raw = await client.get(self.prefix + key)
        except Exception as exc:
            logger.warning("answer_cache.redis_get_failed", error=str(exc))
            return None
        if not raw:
            return None
        try:
            import json

            return QueryResponse(**json.loads(raw))
        except Exception as exc:
            logger.warning("answer_cache.redis_deserialise_failed", error=str(exc))
            return None

    async def set(self, key: str, response: QueryResponse, ttl: int | None = None) -> None:
        try:
            client = await self._conn()
            import json

            await client.set(
                self.prefix + key,
                json.dumps(response.model_dump()),
                ex=int(ttl if ttl is not None else self.ttl_sec),
            )
        except Exception as exc:
            logger.warning("answer_cache.redis_set_failed", error=str(exc))

    async def clear(self) -> None:
        try:
            client = await self._conn()
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor=cursor, match=self.prefix + "*", count=200)
                if keys:
                    await client.delete(*keys)
                if not cursor:
                    break
        except Exception as exc:
            logger.warning("answer_cache.redis_clear_failed", error=str(exc))


# ── Module-level cache resolver ───────────────────────────────────────────


_cache_singleton: AnswerCacheBackend | None = None
_singleton_lock = threading.Lock()


def get_answer_cache() -> AnswerCacheBackend | None:
    """Return the active cache backend, or ``None`` when caching is off."""
    global _cache_singleton
    settings = get_settings()
    if not settings.ANSWER_CACHE_ENABLED:
        return None
    if _cache_singleton is not None:
        return _cache_singleton
    with _singleton_lock:
        if _cache_singleton is not None:
            return _cache_singleton
        backend = (settings.ANSWER_CACHE_BACKEND or "memory").lower()
        if backend == "redis":
            try:
                _cache_singleton = RedisAnswerCache(
                    url=settings.REDIS_URL,
                    ttl_sec=settings.ANSWER_CACHE_TTL_SEC,
                )
            except Exception as exc:
                logger.warning("answer_cache.redis_init_failed", error=str(exc))
                _cache_singleton = MemoryAnswerCache(
                    maxsize=settings.ANSWER_CACHE_MAXSIZE,
                    ttl_sec=settings.ANSWER_CACHE_TTL_SEC,
                )
        else:
            _cache_singleton = MemoryAnswerCache(
                maxsize=settings.ANSWER_CACHE_MAXSIZE,
                ttl_sec=settings.ANSWER_CACHE_TTL_SEC,
            )
        return _cache_singleton


def _reset_cache_singleton_for_tests() -> None:
    """Reset the module singleton. Tests only."""
    global _cache_singleton
    _cache_singleton = None


__all__ = [
    "AnswerCacheBackend",
    "MemoryAnswerCache",
    "RedisAnswerCache",
    "bump_corpus_version",
    "get_answer_cache",
    "get_corpus_version",
    "make_cache_key",
]
