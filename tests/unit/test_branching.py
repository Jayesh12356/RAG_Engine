"""Unit tests for chat session branching helpers (Wave 2.3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def chat_db() -> AsyncIterator[async_sessionmaker]:
    from app.db.relational import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    with patch("app.db.relational.get_engine", return_value=engine), patch(
        "app.db.relational.get_session_maker", return_value=maker
    ):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield maker


@pytest.mark.asyncio
async def test_branch_session_copies_turns_up_to_anchor(chat_db: async_sessionmaker) -> None:
    """``branch_session`` should clone all turns whose timestamps are <= the
    anchor turn into a fresh session and persist a chat_sessions row recording
    the parent link."""
    from app.db.relational import (
        ChatSessionMetaModel,
        ConversationHistoryModel,
        branch_session,
    )

    parent_id = "parent-session"
    base = datetime.utcnow().replace(microsecond=0)
    turns = [
        ("t1", "user", "first?", base),
        ("t2", "assistant", "first answer", base + timedelta(seconds=1)),
        ("t3", "user", "second?", base + timedelta(seconds=2)),
        ("t4", "assistant", "second answer", base + timedelta(seconds=3)),
    ]
    async with chat_db() as session:
        for tid, role, content, created in turns:
            session.add(
                ConversationHistoryModel(
                    id=tid,
                    session_id=parent_id,
                    role=role,
                    content=content,
                    created_at=created,
                )
            )
        await session.commit()

    result = await branch_session(
        parent_session_id=parent_id,
        parent_turn_id="t2",
        new_session_id="branch-1",
        title="Forked at first answer",
    )
    assert result["session_id"] == "branch-1"
    assert result["parent_turn_id"] == "t2"
    assert result["copied_turns"] == 2

    async with chat_db() as session:
        copied = (
            await session.execute(
                select(ConversationHistoryModel).where(
                    ConversationHistoryModel.session_id == "branch-1"
                )
            )
        ).scalars().all()
        assert len(copied) == 2
        contents = sorted(r.content for r in copied)
        assert contents == ["first answer", "first?"]

        meta = (
            await session.execute(
                select(ChatSessionMetaModel).where(
                    ChatSessionMetaModel.session_id == "branch-1"
                )
            )
        ).scalar_one_or_none()
        assert meta is not None
        assert meta.parent_session_id == parent_id
        assert meta.parent_turn_id == "t2"
        assert meta.title == "Forked at first answer"


@pytest.mark.asyncio
async def test_branch_session_unknown_turn_raises(chat_db: async_sessionmaker) -> None:
    from app.db.relational import branch_session

    with pytest.raises(ValueError):
        await branch_session(
            parent_session_id="missing",
            parent_turn_id="ghost",
            new_session_id="x",
        )


@pytest.mark.asyncio
async def test_get_sessions_includes_parent_links(chat_db: async_sessionmaker) -> None:
    from app.db.relational import (
        ChatSessionMetaModel,
        ConversationHistoryModel,
        get_sessions,
    )

    base = datetime.utcnow().replace(microsecond=0)
    async with chat_db() as session:
        session.add_all(
            [
                ConversationHistoryModel(
                    id="p-u",
                    session_id="parent",
                    role="user",
                    content="hello",
                    created_at=base,
                ),
                ConversationHistoryModel(
                    id="c-u",
                    session_id="child",
                    role="user",
                    content="hello",
                    created_at=base + timedelta(seconds=1),
                ),
                ChatSessionMetaModel(
                    session_id="child",
                    parent_session_id="parent",
                    parent_turn_id="p-u",
                    title="kid",
                ),
            ]
        )
        await session.commit()

    sessions = await get_sessions()
    by_id = {s["session_id"]: s for s in sessions}
    assert by_id["child"]["parent_session_id"] == "parent"
    assert by_id["child"]["parent_turn_id"] == "p-u"
    assert by_id["child"]["title"] == "kid"
    assert by_id["parent"]["parent_session_id"] is None
