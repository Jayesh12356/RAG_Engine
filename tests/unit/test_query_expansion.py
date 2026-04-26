"""Unit tests for retrieval-expansion modules.

Covers HyDE (``app.query.hyde``), multi-query paraphrase (``app.query.multiquery``),
and the orchestrator (``app.query.expand``). Mocks the LLM client and
HybridSearch so tests stay deterministic and offline.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.models.query import SearchResult
from app.query.expand import _rrf_fuse, expanded_search
from app.query.hyde import generate_hypothetical_answer
from app.query.multiquery import _parse_paraphrases, generate_paraphrases


def _result(chunk_id: str, score: float = 0.5, document_id: str = "doc-a") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=document_id,
        text=f"text for {chunk_id}",
        score=score,
        metadata={},
    )


# ── HyDE ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.query.hyde.llm_client.complete", new_callable=AsyncMock)
async def test_hyde_generates_text(mock_complete):
    mock_complete.return_value = (
        "Resetting your VPN password starts at the corporate portal. "
        "After authentication, choose 'Reset password' and follow the email "
        "verification step. Updates propagate to Pulse Secure in minutes."
    )
    out = await generate_hypothetical_answer("how do I reset my VPN password")
    assert out is not None and "vpn" in out.lower()
    mock_complete.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.query.hyde.llm_client.complete", new_callable=AsyncMock)
async def test_hyde_returns_none_on_failure(mock_complete):
    mock_complete.side_effect = RuntimeError("provider down")
    out = await generate_hypothetical_answer("anything")
    assert out is None


@pytest.mark.asyncio
@patch("app.query.hyde.llm_client.complete", new_callable=AsyncMock)
async def test_hyde_returns_none_on_short_output(mock_complete):
    mock_complete.return_value = "ok"
    out = await generate_hypothetical_answer("anything")
    assert out is None


@pytest.mark.asyncio
async def test_hyde_returns_none_on_empty_question():
    out = await generate_hypothetical_answer("   ")
    assert out is None


@pytest.mark.asyncio
@patch("app.query.hyde.llm_client.complete", new_callable=AsyncMock)
async def test_hyde_respects_timeout(mock_complete):
    async def slow(*_a, **_kw):
        await asyncio.sleep(0.5)
        return "long enough hypothetical response with details"

    mock_complete.side_effect = slow
    out = await generate_hypothetical_answer("question", timeout_sec=0.05)
    assert out is None


# ── Multi-query ───────────────────────────────────────────────────────────


def test_parse_paraphrases_drops_original_and_numbers():
    raw = (
        "1. how do I reset my VPN password\n"  # echoes original
        "2) Steps to change Pulse Secure password\n"
        "- Forgot VPN credentials, what now?\n"
        "Resetting corporate VPN access for new staff\n"
        "tiny\n"  # too short
    )
    out = _parse_paraphrases(raw, original="how do I reset my VPN password", n=3)
    assert len(out) == 3
    assert "Steps to change Pulse Secure password" in out
    assert all(not item.startswith(("1.", "2)", "-")) for item in out)


def test_parse_paraphrases_caps_at_n():
    raw = "\n".join(f"variant {i}" for i in range(10))
    out = _parse_paraphrases(raw, original="orig", n=3)
    assert len(out) == 3


@pytest.mark.asyncio
@patch("app.query.multiquery.llm_client.complete", new_callable=AsyncMock)
async def test_generate_paraphrases_happy_path(mock_complete):
    mock_complete.return_value = (
        "How can I update my VPN password?\n"
        "Process for changing the corporate VPN password\n"
        "VPN credential reset workflow\n"
    )
    out = await generate_paraphrases("how do I reset my VPN password", n=3)
    assert len(out) == 3


@pytest.mark.asyncio
@patch("app.query.multiquery.llm_client.complete", new_callable=AsyncMock)
async def test_generate_paraphrases_fails_open(mock_complete):
    mock_complete.side_effect = RuntimeError("nope")
    out = await generate_paraphrases("anything", n=3)
    assert out == []


@pytest.mark.asyncio
async def test_generate_paraphrases_no_calls_when_n_zero():
    with patch("app.query.multiquery.llm_client.complete", new_callable=AsyncMock) as mc:
        out = await generate_paraphrases("q", n=0)
        assert out == []
        mc.assert_not_awaited()


# ── RRF fusion ────────────────────────────────────────────────────────────


def test_rrf_fuse_prefers_chunks_appearing_in_multiple_lists():
    list_a = [_result("c1"), _result("c2"), _result("c3")]
    list_b = [_result("c4"), _result("c1"), _result("c5")]  # c1 ranks 2nd
    list_c = [_result("c1"), _result("c6"), _result("c7")]  # c1 ranks 1st

    fused = _rrf_fuse([list_a, list_b, list_c], rrf_k=60, top_k=3)
    assert fused[0].chunk_id == "c1"
    assert len(fused) == 3


def test_rrf_fuse_dedupes_chunks_across_lists():
    list_a = [_result("c1"), _result("c2")]
    list_b = [_result("c1"), _result("c2")]
    fused = _rrf_fuse([list_a, list_b], rrf_k=60, top_k=10)
    ids = [r.chunk_id for r in fused]
    assert ids.count("c1") == 1
    assert ids.count("c2") == 1


def test_rrf_fuse_ignores_blank_chunk_ids():
    list_a = [SearchResult(chunk_id="", document_id="d", text="t", score=1.0)]
    fused = _rrf_fuse([list_a], rrf_k=60, top_k=10)
    assert fused == []


# ── expanded_search ───────────────────────────────────────────────────────


class _StubSearcher:
    """Records every (question, top_k) it sees and returns canned hits."""

    def __init__(self, response_map: dict[str, list[SearchResult]] | None = None):
        self.response_map = response_map or {}
        self.calls: list[tuple[str, str | None, int]] = []

    async def search(self, question, service_category, top_k, tags=None):
        self.calls.append((question, service_category, top_k))
        return self.response_map.get(question, [_result(f"chunk-{question[:8]}")])


@pytest.mark.asyncio
async def test_expanded_search_passthrough_when_flags_off():
    settings = get_settings()
    settings.HYDE_ENABLED = False
    settings.MULTI_QUERY_ENABLED = False

    searcher = _StubSearcher()
    out = await expanded_search(searcher, "what is VPN", None, top_k=5)
    assert len(out) == 1
    assert searcher.calls == [("what is VPN", None, 5)]


@pytest.mark.asyncio
@patch("app.query.expand.generate_paraphrases", new_callable=AsyncMock)
@patch("app.query.expand.generate_hypothetical_answer", new_callable=AsyncMock)
async def test_expanded_search_fans_out_when_both_flags_on(mock_hyde, mock_para):
    settings = get_settings()
    settings.HYDE_ENABLED = True
    settings.MULTI_QUERY_ENABLED = True
    settings.MULTI_QUERY_VARIANTS = 2

    mock_hyde.return_value = "hypothetical paragraph about VPN reset"
    mock_para.return_value = ["VPN password change", "reset corporate VPN"]

    searcher = _StubSearcher(
        {
            "what is VPN": [_result("c-orig", score=0.9)],
            "hypothetical paragraph about VPN reset": [_result("c-hyde", score=0.8)],
            "VPN password change": [_result("c-mq1", score=0.7)],
            "reset corporate VPN": [_result("c-mq2", score=0.6)],
        }
    )

    try:
        out = await expanded_search(searcher, "what is VPN", None, top_k=10)
        # 4 fanned-out searches: original + hyde + 2 paraphrases
        assert len(searcher.calls) == 4
        ids = {r.chunk_id for r in out}
        assert ids == {"c-orig", "c-hyde", "c-mq1", "c-mq2"}
    finally:
        settings.HYDE_ENABLED = False
        settings.MULTI_QUERY_ENABLED = False


@pytest.mark.asyncio
@patch("app.query.expand.generate_paraphrases", new_callable=AsyncMock)
@patch("app.query.expand.generate_hypothetical_answer", new_callable=AsyncMock)
async def test_expanded_search_falls_back_when_expansions_empty(mock_hyde, mock_para):
    settings = get_settings()
    settings.HYDE_ENABLED = True
    settings.MULTI_QUERY_ENABLED = True
    settings.MULTI_QUERY_VARIANTS = 3
    mock_hyde.return_value = None
    mock_para.return_value = []

    searcher = _StubSearcher()
    try:
        out = await expanded_search(searcher, "q", None, top_k=5)
        assert len(out) == 1
        assert len(searcher.calls) == 1  # only the original
    finally:
        settings.HYDE_ENABLED = False
        settings.MULTI_QUERY_ENABLED = False


@pytest.mark.asyncio
@patch("app.query.expand.generate_paraphrases", new_callable=AsyncMock)
@patch("app.query.expand.generate_hypothetical_answer", new_callable=AsyncMock)
async def test_expanded_search_handles_searcher_failures(mock_hyde, mock_para):
    settings = get_settings()
    settings.HYDE_ENABLED = True
    settings.MULTI_QUERY_ENABLED = False
    mock_hyde.return_value = "hypothetical text"

    class FlakySearcher(_StubSearcher):
        async def search(self, question, service_category, top_k, tags=None):
            self.calls.append((question, service_category, top_k))
            if question == "hypothetical text":
                raise RuntimeError("boom")
            return [_result("c-good")]

    searcher = FlakySearcher()
    try:
        out = await expanded_search(searcher, "q", None, top_k=5)
        # The healthy original-question result still shows up.
        assert any(r.chunk_id == "c-good" for r in out)
    finally:
        settings.HYDE_ENABLED = False
