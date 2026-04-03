from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class QueryRequest(BaseModel):
    question: str
    service_category: Optional[str] = None
    top_k: int = 20
    rerank_top_n: Optional[int] = None

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def payload(self) -> Dict[str, Any]:
        return self.metadata

class SourceChunk(BaseModel):
    chunk_id: str
    text: str
    pdf_name: str
    pdf_url: str
    page_number: int
    section_title: str
    score: float

class QueryResponse(BaseModel):
    question: str
    answer: str
    confidence: float
    confidence_label: str
    sources: List[SourceChunk] = Field(default_factory=list)
    service_category: str
    refused: bool = False
