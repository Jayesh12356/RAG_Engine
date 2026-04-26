from typing import Any

from pydantic import BaseModel


class IngestResponse(BaseModel):
    document_id: str = ""
    pdf_name: str = ""
    total_pages: int = 0
    total_chunks: int = 0
    service_name: str = ""
    status: str
    error: str | None = None
    task_id: str | None = None

class QueryAPIRequest(BaseModel):
    question: str
    service_category: str | None = None
    top_k: int = 20
    rerank_top_n: int | None = None
    include_citations: bool | None = None

class DocumentListItem(BaseModel):
    document_id: str
    pdf_name: str
    service_name: str
    total_pages: int
    total_chunks: int
    created_at: str

class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int

class ChunkListResponse(BaseModel):
    document_id: str
    chunks: list[dict[str, Any]]
    total: int

class DeleteResponse(BaseModel):
    document_id: str
    status: str
    chunks_removed: int

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_provider: str
    vector_db: str
    relational_db: str
    demo_mode: bool
    visual_capable: bool = False
    image_gen_active: bool = False

class SessionSummary(BaseModel):
    session_id: str
    turn_count: int
    last_active: str
    first_question: str

class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int

class HistoryResponse(BaseModel):
    session_id: str
    turns: list[Any]
    total: int

class DeleteSessionResponse(BaseModel):
    session_id: str
    status: str
    turns_removed: int
