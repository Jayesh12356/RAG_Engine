"""Unit tests for the local cross-encoder rerank fallback."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.models.query import SearchResult
from app.query import local_reranker
from app.query.local_reranker import _try_load, maybe_local_rerank
from app.query.reranker import CohereReranker


def _make_results() -> list[SearchResult]:
    return [
        SearchResult(chunk_id="c1", document_id="d", text="alpha", score=0.5),
        SearchResult(chunk_id="c2", document_id="d", text="beta", score=0.4),
        SearchResult(chunk_id="c3", document_id="d", text="gamma", score=0.3),
    ]


@pytest.fixture(autouse=True)
def _reset_caches():
    local_reranker._reset_cache_for_tests()
    yield
    local_reranker._reset_cache_for_tests()


# ── _try_load -----------------------------------------------------------------


def test_try_load_returns_none_when_disabled():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = False
    assert _try_load() is None


def test_try_load_returns_none_when_dependency_missing():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = True
    try:
        with patch.dict(
            "sys.modules", {"sentence_transformers": None}
        ):
            assert _try_load() is None
        # Subsequent calls short-circuit (cache miss but failure is sticky).
        assert local_reranker._load_failed is True
    finally:
        settings.LOCAL_RERANKER_ENABLED = False


# ── maybe_local_rerank --------------------------------------------------------


@pytest.mark.asyncio
async def test_maybe_local_rerank_short_circuits_when_disabled():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = False
    out = await maybe_local_rerank("q", _make_results(), top_n=2)
    assert out is None


@pytest.mark.asyncio
async def test_maybe_local_rerank_returns_empty_for_empty_results():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = True
    try:
        out = await maybe_local_rerank("q", [], top_n=5)
        assert out == []
    finally:
        settings.LOCAL_RERANKER_ENABLED = False


@pytest.mark.asyncio
async def test_maybe_local_rerank_returns_none_when_load_fails():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = True
    try:
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            out = await maybe_local_rerank("q", _make_results(), top_n=2)
            assert out is None
    finally:
        settings.LOCAL_RERANKER_ENABLED = False


@pytest.mark.asyncio
async def test_maybe_local_rerank_scores_with_mocked_model():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = True
    fake_model = MagicMock()
    # cross-encoder predict yields one score per (q, doc) pair, in input order
    fake_model.predict.return_value = [0.1, 0.9, 0.5]
    try:
        with patch(
            "app.query.local_reranker._try_load", return_value=fake_model
        ):
            out = await maybe_local_rerank("q", _make_results(), top_n=2)
        assert out is not None and len(out) == 2
        # Highest score (0.9 → c2) wins
        assert out[0].chunk_id == "c2"
        assert out[1].chunk_id == "c3"
    finally:
        settings.LOCAL_RERANKER_ENABLED = False


@pytest.mark.asyncio
async def test_maybe_local_rerank_returns_none_on_score_failure():
    settings = get_settings()
    settings.LOCAL_RERANKER_ENABLED = True
    fake_model = MagicMock()
    fake_model.predict.side_effect = RuntimeError("torch crash")
    try:
        with patch(
            "app.query.local_reranker._try_load", return_value=fake_model
        ):
            out = await maybe_local_rerank("q", _make_results(), top_n=2)
        assert out is None
    finally:
        settings.LOCAL_RERANKER_ENABLED = False


# ── CohereReranker fallback chain --------------------------------------------


@pytest.mark.asyncio
async def test_cohere_reranker_uses_local_fallback_when_cohere_fails():
    """Cohere down → local cross-encoder picks up the rerank."""
    fake_local = [
        SearchResult(chunk_id="c2", document_id="d", text="beta", score=0.99),
        SearchResult(chunk_id="c1", document_id="d", text="alpha", score=0.5),
    ]
    reranker = CohereReranker(demo_mode=False)
    reranker.client = MagicMock()
    reranker.client.rerank = AsyncMock(side_effect=RuntimeError("cohere down"))
    with patch(
        "app.query.reranker.maybe_local_rerank",
        new=AsyncMock(return_value=fake_local),
    ):
        out = await reranker.rerank("q", _make_results(), top_n=2)
    assert [r.chunk_id for r in out] == ["c2", "c1"]


@pytest.mark.asyncio
async def test_cohere_reranker_falls_to_lexical_when_local_unavailable():
    """Cohere down + local unavailable → lexical overlap rescores."""
    reranker = CohereReranker(demo_mode=False)
    reranker.client = MagicMock()
    reranker.client.rerank = AsyncMock(side_effect=RuntimeError("cohere down"))
    results = [
        SearchResult(
            chunk_id="c1", document_id="d", text="alpha apple", score=0.5
        ),
        SearchResult(
            chunk_id="c2", document_id="d", text="beta banana", score=0.5
        ),
        SearchResult(
            chunk_id="c3", document_id="d", text="completely unrelated", score=0.5
        ),
    ]
    with patch(
        "app.query.reranker.maybe_local_rerank",
        new=AsyncMock(return_value=None),
    ):
        out = await reranker.rerank("apple snack", results, top_n=3)
    # Lexical overlap rescue boosts c1 ("apple" word match) above c3.
    assert out[0].chunk_id == "c1"
    assert out[-1].chunk_id == "c3"


@pytest.mark.asyncio
async def test_cohere_reranker_handles_local_raising_exception():
    reranker = CohereReranker(demo_mode=False)
    reranker.client = MagicMock()
    reranker.client.rerank = AsyncMock(side_effect=RuntimeError("cohere down"))
    with patch(
        "app.query.reranker.maybe_local_rerank",
        new=AsyncMock(side_effect=RuntimeError("local crash")),
    ):
        # Must still return a valid list via lexical fallback.
        out = await reranker.rerank("q", _make_results(), top_n=2)
    assert len(out) == 2
