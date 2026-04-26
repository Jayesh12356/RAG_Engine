"""Unit tests for the user_preferences sync layer (Wave 2.7 / 2.8)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def prefs_db() -> AsyncIterator[None]:
    from app.db.relational import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    with patch("app.db.relational.get_engine", return_value=engine), patch(
        "app.db.relational.get_session_maker", return_value=maker
    ):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield


@pytest.mark.asyncio
async def test_get_returns_empty_defaults(prefs_db) -> None:
    from app.db.relational import get_user_preferences

    data = await get_user_preferences("alice")
    assert data["rag_engine_uid"] == "alice"
    assert data["bookmarks"] == []
    assert data["settings"] == {}


@pytest.mark.asyncio
async def test_upsert_and_round_trip(prefs_db) -> None:
    from app.db.relational import get_user_preferences, upsert_user_preferences

    saved = await upsert_user_preferences(
        "bob",
        bookmarks=[{"id": "t1", "question": "hi"}],
        settings_overrides={"theme": "dark"},
    )
    assert saved["bookmarks"] == [{"id": "t1", "question": "hi"}]
    assert saved["settings"] == {"theme": "dark"}

    again = await get_user_preferences("bob")
    assert again["bookmarks"] == [{"id": "t1", "question": "hi"}]
    assert again["settings"] == {"theme": "dark"}


@pytest.mark.asyncio
async def test_upsert_partial_keeps_other_columns(prefs_db) -> None:
    from app.db.relational import upsert_user_preferences

    await upsert_user_preferences(
        "carol",
        bookmarks=[{"id": "x", "question": "y"}],
        settings_overrides={"locale": "en-US"},
    )
    # Patch only settings — bookmarks should remain.
    after = await upsert_user_preferences("carol", settings_overrides={"locale": "fr-FR"})
    assert after["settings"] == {"locale": "fr-FR"}
    assert after["bookmarks"] == [{"id": "x", "question": "y"}]
