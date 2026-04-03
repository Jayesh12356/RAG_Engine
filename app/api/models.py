from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class IngestResponse(BaseModel):
    document_id: str = ""
    pdf_name: str = ""
    total_pages: int = 0
    total_chunks: int = 0
    service_name: str = ""
    status: str
    error: Optional[str] = None
    task_id: Optional[str] = None

class QueryAPIRequest(BaseModel):
    question: str
    service_category: Optional[str] = None
    top_k: int = 20
    rerank_top_n: Optional[int] = None

class DocumentListItem(BaseModel):
    document_id: str
    pdf_name: str
    service_name: str
    total_pages: int
    total_chunks: int
    created_at: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentListItem]
    total: int

class ChunkListResponse(BaseModel):
    document_id: str
    chunks: List[Dict[str, Any]]
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

class SessionSummary(BaseModel):
    session_id: str
    turn_count: int
    last_active: str
    first_question: str

class SessionListResponse(BaseModel):
    sessions: List[SessionSummary]
    total: int

class HistoryResponse(BaseModel):
    session_id: str
    turns: List[Any]
    total: int

class DeleteSessionResponse(BaseModel):
    session_id: str
    status: str
    turns_removed: int
