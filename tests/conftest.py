"""Shared pytest fixtures.

These fixtures replace the boilerplate that used to live in
``tests/e2e/test_e2e.py`` (DB engine wiring, mock vector store, mocked
LLM/rerank/embed, seeded sample PDF) so any new test file can pick up the
same well-known harness.

Fixtures
--------
- ``seeded_pdf_path``: session-scoped path to ``VPN_Setup_Guide.pdf``. If
  the committed asset is missing, the file is generated into a tmp_path
  via ``data/sample_pdfs/sample_it_guide.py`` so test runs do not depend
  on a binary in version control.
- ``e2e_client``: ``httpx.AsyncClient`` wired to the ``app.main`` app
  with an in-memory SQLite session for relational state.
- ``mock_externals``: monkey-patches embeddings, completion, reranker
  and the vector store to deterministic in-memory implementations.
"""
from __future__ import annotations

import importlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ──────────────────────────────────────────────────────────────────────────
# Sample PDF
# ──────────────────────────────────────────────────────────────────────────
SAMPLE_PDF_NAME = "VPN_Setup_Guide.pdf"


@pytest.fixture(scope="session")
def seeded_pdf_path(tmp_path_factory) -> str:
    """Path to a usable VPN_Setup_Guide.pdf.

    We prefer the committed copy under ``data/sample_pdfs/`` (so the same
    bytes are exercised by manual smoke tests). When that is missing, the
    generator script under ``data/sample_pdfs/sample_it_guide.py`` is
    invoked to materialise an equivalent PDF into a tmp directory.
    """
    committed = Path(__file__).resolve().parent.parent / "data" / "sample_pdfs" / SAMPLE_PDF_NAME
    if committed.exists():
        return str(committed)

    target_dir = tmp_path_factory.mktemp("seeded_pdfs")
    target_path = target_dir / SAMPLE_PDF_NAME
    spec = importlib.util.spec_from_file_location(
        "sample_it_guide",
        Path(__file__).resolve().parent.parent / "data" / "sample_pdfs" / "sample_it_guide.py",
    )
    if spec is None or spec.loader is None:
        pytest.skip("sample PDF generator unavailable")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.create_sample_pdf(str(target_path))
    return str(target_path)


# ──────────────────────────────────────────────────────────────────────────
# E2E HTTP client wired with in-memory SQLite
# ──────────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def e2e_client() -> AsyncIterator[AsyncClient]:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.db.relational import Base
    from app.main import app as main_app

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    with patch("app.db.relational.get_engine", return_value=test_engine), patch(
        "app.db.relational.get_session_maker", return_value=test_session_maker
    ), patch("app.api.routes.session_maker", test_session_maker):
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        transport = ASGITransport(app=main_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# ──────────────────────────────────────────────────────────────────────────
# Mock external services (embed / complete / rerank / vector store)
# ──────────────────────────────────────────────────────────────────────────
class _MockVectorStore:
    """In-memory vector store sufficient for ingest + query round-trips."""

    supports_sparse: bool = False

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    async def upsert(self, collection, id, vector, payload=None, sparse_vector=None):
        self.store[id] = payload or {}

    async def hybrid_search(self, collection, dense_vec, sparse_vec, top_k, filter=None):
        from app.models.query import SearchResult

        chunk = SearchResult(
            chunk_id="chunk1",
            document_id="doc1",
            text="Mocked text about VPN setup and password reset.",
            score=0.95,
            metadata={
                "pdf_name": SAMPLE_PDF_NAME,
                "page_number": 1,
                "section_title": "Setup",
                "document_id": "doc1",
                "chunk_id": "chunk1",
            },
        )
        chunk2 = SearchResult(
            chunk_id="chunk2",
            document_id="doc1",
            text="Two-factor authentication via Duo Mobile is required.",
            score=0.86,
            metadata={
                "pdf_name": SAMPLE_PDF_NAME,
                "page_number": 2,
                "section_title": "Authentication",
                "document_id": "doc1",
                "chunk_id": "chunk2",
            },
        )
        return [chunk, chunk2, chunk]

    async def search_by_vector(self, collection, vector, top_k, filter=None):
        return await self.hybrid_search(collection, vector, None, top_k, filter)

    async def delete(self, collection, chunk_ids):
        for cid in chunk_ids:
            self.store.pop(cid, None)
        return len(chunk_ids)

    async def delete_by_filter(self, collection, filter):
        return None

    async def upsert_payload(self, collection, id, payload):
        self.store[id] = payload

    async def fetch_payloads(self, collection, filter, limit=10000):
        return []

    async def ensure_collection(self, name, dim):
        return None


@pytest_asyncio.fixture
async def mock_externals():
    """Patch LLM/embed/rerank and the vector store with deterministic stubs.

    Yields a tuple of ``(vector_store, complete_mock)`` so individual tests
    can override the LLM response (e.g. for refusal-path tests).
    """
    from app.config import get_settings
    from app.models.query import SearchResult

    settings = get_settings()
    mock_vs = _MockVectorStore()

    async def _embed(texts):
        return [[0.1] * settings.EMBEDDING_DIM for _ in texts]

    async def _embed_query(text):
        return [0.1] * settings.EMBEDDING_DIM

    chunk = SearchResult(
        chunk_id="chunk1",
        document_id="doc1",
        text="Mocked text about VPN setup and password reset.",
        score=0.95,
        metadata={
            "pdf_name": SAMPLE_PDF_NAME,
            "page_number": 1,
            "section_title": "Setup",
            "document_id": "doc1",
            "chunk_id": "chunk1",
        },
    )

    with patch("app.llm.client.embed", new_callable=AsyncMock) as m_embed_legacy, patch(
        "app.llm.client.embed_documents", new=_embed
    ), patch("app.llm.client.embed_query", new=_embed_query), patch(
        "app.llm.client.complete", new_callable=AsyncMock
    ) as m_complete, patch(
        "app.query.reranker.CohereReranker.rerank", new_callable=AsyncMock
    ) as m_rerank, patch(
        "app.api.routes.get_vector_store", return_value=mock_vs
    ), patch(
        "app.query.hybrid_search.get_vector_store", return_value=mock_vs
    ), patch(
        "app.ingestion.pipeline.get_vector_store", return_value=mock_vs
    ):
        m_embed_legacy.return_value = [[0.1] * settings.EMBEDDING_DIM]
        m_complete.return_value = "Use the corporate VPN portal to reset your password."
        m_rerank.return_value = [chunk, chunk, chunk]
        yield mock_vs, m_complete


# Provide a default ``RUN_LIVE_E2E`` env so importing the live suite works
# even without manual export.
os.environ.setdefault("RUN_LIVE_E2E", "")
