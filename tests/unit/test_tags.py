"""Tests for the Spaces / tags layer (Wave 2.9)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def tags_db() -> AsyncIterator[None]:
    from app.db.relational import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    with patch("app.db.relational.get_engine", return_value=engine), patch(
        "app.db.relational.get_session_maker", return_value=maker
    ):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield


def test_normalise_tags_strips_dedupes_caps() -> None:
    from app.db.relational import _normalise_tags

    cleaned = _normalise_tags(["  Legal ", "legal", "Q3", "", None, "Q3", "ProductOps"])  # type: ignore[list-item]
    # strip + dedupe (case-insensitive) preserves first form
    assert cleaned == ["Legal", "Q3", "ProductOps"]

    # truncates over-length tags + caps the list
    long_tags = [f"tag-{i}" for i in range(50)]
    capped = _normalise_tags(long_tags)
    assert len(capped) <= 16


@pytest.mark.asyncio
async def test_set_tags_round_trip(tags_db) -> None:
    from app.db.relational import (
        DocumentModel,
        get_session_maker,
        list_all_tags,
        set_document_tags,
    )

    async with get_session_maker()() as session:
        session.add(
            DocumentModel(id="d1", filename="a.pdf", content="...", metadata_={})
        )
        session.add(
            DocumentModel(id="d2", filename="b.pdf", content="...", metadata_={})
        )
        await session.commit()

    out = await set_document_tags("d1", ["Legal", "Finance", "legal"])  # dedupes
    assert out == ["Legal", "Finance"]

    await set_document_tags("d2", ["Finance", "ProductOps"])

    tags_sorted = await list_all_tags()
    assert tags_sorted[0] == "Finance"  # most frequent first
    assert set(tags_sorted) == {"Legal", "Finance", "ProductOps"}


@pytest.mark.asyncio
async def test_set_tags_missing_doc_returns_none(tags_db) -> None:
    from app.db.relational import set_document_tags

    assert await set_document_tags("nope", ["Legal"]) is None


def test_qdrant_filter_passthrough_for_tags() -> None:
    pytest.importorskip("qdrant_client")
    from qdrant_client.http.models import Filter

    from app.db.vector_store import QdrantVectorStore

    # Avoid the real ``__init__`` (would open a network client). Build a bare
    # instance just to exercise ``_build_filter``.
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    f = store._build_filter({"tags": {"$in": ["Legal", "Finance"]}})
    assert isinstance(f, Filter)
    # MatchAny → must contain both values in its any[] payload.
    must = f.must or []
    assert any(getattr(c.match, "any", None) == ["Legal", "Finance"] for c in must)


def test_qdrant_filter_combines_tags_with_simple_match() -> None:
    pytest.importorskip("qdrant_client")

    from app.db.vector_store import QdrantVectorStore

    store = QdrantVectorStore.__new__(QdrantVectorStore)
    f = store._build_filter(
        {"service_name": "VPN", "tags": {"$in": ["Legal"]}}
    )
    must = f.must or []
    keys = [c.key for c in must]
    assert set(keys) == {"service_name", "tags"}
