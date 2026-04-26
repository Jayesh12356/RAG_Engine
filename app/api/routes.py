import asyncio
import json
import os
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import delete, select

from app.api.rate_limit import enforce_chat_or_query_limit

from app.api.models import (
    BranchSessionRequest,
    BranchSessionResponse,
    ChunkListResponse,
    DeleteResponse,
    DeleteSessionResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentTagsRequest,
    DocumentTagsResponse,
    HealthResponse,
    HistoryResponse,
    IngestResponse,
    IngestTaskStatusResponse,
    LogEntryItem,
    MetricsRecentItem,
    MetricsRecentResponse,
    QueryAPIRequest,
    RecentLogsResponse,
    SessionListResponse,
    SessionSummary,
    SettingsSchemaField,
    SettingsSchemaResponse,
    TagsListResponse,
    UserPreferencesResponse,
    UserPreferencesUpdate,
    WebhookCreateRequest,
    WebhookListResponse,
    WebhookSubscriptionItem,
    WebhookUpdateRequest,
)
from app.chat.pipeline import ChatPipeline, ChatRequest, ChatResponse
from app.chat.session import SessionManager
from app.config import get_settings
from app.db.relational import (
    ChunkModel,
    DocumentModel,
    create_ingestion_task,
    get_ingestion_task,
    get_session_maker,
)
from app.db.vector_store import get_vector_store
from app.ingestion.pipeline import IngestPipeline
from app.ingestion.router import is_supported, supported_extensions_human
from app.models.query import QueryRequest
from app.query.cache import bump_corpus_version
from app.query.pipeline import QueryPipeline
from app.storage.pdf_storage import get_pdf_storage

logger = structlog.get_logger(__name__)
router = APIRouter()
settings = get_settings()

session_maker = get_session_maker()

def get_demo_mode(x_demo_mode: str | None = Header(None)) -> bool:
    if x_demo_mode is not None:
        return x_demo_mode.lower() == "true"
    return settings.DEMO_MODE


def _read_uid_from_cookie(cookie_header: str | None) -> str | None:
    """Pull ``rag_engine_uid`` out of a raw ``Cookie:`` header."""
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == "rag_engine_uid" and value:
            return value
    return None

@router.get("/health", response_model=HealthResponse)
async def health_check(x_demo_mode: str | None = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)

    from app.api.models import HealthDbPoolStats
    from app.observability.runtime import (
        db_pool_stats,
        ingestion_queue_depth,
        process_uptime_seconds,
        vector_index_size,
    )

    pool_raw = db_pool_stats() if not demo_mode else None
    pool_model = HealthDbPoolStats(**pool_raw) if pool_raw else None

    vector_size: int | None = None
    queue_depth: int | None = None
    if not demo_mode:
        try:
            vector_size = await vector_index_size()
        except Exception:
            vector_size = None
        try:
            queue_depth = await ingestion_queue_depth()
        except Exception:
            queue_depth = None

    return HealthResponse(
        status="ok",
        llm_provider=settings.LLM_PROVIDER,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        vector_db=settings.VECTOR_DB,
        relational_db=settings.RELATIONAL_DB,
        demo_mode=demo_mode,
        visual_capable=settings.llm_is_visual_capable,
        image_gen_active=settings.image_gen_active,
        uptime_seconds=process_uptime_seconds(),
        db_pool=pool_model,
        vector_index_size=vector_size,
        queue_depth=queue_depth,
    )

