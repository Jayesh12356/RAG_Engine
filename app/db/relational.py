import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import get_settings

Base = declarative_base()

class DocumentModel(Base):
    __tablename__ = "documents"
    id = Column(String(255), primary_key=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    summary = Column(Text, nullable=True)
    # Free-form, lightly-curated tags ("Spaces") used as a Qdrant payload
    # filter and as a sidebar switcher in the UI. Stored as a JSON array of
    # strings for cross-engine portability (Postgres ARRAY would be nicer but
    # the project also targets MySQL and SQLite for tests).
    tags = Column(JSON, nullable=True)
    # Wave 3.6 — non-breaking doc versioning. Re-uploading a file with the
    # same ``filename`` increments this counter so older chunks remain
    # queryable but can be down-weighted at search time.
    version = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime, nullable=True)

class ChunkModel(Base):
    __tablename__ = "chunks"
    id = Column(String(255), primary_key=True)
    document_id = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)


class DocumentFileModel(Base):
    __tablename__ = "document_files"
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(255), ForeignKey("documents.id"), nullable=False, unique=True, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=False, default="application/pdf")
    pdf_blob = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

class ConversationHistoryModel(Base):
    __tablename__ = "conversation_history"
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    sources = Column(JSON, nullable=True)
    service_category = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())


class UserPreferenceModel(Base):
    """Per-user preference bag keyed by ``rag_engine_uid`` cookie.

    Stores bookmarks and arbitrary settings overrides as JSON. Used by
    Wave 2.7 (bookmarks sync) and Wave 2.8 (settings UI). The cookie is
    treated as opaque — there is no real auth in this build.
    """

    __tablename__ = "user_preferences"
    rag_engine_uid = Column(String(64), primary_key=True)
    bookmarks = Column(JSON, nullable=True)
    settings = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class ChatSessionMetaModel(Base):
    """Optional metadata sidecar for chat sessions.

    Most session info is derived from grouping ``conversation_history`` by
    ``session_id``. This table only stores extra fields that don't fit that
    model, currently the parent links used to render the session tree when
    a user branches from an earlier turn.
    """

    __tablename__ = "chat_sessions"
    session_id = Column(String(36), primary_key=True)
    parent_session_id = Column(String(36), nullable=True, index=True)
    parent_turn_id = Column(String(36), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())


class MetricsMinuteModel(Base):
    """One row per minute of pipeline traffic.

    Aggregating at the minute boundary keeps storage trivial (1440 rows/day)
    while giving the status page enough granularity to draw smooth p50/p95
    curves. Updated transactionally by :func:`record_pipeline_metric`.
    """

    __tablename__ = "metrics_minute"
    minute = Column(DateTime, primary_key=True)
    total = Column(Integer, nullable=False, default=0)
    refusals = Column(Integer, nullable=False, default=0)
    sum_latency_ms = Column(Float, nullable=False, default=0.0)
    sum_confidence = Column(Float, nullable=False, default=0.0)
    sum_cost_usd = Column(Float, nullable=False, default=0.0)
    # Compact reservoir of latency samples (JSON list[int] of ms values) used
    # for percentile estimation. Capped at 256 entries per minute.
    latency_samples = Column(JSON, nullable=True)


class WebhookSubscriptionModel(Base):
    """Process-wide webhook subscription (Wave 3.5).

    Webhooks fire on three events: ``ingestion.complete``, ``query.completed``,
    and ``query.refused``. Each row is a single subscription — multiple rows
    can listen to the same event. Configurable via ``/webhooks`` endpoints
    and the Settings UI; powered by ``app/observability/webhooks.py``.

    The optional ``secret`` is sent as a ``X-Helpdesk-Signature`` HMAC-SHA256
    header so the receiver can verify authenticity.
    """

    __tablename__ = "webhook_subscriptions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event = Column(String(64), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    enabled = Column(Integer, nullable=False, default=1)
    secret = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class IngestionTaskModel(Base):
    """Per-upload progress record for the async ingestion path.

    Inserted at task creation, updated by ``IngestPipeline.run`` as it
    advances through stages, polled by ``GET /ingest/{task_id}/status``
    and streamed by ``GET /ingest/{task_id}/events``.
    """

    __tablename__ = "ingestion_tasks"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(255), nullable=True, index=True)
    filename = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    stage = Column(String(64), nullable=False, default="queued")
    progress = Column(Integer, nullable=False, default=0)
    total_chunks = Column(Integer, nullable=False, default=0)
    processed_chunks = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


