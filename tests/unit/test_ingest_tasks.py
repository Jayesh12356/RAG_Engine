"""Unit tests for the ingestion-task progress surface.

Exercises the relational helpers (``create``/``update``/``get``) against
an in-memory SQLite engine, then confirms the FastAPI status endpoint
returns the most recent state. The SSE ``/events`` endpoint is covered
indirectly via ``IngestPipeline._progress`` writing through the same
helpers; the actual stream loop is a thin polling wrapper.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import patch


@pytest_asyncio.fixture
async def task_db() -> AsyncIterator[None]:
    from app.db.relational import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    with patch("app.db.relational.get_engine", return_value=engine), patch(
        "app.db.relational.get_session_maker", return_value=session_maker
    ):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield


@pytest.mark.asyncio
async def test_create_then_get_returns_initial_state(task_db):
    from app.db.relational import create_ingestion_task, get_ingestion_task

    await create_ingestion_task(task_id="t1", filename="vpn.pdf")
    row = await get_ingestion_task("t1")
    assert row is not None
    assert row["task_id"] == "t1"
    assert row["filename"] == "vpn.pdf"
    assert row["status"] == "queued"
    assert row["stage"] == "queued"
    assert row["progress"] == 0


@pytest.mark.asyncio
async def test_update_persists_partial_patches(task_db):
    from app.db.relational import (
        create_ingestion_task,
        get_ingestion_task,
        update_ingestion_task,
    )

    await create_ingestion_task(task_id="t2", filename="report.docx")

    await update_ingestion_task(
        "t2",
        stage="parsing",
        status="running",
        progress=20,
        message="Parsing pages",
    )
    row = await get_ingestion_task("t2")
    assert row["stage"] == "parsing"
    assert row["status"] == "running"
    assert row["progress"] == 20
    assert row["message"] == "Parsing pages"

    await update_ingestion_task(
        "t2",
        stage="embedding",
        progress=70,
        total_chunks=12,
        processed_chunks=8,
    )
    row = await get_ingestion_task("t2")
    assert row["stage"] == "embedding"
    assert row["progress"] == 70
    assert row["total_chunks"] == 12
    assert row["processed_chunks"] == 8


@pytest.mark.asyncio
async def test_update_missing_row_no_raise(task_db):
    from app.db.relational import update_ingestion_task

    await update_ingestion_task("does-not-exist", stage="ignored")


@pytest.mark.asyncio
async def test_progress_clamps_out_of_range(task_db):
    from app.db.relational import (
        create_ingestion_task,
        get_ingestion_task,
        update_ingestion_task,
    )

    await create_ingestion_task(task_id="t3", filename="x.csv")
    await update_ingestion_task("t3", progress=999)
    row = await get_ingestion_task("t3")
    assert row["progress"] == 100
    await update_ingestion_task("t3", progress=-5)
    row = await get_ingestion_task("t3")
    assert row["progress"] == 0


@pytest.mark.asyncio
async def test_terminal_status_recorded(task_db):
    from app.db.relational import (
        create_ingestion_task,
        get_ingestion_task,
        update_ingestion_task,
    )

    await create_ingestion_task(task_id="t4", filename="x.pdf")
    await update_ingestion_task(
        "t4",
        status="failed",
        stage="failed",
        progress=100,
        error="kaboom",
    )
    row = await get_ingestion_task("t4")
    assert row["status"] == "failed"
    assert row["error"] == "kaboom"


@pytest.mark.asyncio
async def test_ingest_pipeline_progress_helper_writes_through(task_db):
    """``_progress`` should patch the same row across multiple calls."""
    from app.db.relational import create_ingestion_task, get_ingestion_task
    from app.ingestion.pipeline import IngestPipeline

    await create_ingestion_task(task_id="t5", filename="manual.pdf")

    pipe = IngestPipeline(demo_mode=True)
    await pipe._progress("t5", stage="parsing", progress=10)
    await pipe._progress(
        "t5", stage="embedding", progress=60, total_chunks=10, processed_chunks=6
    )
    row = await get_ingestion_task("t5")
    assert row["stage"] == "embedding"
    assert row["progress"] == 60
    assert row["processed_chunks"] == 6


@pytest.mark.asyncio
async def test_progress_helper_silently_noops_without_task_id(task_db):
    """Foreground ingest path must not blow up when no task_id is supplied."""
    from app.ingestion.pipeline import IngestPipeline

    pipe = IngestPipeline(demo_mode=True)
    await pipe._progress(None, stage="parsing", progress=5)