async def run_ingest_and_cleanup(
    tmp_path: str,
    demo_mode: bool,
    service_name_override: str | None,
    content: bytes,
    content_type: str,
    task_id: str | None = None,
    original_filename: str | None = None,
):
    try:
        pipeline = IngestPipeline(demo_mode=demo_mode)
        await pipeline.run(
            tmp_path,
            service_name_override,
            pdf_bytes=content,
            content_type=content_type,
            task_id=task_id,
            original_filename=original_filename,
        )
    except Exception as e:
        logger.error("background_ingest_error", error=str(e), path=tmp_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.error("cleanup_tmp_file_error", error=str(e), path=tmp_path)

@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    service_name_override: str | None = Form(None),
    background: bool = Form(False),
    x_demo_mode: str | None = Header(None)
):
    demo_mode = get_demo_mode(x_demo_mode)

    if not file.filename or not is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {supported_extensions_human()}",
        )

    os.makedirs("/tmp", exist_ok=True)
    task_id = str(uuid.uuid4())
    tmp_path = f"/tmp/{task_id}_{file.filename}"

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}") from e

    if background:
        try:
            await create_ingestion_task(task_id=task_id, filename=file.filename)
        except Exception as exc:
            logger.warning("ingest_task_create_failed", error=str(exc))
        background_tasks.add_task(
            run_ingest_and_cleanup,
            tmp_path,
            demo_mode,
            service_name_override,
            content,
            file.content_type or "application/octet-stream",
            task_id,
            file.filename,
        )
        return IngestResponse(
            status="processing",
            task_id=task_id
        )
    else:
        try:
            pipeline = IngestPipeline(demo_mode=demo_mode)
            result = await pipeline.run(
                tmp_path,
                service_name_override,
                pdf_bytes=content,
                content_type=file.content_type or "application/octet-stream",
                original_filename=file.filename,
            )
            return IngestResponse(
                document_id=result.document_id,
                pdf_name=result.pdf_name,
                total_pages=result.total_pages,
                total_chunks=result.total_chunks,
                service_name=result.service_name,
                status=result.status,
                error=result.error
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

@router.get(
    "/ingest/{task_id}/status",
    response_model=IngestTaskStatusResponse,
)
async def get_ingest_status(task_id: str):
    """Snapshot of an in-flight (or finished) background ingest task."""
    task = await get_ingestion_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Ingest task not found")
    return IngestTaskStatusResponse(**task)


@router.get("/ingest/{task_id}/events")
async def stream_ingest_events(task_id: str):
    """SSE stream of progress patches until the task reaches a terminal state."""
    initial = await get_ingestion_task(task_id)
    if initial is None:
        raise HTTPException(status_code=404, detail="Ingest task not found")

    async def gen():
        last_payload = ""
        terminal = {"complete", "failed"}
        deadline = asyncio.get_event_loop().time() + 600
        while True:
            task = await get_ingestion_task(task_id)
            if task is None:
                yield 'data: {"type":"error","message":"Task disappeared"}\n\n'
                return
            payload = json.dumps({"type": "progress", **task})
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if task.get("status") in terminal:
                yield f"data: {json.dumps({'type': 'final', **task})}\n\n"
                return
            if asyncio.get_event_loop().time() > deadline:
                yield 'data: {"type":"error","message":"timeout"}\n\n'
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/query", dependencies=[Depends(enforce_chat_or_query_limit)])
async def query_pipeline(
    request: QueryAPIRequest,
    x_demo_mode: str | None = Header(None)
):
    demo_mode = get_demo_mode(x_demo_mode)
    
    q_req = QueryRequest(
        question=request.question,
        service_category=request.service_category,
        top_k=request.top_k,
        rerank_top_n=request.rerank_top_n,
        include_citations=request.include_citations,
        tags=request.tags or [],
    )
    
    pipeline = QueryPipeline(demo_mode=demo_mode)
    response = await pipeline.run(q_req)
    return response


@router.post("/query/stream", dependencies=[Depends(enforce_chat_or_query_limit)])
async def query_pipeline_stream(
    request: QueryAPIRequest,
    x_demo_mode: str | None = Header(None)
):
    demo_mode = get_demo_mode(x_demo_mode)
    q_req = QueryRequest(
        question=request.question,
        service_category=request.service_category,
        top_k=request.top_k,
        rerank_top_n=request.rerank_top_n,
        include_citations=request.include_citations,
        tags=request.tags or [],
    )
    pipeline = QueryPipeline(demo_mode=demo_mode)
    return StreamingResponse(
        pipeline.run_stream(q_req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(enforce_chat_or_query_limit)],
)
async def chat_endpoint(request: ChatRequest, x_demo_mode: str | None = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    pipeline = ChatPipeline(demo_mode=demo_mode)
    return await pipeline.run(request)


@router.post("/chat/stream", dependencies=[Depends(enforce_chat_or_query_limit)])
async def chat_stream_endpoint(request: ChatRequest, x_demo_mode: str | None = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    pipeline = ChatPipeline(demo_mode=demo_mode)
    return StreamingResponse(
        pipeline.run_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@router.get("/chat/{session_id}/history", response_model=HistoryResponse)
async def get_chat_history(session_id: str, limit: int = 50, x_demo_mode: str | None = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    manager = SessionManager(demo_mode=demo_mode)
    turns = await manager.get_history(session_id, limit=limit)
    if not turns and demo_mode:
        if session_id not in manager._memory_store:
            raise HTTPException(status_code=404, detail="Session not found")
    elif not turns and not demo_mode:
        from sqlalchemy import select

        from app.db.relational import ConversationHistoryModel, get_session_maker
        async with get_session_maker()() as session:
            stmt = select(ConversationHistoryModel.id).where(ConversationHistoryModel.session_id == session_id).limit(1)
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Session not found")
    return HistoryResponse(session_id=session_id, turns=TurnsToDicts(turns), total=len(turns))

def TurnsToDicts(turns) -> list:
    return [t.model_dump() for t in turns]

@router.delete("/chat/{session_id}", response_model=DeleteSessionResponse)
async def delete_chat_session(session_id: str, x_demo_mode: str | None = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    if demo_mode:
        manager = SessionManager(demo_mode=demo_mode)
        if session_id in manager._memory_store:
            removed = len(manager._memory_store[session_id])
            del manager._memory_store[session_id]
        else:
            removed = 0
    else:
        from app.db.relational import delete_session
        removed = await delete_session(session_id)
        
    return DeleteSessionResponse(session_id=session_id, status="deleted", turns_removed=removed)

@router.get("/chat/sessions", response_model=SessionListResponse)
async def get_chat_sessions(x_demo_mode: str | None = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    if demo_mode:
        manager = SessionManager(demo_mode=demo_mode)
        sessions = []
        for sid, turns in manager._memory_store.items():
            if turns:
                first_q_list = [t["content"] for t in turns if t["role"] == "user"]
                first_q = first_q_list[0] if first_q_list else ""
                sessions.append(SessionSummary(
                    session_id=sid,
                    turn_count=len(turns),
                    last_active=turns[-1].get("created_at", ""),
                    first_question=first_q
                ))
        sessions.sort(key=lambda x: x.last_active, reverse=True)
        return SessionListResponse(sessions=sessions, total=len(sessions))
    else:
        from app.db.relational import get_sessions
        raw_sessions = await get_sessions()
        sessions = [SessionSummary(**s) for s in raw_sessions]
        return SessionListResponse(sessions=sessions, total=len(sessions))


_SETTINGS_FIELD_DESCRIPTIONS: dict[str, str] = {
    "LLM_PROVIDER": "Which LLM provider to use for generation.",
    "GROQ_MODEL": "Model id used when LLM_PROVIDER=groq.",
    "OPENROUTER_MODEL": "Model id used when LLM_PROVIDER=openrouter.",
    "OPENAI_MODEL": "Model id used when LLM_PROVIDER=openai.",
    "MAX_CHUNKS_RETURN": "Top-K passages returned to the LLM.",
    "RERANK_TOP_N": "Top-N kept after re-ranking.",
    "MAX_PER_DOC": "Per-document cap when MMR is on.",
    "MMR_ENABLED": "Diversify final passages via MMR.",
    "MMR_LAMBDA": "MMR balance (0=diverse, 1=relevant).",
    "HYDE_ENABLED": "Expand the query with a hypothetical document.",
    "MULTI_QUERY_ENABLED": "Generate multiple paraphrases of the question.",
    "MULTI_QUERY_VARIANTS": "How many query paraphrases to generate.",
    "ANSWER_VERIFIER_ENABLED": "Run a groundedness verifier pass.",
    "ANSWER_VERIFIER_MIN_SCORE": "Minimum groundedness before refusal.",
    "QUERY_REWRITE_ENABLED": "Auto-rewrite low-recall queries.",
    "CHAT_COREFERENCE_REWRITE": "Rewrite follow-ups using chat history.",
    "LOCAL_RERANKER_ENABLED": "Use a local cross-encoder when Cohere is down.",
    "INCLUDE_CITATIONS_DEFAULT": "Show citations on /query by default.",
    "AUTO_SUMMARY_ENABLED": "Summarise documents on ingest.",
    "ANSWER_CACHE_ENABLED": "Reuse identical recent answers.",
    "ANSWER_CACHE_TTL_SEC": "Answer cache TTL in seconds.",
}


def _python_type_name(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


@router.get("/settings/schema", response_model=SettingsSchemaResponse)
async def settings_schema(cookie: str | None = Header(None, alias="Cookie")):
    """List the user-tunable settings, their defaults, and current overrides."""
    from app.config import OVERRIDABLE_SETTINGS, _base_settings

    base = _base_settings()
    effective = get_settings()
    fields: list[SettingsSchemaField] = []
    enums = {
        "LLM_PROVIDER": ["groq", "openrouter", "openai"],
    }
    for key in sorted(OVERRIDABLE_SETTINGS):
        default = getattr(base, key, None)
        current = getattr(effective, key, default)
        type_name = "enum" if key in enums else _python_type_name(default)
        fields.append(
            SettingsSchemaField(
                key=key,
                type=type_name,
                default=default,
                current=current,
                description=_SETTINGS_FIELD_DESCRIPTIONS.get(key, ""),
                enum=enums.get(key),
            )
        )

    overrides: dict = {}
    uid = _read_uid_from_cookie(cookie)
    if uid:
        try:
            from app.db.relational import get_user_preferences

            prefs = await get_user_preferences(uid)
            overrides = prefs.get("settings") or {}
        except Exception:
            overrides = {}

    return SettingsSchemaResponse(fields=fields, overrides=overrides)


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(cookie: str | None = Header(None, alias="Cookie")):
    """Return saved bookmarks + settings overrides for the cookie owner."""
    uid = _read_uid_from_cookie(cookie)
    if not uid:
        raise HTTPException(status_code=401, detail="rag_engine_uid cookie required")
    from app.db.relational import get_user_preferences

    data = await get_user_preferences(uid)
    return UserPreferencesResponse(**data)


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    payload: UserPreferencesUpdate,
    cookie: str | None = Header(None, alias="Cookie"),
):
    """Replace bookmarks and/or settings overrides for the cookie owner."""
    uid = _read_uid_from_cookie(cookie)
    if not uid:
        raise HTTPException(status_code=401, detail="rag_engine_uid cookie required")
    from app.db.relational import upsert_user_preferences

    data = await upsert_user_preferences(
        uid,
        bookmarks=[b.model_dump() for b in payload.bookmarks] if payload.bookmarks is not None else None,
        settings_overrides=payload.settings if payload.settings is not None else None,
    )
    return UserPreferencesResponse(**data)


@router.post("/chat/sessions/{session_id}/branch", response_model=BranchSessionResponse)
async def branch_chat_session(
    session_id: str,
    request: BranchSessionRequest,
    x_demo_mode: str | None = Header(None),
):
    """Fork a chat session at the given turn, copying earlier turns into a new session."""
    demo_mode = get_demo_mode(x_demo_mode)
    if demo_mode:
        manager = SessionManager(demo_mode=demo_mode)
        turns = manager._memory_store.get(session_id) or []
        anchor_idx = next(
            (i for i, t in enumerate(turns) if t.get("id") == request.parent_turn_id),
            None,
        )
        if anchor_idx is None:
            raise HTTPException(status_code=404, detail="parent_turn_id not found in session")
        new_id = str(uuid.uuid4())
        copied = []
        for t in turns[: anchor_idx + 1]:
            new_turn = dict(t)
            new_turn["id"] = str(uuid.uuid4())
            new_turn["session_id"] = new_id
            copied.append(new_turn)
        manager._memory_store[new_id] = copied
        return BranchSessionResponse(
            session_id=new_id,
            parent_session_id=session_id,
            parent_turn_id=request.parent_turn_id,
            copied_turns=len(copied),
            title=request.title,
        )

    from app.db.relational import branch_session
    try:
        result = await branch_session(
            parent_session_id=session_id,
            parent_turn_id=request.parent_turn_id,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BranchSessionResponse(**result)


@router.get("/pdfs/{pdf_name}")
async def serve_pdf(pdf_name: str):
    safe_name = os.path.basename(pdf_name)

    # 1) Primary compatibility path: lookup by filename in relational metadata, then load bytes via configured storage backend.
    async with session_maker() as session:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.filename == safe_name)
            .order_by(DocumentModel.created_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        doc = res.scalar_one_or_none()
    if doc is not None:
        stored = await get_pdf_storage().get_pdf(doc.id)
        if stored is not None:
            return Response(
                content=stored.pdf_bytes,
                media_type=stored.content_type or "application/pdf",
                headers={"Content-Disposition": f'inline; filename="{stored.filename or safe_name}"'},
            )

    # 2) Legacy filesystem fallback
    candidate_dirs = [
        os.path.join(os.getcwd(), "data", "uploaded_pdfs"),
        os.path.join(os.getcwd(), "data", "sample_pdfs"),
    ]
    for pdf_dir in candidate_dirs:
        base_dir = os.path.realpath(pdf_dir)
        pdf_path = os.path.realpath(os.path.join(base_dir, safe_name))
        if not pdf_path.startswith(base_dir):
            continue
        if os.path.exists(pdf_path):
            return FileResponse(pdf_path, media_type="application/pdf")
    raise HTTPException(status_code=404, detail="PDF not found.")


@router.get("/pdfs/by-id/{document_id}")
async def serve_pdf_by_document_id(document_id: str):
    storage = get_pdf_storage()
    stored = await storage.get_pdf(document_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="PDF not found.")
    filename = stored.filename or f"{document_id}.pdf"
    return Response(
        content=stored.pdf_bytes,
        media_type=stored.content_type or "application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(tag: str | None = None):
    try:
        async with session_maker() as session:
            stmt = select(DocumentModel).order_by(DocumentModel.created_at.desc())
            result = await session.execute(stmt)
            docs = result.scalars().all()

            items = []
            wanted = (tag or "").strip().lower()
            for d in docs:
                meta = d.metadata_ or {}
                doc_tags = list(d.tags or [])
                if wanted and wanted not in {t.lower() for t in doc_tags if isinstance(t, str)}:
                    continue
                items.append(DocumentListItem(
                    document_id=d.id,
                    pdf_name=d.filename,
                    service_name=meta.get("service_name", "Unknown"),
                    total_pages=meta.get("total_pages", 0),
                    total_chunks=meta.get("total_chunks", 0),
                    created_at=str(d.created_at),
                    summary=d.summary,
                    tags=doc_tags,
                    version=int(d.version or meta.get("version") or 1),
                ))
            return DocumentListResponse(documents=items, total=len(items))
    except Exception as e:
        logger.error("list_documents_error", error=str(e))
        raise HTTPException(status_code=500, detail="Database connection error.") from e


@router.get("/tags", response_model=TagsListResponse)
async def list_tags():
    """Return every tag in use across the corpus, sorted by frequency."""
    from app.db.relational import list_all_tags

    return TagsListResponse(tags=await list_all_tags())


@router.get("/metrics/recent", response_model=MetricsRecentResponse)
async def list_recent_metrics(minutes: int = 60):
    """Return the latest minute-by-minute aggregate metrics for the status page."""
    from app.db.relational import recent_metrics

    safe_minutes = max(1, min(int(minutes or 60), 1440))
    points = [MetricsRecentItem(**row) for row in await recent_metrics(safe_minutes)]
    return MetricsRecentResponse(points=points)


@router.get("/webhooks", response_model=WebhookListResponse)
async def list_webhook_subscriptions():
    """List configured webhook subscriptions and the supported event names."""
    from app.db.relational import WEBHOOK_EVENTS, list_webhooks

    rows = await list_webhooks()
    return WebhookListResponse(
        events=list(WEBHOOK_EVENTS),
        subscriptions=[WebhookSubscriptionItem(**row) for row in rows],
    )


@router.post("/webhooks", response_model=WebhookSubscriptionItem)
async def create_webhook_subscription(payload: WebhookCreateRequest):
    """Add a new webhook subscription."""
    from app.db.relational import WEBHOOK_EVENTS, create_webhook

    if payload.event not in WEBHOOK_EVENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event {payload.event!r}. Valid: {', '.join(WEBHOOK_EVENTS)}",
        )
    if not payload.url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")

    row = await create_webhook(
        event=payload.event,
        url=payload.url,
        enabled=payload.enabled,
        secret=payload.secret,
    )
    return WebhookSubscriptionItem(**row)


@router.patch("/webhooks/{webhook_id}", response_model=WebhookSubscriptionItem)
async def patch_webhook_subscription(webhook_id: str, payload: WebhookUpdateRequest):
    """Update a webhook subscription's URL, secret, or enabled flag."""
    from app.db.relational import update_webhook

    row = await update_webhook(
        webhook_id,
        enabled=payload.enabled,
        url=payload.url,
        secret=payload.secret,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookSubscriptionItem(**row)


@router.delete("/webhooks/{webhook_id}", response_model=dict)
async def delete_webhook_subscription(webhook_id: str):
    """Remove a webhook subscription."""
    from app.db.relational import delete_webhook

    deleted = await delete_webhook(webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"id": webhook_id, "status": "deleted"}


@router.post("/webhooks/{webhook_id}/test", response_model=dict)
async def test_webhook_subscription(webhook_id: str):
    """Send a synthetic test payload to a single subscription URL.

    Operators expect the "Test" button to fire regardless of the enabled
    flag (otherwise you can't verify a paused webhook before re-enabling
    it), so we bypass :func:`dispatch_webhook` and deliver directly.
    """
    from app.db.relational import list_webhooks
    from app.observability.webhooks import deliver_to_subscription

    rows = await list_webhooks()
    sub = next((r for r in rows if r["id"] == webhook_id), None)
    if sub is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    success = await deliver_to_subscription(
        sub,
        {"test": True, "subscription_id": webhook_id, "url": sub["url"]},
    )
    return {"id": webhook_id, "delivered": 1 if success else 0, "ok": success}


@router.get("/logs/recent", response_model=RecentLogsResponse)
async def list_recent_logs(limit: int = 200, level: str | None = None):
    """Return the latest N entries from the in-memory log ring buffer.

    The ``/app/status`` recent-activity tab polls this endpoint to surface
    structured log events without needing an external sink.
    """
    from app.observability import recent_log_entries

    safe_limit = max(1, min(int(limit or 200), 500))
    items: list[LogEntryItem] = []
    for raw in recent_log_entries(limit=safe_limit, level=level):
        seq = int(raw.get("seq") or 0)
        ts_value = raw.get("ts") or raw.get("timestamp") or 0
        try:
            ts = float(ts_value)
        except (TypeError, ValueError):
            ts = 0.0
        level_value = str(raw.get("level") or "info")
        event_value = raw.get("event")
        extra: dict[str, Any] = {}
        for key, value in raw.items():
            if key in {"seq", "ts", "timestamp", "level", "event"}:
                continue
            try:
                json.dumps(value)
                extra[key] = value
            except TypeError:
                extra[key] = repr(value)
        items.append(
            LogEntryItem(
                seq=seq,
                ts=ts,
                level=level_value,
                event=str(event_value) if event_value is not None else None,
                extra=extra,
            )
        )
    return RecentLogsResponse(entries=items)


@router.put("/documents/{document_id}/tags", response_model=DocumentTagsResponse)
async def update_document_tags(document_id: str, payload: DocumentTagsRequest):
    """Replace the tag list on a document and propagate to Qdrant payloads."""
    from app.db.relational import set_document_tags

    cleaned = await set_document_tags(document_id, payload.tags)
    if cleaned is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Sync chunk payloads in the vector store so payload-filtered retrieval
    # picks up the new tag set on the next request. Best-effort: a vector
    # store outage shouldn't fail the metadata update itself.
    try:
        async with session_maker() as session:
            stmt = select(ChunkModel.id).where(ChunkModel.document_id == document_id)
            res = await session.execute(stmt)
            chunk_ids = list(res.scalars().all())
        if chunk_ids:
            vector_store = get_vector_store()
            updater = getattr(vector_store, "update_payload", None)
            if callable(updater):
                await updater(
                    collection=settings.vector_collection,
                    chunk_ids=chunk_ids,
                    payload={"tags": cleaned},
                )
    except Exception as exc:  # pragma: no cover — vector outage shouldn't 500.
        logger.warning("tags.vector_payload_sync_failed", error=str(exc))

    return DocumentTagsResponse(document_id=document_id, tags=cleaned)

@router.get("/documents/{document_id}/chunks", response_model=ChunkListResponse)
async def list_chunks(document_id: str):
    async with session_maker() as session:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Document not found")
            
        stmt = select(ChunkModel).where(ChunkModel.document_id == document_id)
        result = await session.execute(stmt)
        chunks = result.scalars().all()
        
        chunk_items = []
        for c in chunks:
            preview = c.text[:100] + "..." if len(c.text) > 100 else c.text
            meta = c.metadata_ or {}
            chunk_items.append({
                "chunk_id": c.id,
                "text_preview": preview,
                "page_number": meta.get("page_number", 0),
                "section_title": meta.get("section_title", "")
            })
            
        return ChunkListResponse(
            document_id=document_id,
            chunks=chunk_items,
            total=len(chunk_items)
        )

@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(document_id: str):
    async with session_maker() as session:
        # 1. Check doc exists
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Document not found.")

        # 2. Get chunk ids
        stmt = select(ChunkModel.id).where(ChunkModel.document_id == document_id)
        res = await session.execute(stmt)
        chunk_ids = list(res.scalars().all())
        
        # 3. Delete from vector store
        if chunk_ids:
            try:
                vector_store = get_vector_store()
                await vector_store.delete(collection=settings.vector_collection, chunk_ids=chunk_ids)
            except Exception as e:
                logger.error("vector_store_delete_error", error=str(e))
            
        # 4. Delete chunks from relational
        stmt_del_chunks = delete(ChunkModel).where(ChunkModel.document_id == document_id)
        await session.execute(stmt_del_chunks)
        
        # 5. Delete doc from relational
        stmt_del_doc = delete(DocumentModel).where(DocumentModel.id == document_id)
        await session.execute(stmt_del_doc)

        await session.commit()

    # 6. Delete stored PDF bytes from selected backend
    storage = get_pdf_storage()
    await storage.delete_pdf(document_id)

    bump_corpus_version(reason="document_deleted")

    return DeleteResponse(
        document_id=document_id,
        status="deleted",
        chunks_removed=len(chunk_ids)
    )
