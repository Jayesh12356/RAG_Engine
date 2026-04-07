from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Header
from fastapi.responses import FileResponse, StreamingResponse, Response
from typing import Optional
from sqlalchemy import select, delete
import uuid
import os
import structlog

from app.api.models import (
    IngestResponse, QueryAPIRequest, DocumentListItem, DocumentListResponse,
    ChunkListResponse, DeleteResponse, HealthResponse, SessionSummary, SessionListResponse,
    HistoryResponse, DeleteSessionResponse
)
from app.models.query import QueryRequest
from app.config import get_settings
from app.ingestion.pipeline import IngestPipeline
from app.query.pipeline import QueryPipeline
from app.db.relational import get_session_maker, DocumentModel, ChunkModel
from app.db.vector_store import get_vector_store
from app.chat.pipeline import ChatPipeline, ChatRequest, ChatResponse
from app.chat.session import SessionManager
from app.storage.pdf_storage import get_pdf_storage

logger = structlog.get_logger(__name__)
router = APIRouter()
settings = get_settings()

session_maker = get_session_maker()

def get_demo_mode(x_demo_mode: Optional[str] = Header(None)) -> bool:
    if x_demo_mode is not None:
        return x_demo_mode.lower() == "true"
    return settings.DEMO_MODE

@router.get("/health", response_model=HealthResponse)
async def health_check(x_demo_mode: Optional[str] = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    return HealthResponse(
        status="ok",
        llm_provider=settings.LLM_PROVIDER,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        vector_db=settings.VECTOR_DB,
        relational_db=settings.RELATIONAL_DB,
        demo_mode=demo_mode
    )

async def run_ingest_and_cleanup(
    tmp_path: str,
    demo_mode: bool,
    service_name_override: Optional[str],
    content: bytes,
    content_type: str,
):
    try:
        pipeline = IngestPipeline(demo_mode=demo_mode)
        await pipeline.run(
            tmp_path,
            service_name_override,
            pdf_bytes=content,
            content_type=content_type,
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
    service_name_override: Optional[str] = Form(None),
    background: bool = Form(False),
    x_demo_mode: Optional[str] = Header(None)
):
    demo_mode = get_demo_mode(x_demo_mode)
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    os.makedirs("/tmp", exist_ok=True)
    task_id = str(uuid.uuid4())
    tmp_path = f"/tmp/{task_id}_{file.filename}"
    
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
        
    if background:
        background_tasks.add_task(
            run_ingest_and_cleanup,
            tmp_path,
            demo_mode,
            service_name_override,
            content,
            file.content_type or "application/pdf",
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
                content_type=file.content_type or "application/pdf",
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

@router.post("/query")
async def query_pipeline(
    request: QueryAPIRequest,
    x_demo_mode: Optional[str] = Header(None)
):
    demo_mode = get_demo_mode(x_demo_mode)
    
    q_req = QueryRequest(
        question=request.question,
        service_category=request.service_category,
        top_k=request.top_k,
        rerank_top_n=request.rerank_top_n
    )
    
    pipeline = QueryPipeline(demo_mode=demo_mode)
    response = await pipeline.run(q_req)
    return response


@router.post("/query/stream")
async def query_pipeline_stream(
    request: QueryAPIRequest,
    x_demo_mode: Optional[str] = Header(None)
):
    demo_mode = get_demo_mode(x_demo_mode)
    q_req = QueryRequest(
        question=request.question,
        service_category=request.service_category,
        top_k=request.top_k,
        rerank_top_n=request.rerank_top_n
    )
    pipeline = QueryPipeline(demo_mode=demo_mode)
    return StreamingResponse(
        pipeline.run_stream(q_req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, x_demo_mode: Optional[str] = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    pipeline = ChatPipeline(demo_mode=demo_mode)
    return await pipeline.run(request)


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, x_demo_mode: Optional[str] = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    pipeline = ChatPipeline(demo_mode=demo_mode)
    return StreamingResponse(
        pipeline.run_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@router.get("/chat/{session_id}/history", response_model=HistoryResponse)
async def get_chat_history(session_id: str, limit: int = 50, x_demo_mode: Optional[str] = Header(None)):
    demo_mode = get_demo_mode(x_demo_mode)
    manager = SessionManager(demo_mode=demo_mode)
    turns = await manager.get_history(session_id, limit=limit)
    if not turns and demo_mode:
        if session_id not in manager._memory_store:
            raise HTTPException(status_code=404, detail="Session not found")
    elif not turns and not demo_mode:
        from app.db.relational import get_session_maker, ConversationHistoryModel
        from sqlalchemy import select
        async with get_session_maker()() as session:
            stmt = select(ConversationHistoryModel.id).where(ConversationHistoryModel.session_id == session_id).limit(1)
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Session not found")
    return HistoryResponse(session_id=session_id, turns=TurnsToDicts(turns), total=len(turns))

def TurnsToDicts(turns) -> list:
    return [t.model_dump() for t in turns]

@router.delete("/chat/{session_id}", response_model=DeleteSessionResponse)
async def delete_chat_session(session_id: str, x_demo_mode: Optional[str] = Header(None)):
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
async def get_chat_sessions(x_demo_mode: Optional[str] = Header(None)):
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
async def list_documents():
    try:
        async with session_maker() as session:
            stmt = select(DocumentModel).order_by(DocumentModel.created_at.desc())
            result = await session.execute(stmt)
            docs = result.scalars().all()
            
            items = []
            for d in docs:
                meta = d.metadata_ or {}
                items.append(DocumentListItem(
                    document_id=d.id,
                    pdf_name=d.filename,
                    service_name=meta.get("service_name", "Unknown"),
                    total_pages=meta.get("total_pages", 0),
                    total_chunks=meta.get("total_chunks", 0),
                    created_at=str(d.created_at)
                ))
            return DocumentListResponse(documents=items, total=len(items))
    except Exception as e:
        logger.error("list_documents_error", error=str(e))
        raise HTTPException(status_code=500, detail="Database connection error.")

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
        
    return DeleteResponse(
        document_id=document_id,
        status="deleted",
        chunks_removed=len(chunk_ids)
    )