async def create_ingestion_task(task_id: str, filename: str) -> str:
    """Insert a fresh ``ingestion_tasks`` row in the ``queued`` state."""
    async with get_session_maker()() as session:
        row = IngestionTaskModel(
            id=task_id,
            filename=filename,
            status="queued",
            stage="queued",
            progress=0,
        )
        session.add(row)
        await session.commit()
    return task_id


async def update_ingestion_task(
    task_id: str,
    *,
    stage: str | None = None,
    status: str | None = None,
    progress: int | None = None,
    document_id: str | None = None,
    total_chunks: int | None = None,
    processed_chunks: int | None = None,
    message: str | None = None,
    error: str | None = None,
) -> None:
    """Patch the task row. Silently no-ops when the row is missing."""
    async with get_session_maker()() as session:
        stmt = select(IngestionTaskModel).where(IngestionTaskModel.id == task_id)
        res = await session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return
        if stage is not None:
            row.stage = stage
        if status is not None:
            row.status = status
        if progress is not None:
            row.progress = max(0, min(100, int(progress)))
        if document_id is not None:
            row.document_id = document_id
        if total_chunks is not None:
            row.total_chunks = int(total_chunks)
        if processed_chunks is not None:
            row.processed_chunks = int(processed_chunks)
        if message is not None:
            row.message = message
        if error is not None:
            row.error = error
        row.updated_at = datetime.utcnow()
        await session.commit()


