from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str
    service_category: str | None = None
    top_k: int = 20
    rerank_top_n: int | None = None
    include_citations: bool | None = None
    # Optional Spaces filter (Wave 2.9). When non-empty, retrieval restricts to
    # chunks whose payload ``tags`` array intersects the supplied list.
    tags: list[str] = Field(default_factory=list)


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


class TextSpan(BaseModel):
    """Character-level span inside a chunk's text.

    ``start`` and ``end`` are 0-indexed offsets into the original chunk text;
    ``text`` is the raw substring (handy for the UI when it doesn't have the
    full chunk loaded).
    """

    text: str = ""
    start: int = 0
    end: int = 0


class Citation(BaseModel):
    """Compact reference back to a retrieved chunk for downstream UIs."""

    chunk_id: str = ""
    document_id: str = ""
    pdf_name: str = ""
    page_number: int = 0
    section_title: str = ""
    score: float = 0.0
    text_span: TextSpan | None = None


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
    # Approximate USD cost for the LLM call(s) that produced this answer.
    # Estimated from token counts × the active provider's published pricing;
    # surfaced in the ConfidenceGauge popover so users can see "$ / question".
    cost_usd: float = 0.0
    latency_ms: float = 0.0
