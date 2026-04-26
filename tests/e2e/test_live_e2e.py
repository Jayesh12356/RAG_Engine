"""Live end-to-end smoke test against real Qdrant + provider APIs.

This suite is gated behind ``RUN_LIVE_E2E=1`` and is **skipped** by default
so the unit/integration/mocked-E2E tests stay deterministic and offline.

It is intentionally minimal — we only assert that the full pipeline can:

1. Connect to Qdrant (via ``QDRANT_URL``).
2. Ingest the seeded VPN sample PDF.
3. Answer a VPN question with a non-refusal answer and at least one citation
   pointing back to the seeded document.
4. Refuse cleanly on an out-of-scope question.

If any required service or key is missing the test cleanly skips. CI is
expected to keep ``RUN_LIVE_E2E`` unset; developers run this by hand or in
a dedicated nightly job.
"""
from __future__ import annotations

import asyncio
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_E2E") != "1",
    reason="live e2e disabled (set RUN_LIVE_E2E=1 to run)",
)


def _qdrant_reachable() -> bool:
    from app.config import get_settings

    parsed = urlparse(get_settings().QDRANT_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if (parsed.scheme or "").startswith("https") else 6333)
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except OSError:
        return False


def _have_any_llm_key() -> bool:
    from app.config import get_settings

    s = get_settings()
    return any([s.GROQ_API_KEY, s.OPENAI_API_KEY, s.OPENROUTER_API_KEY])


def _have_any_embedding_key() -> bool:
    from app.config import get_settings

    s = get_settings()
    return any([s.OPENAI_API_KEY, s.OPENROUTER_API_KEY, s.COHERE_API_KEY])


@pytest.mark.asyncio
async def test_live_vpn_question_returns_grounded_answer(seeded_pdf_path):
    if not _qdrant_reachable():
        pytest.skip("Qdrant is not reachable at QDRANT_URL")
    if not _have_any_llm_key() or not _have_any_embedding_key():
        pytest.skip("no LLM/embedding provider keys configured")

    from app.config import get_settings
    from app.db.relational import init_db
    from app.db.vector_store import get_vector_store
    from app.ingestion.pipeline import IngestPipeline
    from app.models.query import QueryRequest
    from app.query.pipeline import QueryPipeline

    settings = get_settings()

    await init_db()
    vs = get_vector_store()
    await vs.ensure_collection(settings.vector_collection, settings.EMBEDDING_DIM)

    with open(seeded_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    ingest = IngestPipeline(demo_mode=False)
    result = await ingest.run(
        seeded_pdf_path,
        pdf_bytes=pdf_bytes,
        content_type="application/pdf",
    )
    assert result.status == "success", result.error
    assert result.total_chunks > 0

    pipeline = QueryPipeline(demo_mode=False)
    response = await pipeline.run(
        QueryRequest(
            question="How do I reset my VPN password?",
            include_citations=True,
        )
    )

    assert response.refused is False, f"unexpected refusal: {response.answer!r}"
    assert response.confidence >= settings.CONFIDENCE_THRESHOLD
    assert response.citations, "expected at least one citation in live e2e"
    pdf_names = {c.pdf_name for c in response.citations}
    assert Path(seeded_pdf_path).name in pdf_names

    # Out-of-scope question should refuse cleanly.
    refusal = await pipeline.run(QueryRequest(question="what is the weather in Paris?"))
    assert refusal.refused is True
    assert refusal.confidence_label == "refused"
    assert refusal.sources == []


@pytest.mark.asyncio
async def test_live_chat_round_trip(seeded_pdf_path):
    """Smoke-test the chat pipeline end-to-end with real providers."""
    if not _qdrant_reachable():
        pytest.skip("Qdrant is not reachable at QDRANT_URL")
    if not _have_any_llm_key() or not _have_any_embedding_key():
        pytest.skip("no LLM/embedding provider keys configured")

    from app.chat.pipeline import ChatPipeline, ChatRequest
    from app.config import get_settings

    settings = get_settings()
    pipeline = ChatPipeline(demo_mode=False)

    response = await pipeline.run(
        ChatRequest(question="How do I reset my VPN password?", include_citations=True)
    )
    assert response.refused is False, f"unexpected refusal: {response.answer!r}"
    assert response.confidence >= settings.CONFIDENCE_THRESHOLD
    assert response.session_id
    assert response.turn_id


def test_live_suite_imports_cleanly():
    """Sanity check: importing the live suite must not crash even without
    env vars present (the gate is a pytestmark, not an import-time check)."""
    assert asyncio is not None
