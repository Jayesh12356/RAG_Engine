from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str
    service_category: str | None = None
    top_k: int = 20
    rerank_top_n: int | None = None
    include_citations: bool | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def payload(self) -> dict[str, Any]:
        return self.metadata


class SourceChunk(BaseModel):
    chunk_id: str
    text: str
    pdf_name: str
    pdf_url: str
    page_number: int
    section_title: str
    score: float


class Citation(BaseModel):
    """Compact reference back to a retrieved chunk for downstream UIs."""

    chunk_id: str = ""
    document_id: str = ""
    pdf_name: str = ""
    page_number: int = 0
    section_title: str = ""
    score: float = 0.0


class QueryResponse(BaseModel):
    question: str
    answer: str
    confidence: float
    confidence_label: str
    sources: list[SourceChunk] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    service_category: str
    refused: bool = False
    visual_capable: bool = False
