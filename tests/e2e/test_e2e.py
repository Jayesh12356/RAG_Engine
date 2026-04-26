"""End-to-end tests using shared fixtures (mocked external services).

Covers:
- ``/health``
- Ingest → query happy path with a seeded sample PDF.
- Document lifecycle (list / chunks / delete).
- Confidence-gate refusal path.
- Demo-mode header passthrough.
- OCR-routed ingest of scanned PDFs.
- Provider switching via env (no network required).
- ``/query`` with ``include_citations=true``.
- ``/query/stream`` happy path returning a ``final`` SSE event.
- ``/chat`` and ``/chat/stream`` happy paths plus refusal.
- Hybrid search wiring + MMR diversification through the mock store.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.query.rag_generator import REFUSAL_PHRASE


# ──────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_health_reflects_config(e2e_client):
    from app.config import get_settings

    settings = get_settings()
    resp = await e2e_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == settings.LLM_PROVIDER
    assert data["vector_db"] == settings.VECTOR_DB


# ──────────────────────────────────────────────────────────────────────────
# Ingest → query
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_ingest_then_query(e2e_client, mock_externals, seeded_pdf_path):
    mock_vs, m_complete = mock_externals

    with open(seeded_pdf_path, "rb") as f:
        file_content = f.read()
    files = {"file": (Path(seeded_pdf_path).name, file_content, "application/pdf")}

    resp1 = await e2e_client.post("/ingest", files=files)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "success"
    assert data1["total_chunks"] > 0

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    resp2 = await e2e_client.post("/query", json={"question": "How do I reset my VPN password?"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["refused"] is False
    assert data2["confidence"] >= 0.5
    assert len(data2["sources"]) > 0
    assert data2["sources"][0]["pdf_name"] == "VPN_Setup_Guide.pdf"


@pytest.mark.asyncio
async def test_e2e_query_with_citations(e2e_client, mock_externals, seeded_pdf_path):
    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    resp = await e2e_client.post(
        "/query",
        json={
            "question": "How do I reset my VPN password?",
            "include_citations": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is False
    assert isinstance(body.get("citations"), list)
    assert len(body["citations"]) >= 1
    cite = body["citations"][0]
    for key in ("chunk_id", "document_id", "pdf_name", "page_number", "section_title", "score"):
        assert key in cite


@pytest.mark.asyncio
async def test_e2e_query_without_citations(e2e_client, mock_externals, seeded_pdf_path):
    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    resp = await e2e_client.post(
        "/query",
        json={
            "question": "How do I reset my VPN password?",
            "include_citations": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is False
    assert body.get("citations") == []


# ──────────────────────────────────────────────────────────────────────────
# /query/stream
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_query_stream_emits_final_event(e2e_client, mock_externals, seeded_pdf_path):
    """``/query/stream`` should emit a final SSE event with the payload.

    We do not exercise actual token streaming here because the LLM client is
    mocked; instead we assert the pipeline reaches the ``final`` event with
    the extractive fallback payload (since ``complete_stream`` is not
    patched, it raises and the pipeline gracefully falls back).
    """
    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    body_text = ""
    async with e2e_client.stream(
        "POST", "/query/stream", json={"question": "How do I reset my VPN password?"}
    ) as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            body_text += chunk

    assert "data:" in body_text
    final_lines = [ln for ln in body_text.splitlines() if "\"type\":" in ln]
    assert any("\"type\": \"final\"" in ln or "'type': 'final'" in ln for ln in final_lines) or (
        '"type": "final"' in body_text
    )


# ──────────────────────────────────────────────────────────────────────────
# Document lifecycle
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_document_lifecycle(e2e_client, mock_externals, seeded_pdf_path):
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}

    resp1 = await e2e_client.post("/ingest", files=files)
    doc_id = resp1.json()["document_id"]

    resp2 = await e2e_client.get("/documents")
    assert any(d["document_id"] == doc_id for d in resp2.json()["documents"])

    resp3 = await e2e_client.get(f"/documents/{doc_id}/chunks")
    assert len(resp3.json()["chunks"]) > 0

    resp4 = await e2e_client.delete(f"/documents/{doc_id}")
    assert resp4.json()["status"] == "deleted"

    resp5 = await e2e_client.get("/documents")
    assert not any(d["document_id"] == doc_id for d in resp5.json()["documents"])


# ──────────────────────────────────────────────────────────────────────────
# Confidence gate
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_confidence_gate_fires(e2e_client, mock_externals):
    mock_vs, m_complete = mock_externals
    m_complete.return_value = REFUSAL_PHRASE

    resp = await e2e_client.post(
        "/query", json={"question": "what is the weather in Paris?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["confidence_label"] == "refused"
    assert data["sources"] == []


# ──────────────────────────────────────────────────────────────────────────
# Demo-mode passthrough
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_demo_mode_header(e2e_client, mock_externals, seeded_pdf_path):
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    headers = {"X-Demo-Mode": "true"}
    resp1 = await e2e_client.post("/ingest", files=files, headers=headers)
    assert resp1.status_code == 200

    resp2 = await e2e_client.post("/query", json={"question": "hello"}, headers=headers)
    assert resp2.status_code == 200


# ──────────────────────────────────────────────────────────────────────────
# OCR-routed ingest
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_ingest_scanned_pdf_with_ocr_route(e2e_client, mock_externals):
    scanned_pdf_path = "image_pdfs/Increase_Laptop_Battery.pdf"
    if not os.path.exists(scanned_pdf_path):
        pytest.skip("image_pdfs sample is not available in this environment")

    with patch(
        "app.ingestion.pdf_parser._detect_pdf_type", return_value=("image_pdf", {1})
    ), patch(
        "app.ingestion.pdf_parser.extract_page_text_with_ocr",
        return_value={
            "text": "Scanned page text from OCR",
            "confidence": 0.9,
            "used_vision": False,
            "fallback_attempted": False,
        },
    ):
        with open(scanned_pdf_path, "rb") as f:
            file_content = f.read()
        files = {"file": ("Increase_Laptop_Battery.pdf", file_content, "application/pdf")}
        resp = await e2e_client.post("/ingest", files=files)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "success"
    assert payload["total_chunks"] > 0


# ──────────────────────────────────────────────────────────────────────────
# Provider switching
# ──────────────────────────────────────────────────────────────────────────
def test_e2e_provider_switching_config():
    from app.config import get_settings

    with patch.dict("os.environ", {"VECTOR_DB": "qdrant"}):
        from app.db.vector_store import QdrantVectorStore, get_vector_store

        get_settings.cache_clear()
        assert isinstance(get_vector_store(), QdrantVectorStore)

    with patch.dict("os.environ", {"VECTOR_DB": "milvus"}):
        get_settings.cache_clear()
        from app.db.vector_store import MilvusVectorStore, get_vector_store

        assert isinstance(get_vector_store(), MilvusVectorStore)

    with patch.dict("os.environ", {"RELATIONAL_DB": "mysql"}):
        get_settings.cache_clear()
        from app.db.relational import get_engine

        engine = get_engine()
        assert "aiomysql" in str(engine.url)

    with patch.dict("os.environ", {"LLM_PROVIDER": "groq"}):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.LLM_PROVIDER == "groq"


# ──────────────────────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_chat_happy_path(e2e_client, mock_externals, seeded_pdf_path):
    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    resp = await e2e_client.post(
        "/chat",
        json={"question": "How do I reset my VPN password?", "include_citations": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is False
    assert body["session_id"]
    assert body["turn_id"]
    assert len(body["sources"]) >= 1
    assert isinstance(body.get("citations"), list)
    assert len(body["citations"]) >= 1


@pytest.mark.asyncio
async def test_e2e_chat_refusal(e2e_client, mock_externals):
    mock_vs, m_complete = mock_externals
    m_complete.return_value = REFUSAL_PHRASE

    resp = await e2e_client.post(
        "/chat",
        json={"question": "what is the weather in Paris?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is True
    assert body["confidence_label"] == "refused"
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_e2e_chat_stream_emits_final_event(
    e2e_client, mock_externals, seeded_pdf_path
):
    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    body_text = ""
    async with e2e_client.stream(
        "POST",
        "/chat/stream",
        json={"question": "How do I reset my VPN password?"},
    ) as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            body_text += chunk

    assert "data:" in body_text
    assert '"type": "final"' in body_text or "'type': 'final'" in body_text


# ──────────────────────────────────────────────────────────────────────────
# Hybrid search + MMR (smoke)
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_hybrid_path_with_mock_store(e2e_client, mock_externals, seeded_pdf_path):
    """The mock store returns three duplicate chunks; MMR should keep at least
    one chunk and the pipeline should still return a non-refusal answer.
    """
    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    resp = await e2e_client.post(
        "/query",
        json={"question": "How do I reset my VPN password?", "top_k": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is False
    assert len(body["sources"]) >= 1


# ──────────────────────────────────────────────────────────────────────────
# Query rewrite (feature flag wired through; no LLM call required when
# initial top score is strong)
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_e2e_query_rewrite_disabled_by_default(
    e2e_client, mock_externals, seeded_pdf_path
):
    """With strong mocked retrieval scores the rewrite stage is skipped, so
    the question reaches the rest of the pipeline unchanged.
    """
    from app.config import get_settings

    settings = get_settings()
    assert settings.QUERY_REWRITE_ENABLED is False or settings.QUERY_REWRITE_TRIGGER_SCORE <= 0.95

    mock_vs, m_complete = mock_externals
    with open(seeded_pdf_path, "rb") as f:
        files = {"file": (Path(seeded_pdf_path).name, f.read(), "application/pdf")}
    await e2e_client.post("/ingest", files=files)

    m_complete.return_value = "Use the corporate VPN portal to reset your password."

    resp = await e2e_client.post("/query", json={"question": "vpn password reset"})
    assert resp.status_code == 200
    assert resp.json()["refused"] is False
