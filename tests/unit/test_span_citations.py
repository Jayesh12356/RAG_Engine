"""Tests for span-level citations + SSE ``citations`` events."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.models.query import QueryRequest, SearchResult, TextSpan
from app.query.pipeline import QueryPipeline
from app.query.rag_generator import _best_span_for_question, build_citations


def _result(text: str, *, chunk_id: str = "c1", **kwargs) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=kwargs.pop("document_id", "doc-a"),
        text=text,
        score=kwargs.pop("score", 0.5),
        metadata=kwargs.pop("metadata", {"pdf_name": "doc.pdf", "page_number": 1}),
    )


# ── _best_span_for_question ───────────────────────────────────────────────


def test_span_picks_overlapping_sentence():
    chunk = (
        "VPN access uses the corporate portal. "
        "Resetting your VPN password requires email verification. "
        "All connections require Duo two-factor."
    )
    span = _best_span_for_question("how do I reset my VPN password", chunk)
    assert span is not None
    assert "Reset" in span.text or "reset" in span.text
    assert span.start >= 0
    assert span.end > span.start
    assert chunk[span.start:span.end].startswith("Resetting")


def test_span_falls_back_to_first_sentence_when_no_overlap():
    chunk = "First sentence. Second sentence. Third."
    span = _best_span_for_question("totally unrelated noun", chunk)
    assert span is not None
    assert span.text.startswith("First")
    assert span.start == 0


def test_span_returns_none_for_empty_chunk():
    assert _best_span_for_question("anything", "") is None
    assert _best_span_for_question("anything", "   ") is None


def test_span_caps_to_max_chars():
    chunk = "A" * 1000
    span = _best_span_for_question("a", chunk, max_chars=100)
    assert span is not None
    assert len(span.text) <= 100


def test_span_handles_chunk_without_sentence_terminators():
    chunk = "no terminator here just words and phrases"
    span = _best_span_for_question("words", chunk)
    assert span is not None
    assert "words" in span.text


# ── build_citations ───────────────────────────────────────────────────────


def test_build_citations_emits_text_span_when_question_provided():
    chunks = [
        _result(
            "Background context unrelated. Resetting your VPN password is documented in the IT manual.",
            chunk_id="c1",
        ),
    ]
    cites = build_citations(chunks, question="how to reset VPN password")
    assert len(cites) == 1
    assert cites[0].text_span is not None
    assert "Reset" in (cites[0].text_span.text or "")


def test_build_citations_works_without_question():
    chunks = [_result("Just some text here. And more text.", chunk_id="c1")]
    cites = build_citations(chunks)
    assert len(cites) == 1
    assert cites[0].text_span is not None
    # First sentence is the fallback
    assert cites[0].text_span.text.startswith("Just some")


def test_text_span_round_trips_via_pydantic():
    span = TextSpan(text="hello", start=0, end=5)
    assert span.model_dump() == {"text": "hello", "start": 0, "end": 5}


# ── SSE citation event in run_stream ──────────────────────────────────────


@pytest.mark.asyncio
async def test_query_stream_emits_citations_event_when_requested():
    settings = get_settings()
    settings.HYDE_ENABLED = False
    settings.MULTI_QUERY_ENABLED = False

    pipeline = QueryPipeline(demo_mode=True)
    request = QueryRequest(
        question="how do I reset my VPN password",
        include_citations=True,
    )

    fake_stream = AsyncMock()

    async def _stream(*_a, **_kw):
        yield "answer "
        yield "tokens"

    pipeline.searcher = MagicMock()
    pipeline.searcher.search = AsyncMock(
        return_value=[
            _result(
                "VPN password reset is in the corporate portal. Use Duo for 2FA.",
                chunk_id="c1",
                score=0.9,
            ),
            _result(
                "SSL certificate issues require an active VPN.",
                chunk_id="c2",
                score=0.4,
            ),
        ]
    )
    pipeline.reranker = MagicMock()
    pipeline.reranker.rerank = AsyncMock(side_effect=lambda q, r, n: r[:n])

    with patch(
        "app.query.pipeline.llm_client.complete_stream",
        side_effect=_stream,
    ):
        events: list[dict] = []
        async for raw in pipeline.run_stream(request):
            assert raw.startswith("data: ")
            payload = json.loads(raw.removeprefix("data: ").strip())
            events.append(payload)

    types = [e["type"] for e in events]
    assert "citations" in types
    citations_event = next(e for e in events if e["type"] == "citations")
    assert isinstance(citations_event["items"], list)
    assert len(citations_event["items"]) >= 1
    first = citations_event["items"][0]
    # text_span should be present and non-empty for the top chunk
    assert first.get("text_span") is not None
    assert first["text_span"]["text"]


@pytest.mark.asyncio
async def test_query_stream_omits_citations_event_when_not_requested():
    settings = get_settings()
    settings.INCLUDE_CITATIONS_DEFAULT = False
    settings.HYDE_ENABLED = False
    settings.MULTI_QUERY_ENABLED = False

    pipeline = QueryPipeline(demo_mode=True)
    request = QueryRequest(question="anything")

    async def _stream(*_a, **_kw):
        yield "ok"

    pipeline.searcher = MagicMock()
    pipeline.searcher.search = AsyncMock(
        return_value=[
            _result("Hello there world. Another sentence.", chunk_id="c1", score=0.9),
            _result("Other text. Filler sentence.", chunk_id="c2", score=0.85),
        ]
    )
    pipeline.reranker = MagicMock()
    pipeline.reranker.rerank = AsyncMock(side_effect=lambda q, r, n: r[:n])

    with patch(
        "app.query.pipeline.llm_client.complete_stream",
        side_effect=_stream,
    ):
        types: list[str] = []
        async for raw in pipeline.run_stream(request):
            payload = json.loads(raw.removeprefix("data: ").strip())
            types.append(payload["type"])

    assert "citations" not in types
