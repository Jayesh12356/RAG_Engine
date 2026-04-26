"""Unit tests for the answer cache and corpus-version invalidation."""
from __future__ import annotations

import asyncio

import pytest

from app.config import get_settings
from app.models.query import QueryResponse
from app.query import cache as cache_mod


@pytest.fixture(autouse=True)
def _reset_cache_state():
    cache_mod._reset_corpus_version_for_tests()
    cache_mod._reset_cache_singleton_for_tests()
    settings = get_settings()
    prev = (
        settings.ANSWER_CACHE_ENABLED,
        settings.ANSWER_CACHE_BACKEND,
        settings.ANSWER_CACHE_MAXSIZE,
        settings.ANSWER_CACHE_TTL_SEC,
    )
    settings.ANSWER_CACHE_ENABLED = True
    settings.ANSWER_CACHE_BACKEND = "memory"
    settings.ANSWER_CACHE_MAXSIZE = 4
    settings.ANSWER_CACHE_TTL_SEC = 60
    yield
    (
        settings.ANSWER_CACHE_ENABLED,
        settings.ANSWER_CACHE_BACKEND,
        settings.ANSWER_CACHE_MAXSIZE,
        settings.ANSWER_CACHE_TTL_SEC,
    ) = prev
    cache_mod._reset_corpus_version_for_tests()
    cache_mod._reset_cache_singleton_for_tests()


def _response(answer: str = "ans") -> QueryResponse:
    return QueryResponse(
        question="how do I reset my password?",
        answer=answer,
        confidence=0.8,
        confidence_label="high",
        sources=[],
        citations=[],
        service_category="GENERAL",
        refused=False,
        visual_capable=False,
    )


# ── make_cache_key + corpus version --------------------------------------


def test_cache_key_is_stable_for_same_inputs():
    k1 = cache_mod.make_cache_key(question="x", top_k=5, service_category="GENERAL")
    k2 = cache_mod.make_cache_key(question="x", top_k=5, service_category="GENERAL")
    assert k1 == k2


def test_cache_key_differs_when_corpus_bumps():
    k1 = cache_mod.make_cache_key(question="x", top_k=5, service_category="GENERAL")
    cache_mod.bump_corpus_version(reason="test")
    k2 = cache_mod.make_cache_key(question="x", top_k=5, service_category="GENERAL")
    assert k1 != k2


def test_cache_key_differs_for_different_top_k():
    k1 = cache_mod.make_cache_key(question="x", top_k=5, service_category="GENERAL")
    k2 = cache_mod.make_cache_key(question="x", top_k=8, service_category="GENERAL")
    assert k1 != k2


def test_cache_key_differs_for_different_service_category():
    k1 = cache_mod.make_cache_key(question="x", top_k=5, service_category="GENERAL")
    k2 = cache_mod.make_cache_key(question="x", top_k=5, service_category="VPN")
    assert k1 != k2


def test_cache_key_normalizes_whitespace_and_case():
    k1 = cache_mod.make_cache_key(question="HELLO  ", top_k=5, service_category="GENERAL")
    k2 = cache_mod.make_cache_key(question="hello", top_k=5, service_category="general")
    assert k1 == k2


def test_corpus_version_starts_at_one():
    assert cache_mod.get_corpus_version() == 1


def test_bump_corpus_version_returns_new_value():
    assert cache_mod.bump_corpus_version() == 2
    assert cache_mod.bump_corpus_version(reason="ingest") == 3
    assert cache_mod.get_corpus_version() == 3


# ── MemoryAnswerCache ---------------------------------------------------


@pytest.mark.asyncio
async def test_memory_cache_set_and_get_round_trips():
    cache = cache_mod.MemoryAnswerCache(maxsize=4, ttl_sec=60)
    key = "k"
    await cache.set(key, _response("hello"))
    out = await cache.get(key)
    assert out is not None
    assert out.answer == "hello"
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    assert stats["size"] == 1


@pytest.mark.asyncio
async def test_memory_cache_miss_returns_none():
    cache = cache_mod.MemoryAnswerCache()
    out = await cache.get("nope")
    assert out is None
    assert cache.stats()["misses"] == 1


@pytest.mark.asyncio
async def test_memory_cache_lru_eviction():
    cache = cache_mod.MemoryAnswerCache(maxsize=2, ttl_sec=60)
    await cache.set("a", _response("A"))
    await cache.set("b", _response("B"))
    await cache.set("c", _response("C"))
    assert await cache.get("a") is None
    assert (await cache.get("b")).answer == "B"
    assert (await cache.get("c")).answer == "C"


@pytest.mark.asyncio
async def test_memory_cache_lru_promotes_on_get():
    cache = cache_mod.MemoryAnswerCache(maxsize=2, ttl_sec=60)
    await cache.set("a", _response("A"))
    await cache.set("b", _response("B"))
    await cache.get("a")
    await cache.set("c", _response("C"))
    assert (await cache.get("a")).answer == "A"
    assert await cache.get("b") is None
    assert (await cache.get("c")).answer == "C"


@pytest.mark.asyncio
async def test_memory_cache_ttl_expiry():
    cache = cache_mod.MemoryAnswerCache(maxsize=4, ttl_sec=60)
    await cache.set("k", _response("X"), ttl=0)
    await asyncio.sleep(0.01)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_memory_cache_clear():
    cache = cache_mod.MemoryAnswerCache()
    await cache.set("k", _response("X"))
    await cache.clear()
    assert await cache.get("k") is None
    assert cache.stats()["size"] == 0


# ── get_answer_cache resolver -------------------------------------------


def test_get_answer_cache_disabled_returns_none():
    settings = get_settings()
    settings.ANSWER_CACHE_ENABLED = False
    cache_mod._reset_cache_singleton_for_tests()
    assert cache_mod.get_answer_cache() is None


def test_get_answer_cache_memory_is_singleton():
    c1 = cache_mod.get_answer_cache()
    c2 = cache_mod.get_answer_cache()
    assert c1 is c2
    assert isinstance(c1, cache_mod.MemoryAnswerCache)


def test_get_answer_cache_redis_falls_back_when_unavailable():
    settings = get_settings()
    settings.ANSWER_CACHE_BACKEND = "redis"
    cache_mod._reset_cache_singleton_for_tests()
    cache = cache_mod.get_answer_cache()
    # Even when Redis import fails the resolver must hand back a usable
    # cache so the pipeline never crashes due to a misconfigured backend.
    assert cache is not None


# ── Invalidation via corpus-version bump --------------------------------


@pytest.mark.asyncio
async def test_corpus_bump_invalidates_lookups():
    cache = cache_mod.MemoryAnswerCache(maxsize=4, ttl_sec=60)
    key_v1 = cache_mod.make_cache_key(
        question="q", top_k=5, service_category="GENERAL"
    )
    await cache.set(key_v1, _response("v1"))
    cache_mod.bump_corpus_version(reason="ingest")
    key_v2 = cache_mod.make_cache_key(
        question="q", top_k=5, service_category="GENERAL"
    )
    assert key_v1 != key_v2
    assert await cache.get(key_v2) is None
    assert (await cache.get(key_v1)).answer == "v1"