async def get_ingestion_task(task_id: str) -> dict | None:
    """Fetch a task row as a serialisable dict, or ``None`` when missing."""
    async with get_session_maker()() as session:
        stmt = select(IngestionTaskModel).where(IngestionTaskModel.id == task_id)
        res = await session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        return {
            "task_id": row.id,
            "document_id": row.document_id,
            "filename": row.filename,
            "status": row.status,
            "stage": row.stage,
            "progress": row.progress,
            "total_chunks": row.total_chunks,
            "processed_chunks": row.processed_chunks,
            "message": row.message,
            "error": row.error,
            "started_at": row.started_at.isoformat() if row.started_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

async def insert_turn(session_id: str, role: str, content: str, question: str = None, answer: str = None, 
                      confidence: float = None, sources: list = None, service_category: str = None) -> str:
    turn_id = str(uuid.uuid4())
    async with get_session_maker()() as session:
        turn = ConversationHistoryModel(
            id=turn_id,
            session_id=session_id,
            role=role,
            content=content,
            question=question,
            answer=answer,
            confidence=confidence,
            sources=sources,
            service_category=service_category
        )
        session.add(turn)
        await session.commit()
    return turn_id

async def get_history(session_id: str, limit: int = 50) -> list[dict]:
    async with get_session_maker()() as session:
        stmt = select(ConversationHistoryModel)\
            .where(ConversationHistoryModel.session_id == session_id)\
            .order_by(ConversationHistoryModel.created_at.desc())\
            .limit(limit)
        result = await session.execute(stmt)
        turns = result.scalars().all()
        
        history = []
        for t in reversed(turns):
            history.append({
                "id": t.id,
                "session_id": t.session_id,
                "role": t.role,
                "content": t.content,
                "confidence": t.confidence,
                "service_category": t.service_category,
                "sources": t.sources or [],
                "created_at": t.created_at.isoformat() if t.created_at else ""
            })
        return history

async def get_sessions() -> list[dict]:
    async with get_session_maker()() as session:
        # Get count and latest activity per session
        stmt = select(
            ConversationHistoryModel.session_id,
            func.count(ConversationHistoryModel.id).label("turn_count"),
            func.max(ConversationHistoryModel.created_at).label("last_active")
        ).group_by(ConversationHistoryModel.session_id).order_by(func.max(ConversationHistoryModel.created_at).desc())
        
        result = await session.execute(stmt)
        sessions_aggs = result.all()

        meta_stmt = select(
            ChatSessionMetaModel.session_id,
            ChatSessionMetaModel.parent_session_id,
            ChatSessionMetaModel.parent_turn_id,
            ChatSessionMetaModel.title,
        )
        meta_rows = (await session.execute(meta_stmt)).all()
        meta_by_id: dict[str, dict] = {}
        for row in meta_rows:
            meta_by_id[row.session_id] = {
                "parent_session_id": row.parent_session_id,
                "parent_turn_id": row.parent_turn_id,
                "title": row.title,
            }
        
        sessions = []
        for s in sessions_aggs:
            # get the first question
            first_q_stmt = select(ConversationHistoryModel.content)\
                .where(ConversationHistoryModel.session_id == s.session_id, ConversationHistoryModel.role == "user")\
                .order_by(ConversationHistoryModel.created_at.asc())\
                .limit(1)
            first_q_res = await session.execute(first_q_stmt)
            first_q = first_q_res.scalar_one_or_none()
            meta = meta_by_id.get(s.session_id, {})

            sessions.append({
                "session_id": s.session_id,
                "turn_count": s.turn_count,
                "last_active": s.last_active.isoformat() if s.last_active else "",
                "first_question": first_q or "",
                "parent_session_id": meta.get("parent_session_id"),
                "parent_turn_id": meta.get("parent_turn_id"),
                "title": meta.get("title"),
            })
        return sessions

async def delete_session(session_id: str) -> int:
    async with get_session_maker()() as session:
        stmt = delete(ConversationHistoryModel).where(ConversationHistoryModel.session_id == session_id)
        result = await session.execute(stmt)
        await session.execute(
            delete(ChatSessionMetaModel).where(ChatSessionMetaModel.session_id == session_id)
        )
        await session.commit()
        return result.rowcount


async def branch_session(
    *,
    parent_session_id: str,
    parent_turn_id: str,
    new_session_id: str | None = None,
    title: str | None = None,
) -> dict:
    """Fork a chat session at ``parent_turn_id``.

    Copies conversation rows whose ``created_at`` is <= the parent turn's
    ``created_at`` (and whose ids are <= the parent turn id when timestamps
    tie) into a new session, and records the parent link.
    """

    new_id = new_session_id or str(uuid.uuid4())
    async with get_session_maker()() as session:
        anchor_stmt = select(ConversationHistoryModel).where(
            ConversationHistoryModel.id == parent_turn_id,
            ConversationHistoryModel.session_id == parent_session_id,
        )
        anchor = (await session.execute(anchor_stmt)).scalar_one_or_none()
        if anchor is None:
            raise ValueError("parent_turn_id not found in parent_session_id")

        # Pull all turns up to and including the anchor.
        turns_stmt = (
            select(ConversationHistoryModel)
            .where(ConversationHistoryModel.session_id == parent_session_id)
            .where(ConversationHistoryModel.created_at <= anchor.created_at)
            .order_by(ConversationHistoryModel.created_at.asc(), ConversationHistoryModel.id.asc())
        )
        rows = (await session.execute(turns_stmt)).scalars().all()

        copied = 0
        for row in rows:
            session.add(
                ConversationHistoryModel(
                    id=str(uuid.uuid4()),
                    session_id=new_id,
                    role=row.role,
                    content=row.content,
                    question=row.question,
                    answer=row.answer,
                    confidence=row.confidence,
                    sources=row.sources,
                    service_category=row.service_category,
                    created_at=row.created_at,
                )
            )
            copied += 1
            if row.id == parent_turn_id:
                break

        session.add(
            ChatSessionMetaModel(
                session_id=new_id,
                parent_session_id=parent_session_id,
                parent_turn_id=parent_turn_id,
                title=title,
            )
        )
        await session.commit()

        return {
            "session_id": new_id,
            "parent_session_id": parent_session_id,
            "parent_turn_id": parent_turn_id,
            "copied_turns": copied,
            "title": title,
        }

async def get_user_preferences(rag_engine_uid: str) -> dict:
    """Return ``{bookmarks, settings}`` for a uid, defaulting to empty values."""
    async with get_session_maker()() as session:
        stmt = select(UserPreferenceModel).where(
            UserPreferenceModel.rag_engine_uid == rag_engine_uid
        )
        res = await session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return {"rag_engine_uid": rag_engine_uid, "bookmarks": [], "settings": {}}
        return {
            "rag_engine_uid": row.rag_engine_uid,
            "bookmarks": row.bookmarks or [],
            "settings": row.settings or {},
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


async def upsert_user_preferences(
    rag_engine_uid: str,
    *,
    bookmarks: list | None = None,
    settings_overrides: dict | None = None,
) -> dict:
    """Insert or merge a ``user_preferences`` row.

    ``None`` arguments leave the existing column untouched. Returns the
    persisted state for the caller to echo back.
    """
    async with get_session_maker()() as session:
        stmt = select(UserPreferenceModel).where(
            UserPreferenceModel.rag_engine_uid == rag_engine_uid
        )
        res = await session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            row = UserPreferenceModel(
                rag_engine_uid=rag_engine_uid,
                bookmarks=bookmarks if bookmarks is not None else [],
                settings=settings_overrides if settings_overrides is not None else {},
            )
            session.add(row)
        else:
            if bookmarks is not None:
                row.bookmarks = bookmarks
            if settings_overrides is not None:
                row.settings = settings_overrides
            row.updated_at = datetime.utcnow()
        await session.commit()
        return {
            "rag_engine_uid": rag_engine_uid,
            "bookmarks": row.bookmarks or [],
            "settings": row.settings or {},
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


# ── Tag helpers (Wave 2.9 — Spaces) ─────────────────────────────────────────
_MAX_TAGS_PER_DOC = 16
_MAX_TAG_LEN = 32


def _normalise_tags(raw: list[str] | None) -> list[str]:
    """Strip, dedupe (case-insensitive), and cap a tag list."""
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()[:_MAX_TAG_LEN]
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= _MAX_TAGS_PER_DOC:
            break
    return out


async def set_document_tags(document_id: str, tags: list[str]) -> list[str] | None:
    """Replace tags on a document. Returns ``None`` when the doc is missing."""
    cleaned = _normalise_tags(tags)
    async with get_session_maker()() as session:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        res = await session.execute(stmt)
        doc = res.scalar_one_or_none()
        if doc is None:
            return None
        doc.tags = cleaned
        await session.commit()
    return cleaned


async def list_all_tags() -> list[str]:
    """Aggregate every tag across the corpus, sorted by descending frequency."""
    async with get_session_maker()() as session:
        stmt = select(DocumentModel.tags)
        res = await session.execute(stmt)
        counts: dict[str, int] = {}
        for (tags,) in res.all():
            if not tags:
                continue
            for t in tags:
                if not isinstance(t, str):
                    continue
                counts[t] = counts.get(t, 0) + 1
        return sorted(counts.keys(), key=lambda k: (-counts[k], k.lower()))


# ── Metrics helpers ─────────────────────────────────────────────────────────
def _truncate_to_minute(ts: datetime | None) -> datetime:
    now = ts or datetime.utcnow()
    return now.replace(second=0, microsecond=0)


async def record_pipeline_metric(
    *,
    latency_ms: float,
    refused: bool,
    confidence: float | None = None,
    cost_usd: float | None = None,
) -> None:
    """Upsert a one-minute aggregate row in ``metrics_minute``.

    Failures are swallowed — observability must never block the pipeline.
    The reservoir of latency samples is capped per-minute so even bursty
    traffic stays bounded.
    """
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: F401
    except Exception:
        pg_insert = None  # type: ignore[assignment]

    minute = _truncate_to_minute(None)
    sample_int = int(max(0.0, latency_ms))
    confidence_value = float(confidence) if confidence is not None else 0.0
    cost_value = float(cost_usd) if cost_usd is not None else 0.0

    try:
        async with get_session_maker()() as session:
            existing = await session.get(MetricsMinuteModel, minute)
            if existing is None:
                row = MetricsMinuteModel(
                    minute=minute,
                    total=1,
                    refusals=1 if refused else 0,
                    sum_latency_ms=float(latency_ms),
                    sum_confidence=confidence_value,
                    sum_cost_usd=cost_value,
                    latency_samples=[sample_int],
                )
                session.add(row)
            else:
                existing.total = (existing.total or 0) + 1
                if refused:
                    existing.refusals = (existing.refusals or 0) + 1
                existing.sum_latency_ms = (existing.sum_latency_ms or 0.0) + float(latency_ms)
                existing.sum_confidence = (existing.sum_confidence or 0.0) + confidence_value
                existing.sum_cost_usd = (existing.sum_cost_usd or 0.0) + cost_value
                samples = list(existing.latency_samples or [])
                samples.append(sample_int)
                if len(samples) > 256:
                    samples = samples[-256:]
                existing.latency_samples = samples
            await session.commit()
    except Exception:
        # Metrics persistence must never bring down the pipeline.
        pass


def _percentile(samples: list[int], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * frac)


async def recent_metrics(minutes: int = 60) -> list[dict]:
    """Return up to ``minutes`` rows ending at the current minute."""
    minutes = max(1, min(minutes, 1440))
    async with get_session_maker()() as session:
        stmt = (
            select(MetricsMinuteModel)
            .order_by(MetricsMinuteModel.minute.desc())
            .limit(minutes)
        )
        rows = (await session.execute(stmt)).scalars().all()
    out: list[dict] = []
    for row in rows:
        samples = list(row.latency_samples or [])
        total = int(row.total or 0)
        out.append(
            {
                "minute": row.minute.replace(microsecond=0).isoformat() + "Z",
                "total": total,
                "refusals": int(row.refusals or 0),
                "p50_ms": _percentile(samples, 50),
                "p95_ms": _percentile(samples, 95),
                "mean_confidence": (row.sum_confidence or 0.0) / total if total else 0.0,
                "cost_usd": float(row.sum_cost_usd or 0.0),
            }
        )
    out.reverse()
    return out


# ── Webhook subscription helpers ────────────────────────────────────────────
WEBHOOK_EVENTS: tuple[str, ...] = (
    "ingestion.complete",
    "query.completed",
    "query.refused",
)


async def list_webhooks(event: str | None = None) -> list[dict]:
    """Return all configured webhook subscriptions, newest first.

    When ``event`` is supplied only enabled subscriptions for that event are
    returned, suitable for the dispatch hot path. Without filters, every row
    (including disabled) is returned for the management UI.
    """
    async with get_session_maker()() as session:
        stmt = select(WebhookSubscriptionModel).order_by(
            WebhookSubscriptionModel.created_at.desc()
        )
        if event:
            stmt = stmt.where(
                WebhookSubscriptionModel.event == event,
                WebhookSubscriptionModel.enabled == 1,
            )
        rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": row.id,
            "event": row.event,
            "url": row.url,
            "enabled": bool(row.enabled),
            "secret": row.secret,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


async def create_webhook(
    *,
    event: str,
    url: str,
    enabled: bool = True,
    secret: str | None = None,
) -> dict:
    """Insert a new webhook subscription row and return it."""
    if event not in WEBHOOK_EVENTS:
        raise ValueError(f"unknown event: {event!r}")
    async with get_session_maker()() as session:
        row = WebhookSubscriptionModel(
            id=str(uuid.uuid4()),
            event=event,
            url=url,
            enabled=1 if enabled else 0,
            secret=secret,
        )
        session.add(row)
        await session.commit()
        return {
            "id": row.id,
            "event": row.event,
            "url": row.url,
            "enabled": bool(row.enabled),
            "secret": row.secret,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


async def delete_webhook(webhook_id: str) -> bool:
    """Remove a webhook subscription. Returns True when a row was deleted."""
    async with get_session_maker()() as session:
        stmt = delete(WebhookSubscriptionModel).where(
            WebhookSubscriptionModel.id == webhook_id
        )
        res = await session.execute(stmt)
        await session.commit()
        return (res.rowcount or 0) > 0


async def update_webhook(
    webhook_id: str,
    *,
    enabled: bool | None = None,
    url: str | None = None,
    secret: str | None = None,
) -> dict | None:
    """Patch a subscription. ``None`` arguments leave the column untouched."""
    async with get_session_maker()() as session:
        row = await session.get(WebhookSubscriptionModel, webhook_id)
        if row is None:
            return None
        if enabled is not None:
            row.enabled = 1 if enabled else 0
        if url is not None:
            row.url = url
        if secret is not None:
            row.secret = secret or None
        row.updated_at = datetime.utcnow()
        await session.commit()
        return {
            "id": row.id,
            "event": row.event,
            "url": row.url,
            "enabled": bool(row.enabled),
            "secret": row.secret,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


def get_engine():
    settings = get_settings()
    connect_args = {}
    if settings.relational_url.startswith("postgresql+asyncpg://"):
        connect_args = {"server_settings": {"search_path": settings.db_schema}}
    return create_async_engine(settings.relational_url, echo=False, connect_args=connect_args)

def _existing_columns(sync_conn, table: str) -> set[str]:
    """Return the lowercase column names already present on ``table``."""
    from sqlalchemy import inspect as _inspect

    try:
        cols = _inspect(sync_conn).get_columns(table)
    except Exception:
        return set()
    return {c["name"].lower() for c in cols}


def _apply_lightweight_migrations(sync_conn) -> None:
    """Add columns that newer code expects but older databases may lack.

    Keep this list small and idempotent — anything fancier should be a
    proper migration. The pattern is: introspect, then ``ALTER TABLE`` only
    when the column is missing, so re-running is a no-op.

    The additions cover every column we have introduced after the initial
    ``documents`` schema so old prod databases pick them up without manual
    intervention. Type names are deliberately neutral (``TEXT`` /
    ``INTEGER``) so they parse on Postgres, MySQL and SQLite.
    """
    additions: list[tuple[str, str, str]] = [
        ("documents", "summary", "TEXT"),
        ("documents", "tags", "TEXT"),
        ("documents", "version", "INTEGER"),
        ("chat_sessions", "title", "TEXT"),
        ("chat_sessions", "parent_session_id", "TEXT"),
        ("chat_sessions", "parent_turn_id", "TEXT"),
    ]
    for table, column, ddl in additions:
        try:
            existing = _existing_columns(sync_conn, table)
        except Exception:
            continue
        if not existing:
            # Table doesn't exist yet — ``create_all`` already ran, so this
            # only happens if the table is genuinely missing; skip rather
            # than emit an ALTER that would fail.
            continue
        if column.lower() in existing:
            continue
        try:
            sync_conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
            )
        except Exception:
            # Best-effort: another worker likely won the race, or the
            # backend rejected the DDL (e.g. permissions). The application
            # will keep functioning because reads default the column to
            # NULL / 1.
            pass


async def init_db():
    settings = get_settings()
    engine = get_engine()
    async with engine.begin() as conn:
        if settings.relational_url.startswith("postgresql+asyncpg://"):
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"'))
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_lightweight_migrations)

def get_session_maker():
    engine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
