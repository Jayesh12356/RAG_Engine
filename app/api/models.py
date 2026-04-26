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


class IngestTaskStatusResponse(BaseModel):
    task_id: str
    document_id: str | None = None
    filename: str
    status: str
    stage: str
    progress: int = 0
    total_chunks: int = 0
    processed_chunks: int = 0
    message: str | None = None
    error: str | None = None
    started_at: str = ""
    updated_at: str = ""

class QueryAPIRequest(BaseModel):
    question: str
    service_category: str | None = None
    top_k: int = 20
    rerank_top_n: int | None = None
    include_citations: bool | None = None
    # Optional Spaces filter (Wave 2.9). Passed straight through to retrieval.
    tags: list[str] = []

class DocumentListItem(BaseModel):
    document_id: str
    pdf_name: str
    service_name: str
    total_pages: int
    total_chunks: int
    created_at: str
    summary: str | None = None
    tags: list[str] = []
    version: int = 1

class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int


class DocumentTagsRequest(BaseModel):
    """Replace the tag set on a document.

    The server normalises (strips whitespace, dedupes case-insensitively, caps
    at ~16 tags) so the UI can stay dumb.
    """

    tags: list[str]


class DocumentTagsResponse(BaseModel):
    document_id: str
    tags: list[str]


class TagsListResponse(BaseModel):
    tags: list[str]

class ChunkListResponse(BaseModel):
    document_id: str
    chunks: list[dict[str, Any]]
    total: int

class DeleteResponse(BaseModel):
    document_id: str
    status: str
    chunks_removed: int

class HealthDbPoolStats(BaseModel):
    """Snapshot of the SQLAlchemy async engine pool, when introspectable."""

    size: int | None = None
    checked_in: int | None = None
    checked_out: int | None = None
    overflow: int | None = None


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_provider: str
    vector_db: str
    relational_db: str
    demo_mode: bool
    visual_capable: bool = False
    image_gen_active: bool = False
    # Wave 3.6 — operational signals surfaced on /app/status.
    uptime_seconds: float | None = None
    db_pool: HealthDbPoolStats | None = None
    vector_index_size: int | None = None
    queue_depth: int | None = None

class SessionSummary(BaseModel):
    session_id: str
    turn_count: int
    last_active: str
    first_question: str
    parent_session_id: str | None = None
    parent_turn_id: str | None = None
    title: str | None = None

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


class BranchSessionRequest(BaseModel):
    parent_turn_id: str
    title: str | None = None


class BranchSessionResponse(BaseModel):
    session_id: str
    parent_session_id: str
    parent_turn_id: str
    copied_turns: int
    title: str | None = None


class BookmarkItem(BaseModel):
    id: str
    question: str
    answer: str | None = None
    createdAt: str | None = None


class UserPreferencesResponse(BaseModel):
    rag_engine_uid: str
    bookmarks: list[BookmarkItem] = []
    settings: dict[str, Any] = {}
    updated_at: str | None = None


class SettingsSchemaField(BaseModel):
    key: str
    type: str  # "bool" | "int" | "float" | "string" | "enum"
    default: Any
    current: Any
    description: str = ""
    enum: list[str] | None = None


class SettingsSchemaResponse(BaseModel):
    """Public knob inventory for the /app/settings page."""

    fields: list[SettingsSchemaField]
    overrides: dict[str, Any] = {}


class UserPreferencesUpdate(BaseModel):
    bookmarks: list[BookmarkItem] | None = None
    settings: dict[str, Any] | None = None


class LogEntryItem(BaseModel):
    """A single structured log event captured by the in-memory ring buffer."""

    seq: int
    ts: float
    level: str
    event: str | None = None
    extra: dict[str, Any] = {}


class RecentLogsResponse(BaseModel):
    entries: list[LogEntryItem]


class MetricsRecentItem(BaseModel):
    minute: str
    total: int = 0
    refusals: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    mean_confidence: float = 0.0
    cost_usd: float = 0.0


class MetricsRecentResponse(BaseModel):
    points: list[MetricsRecentItem]


class WebhookSubscriptionItem(BaseModel):
    id: str
    event: str
    url: str
    enabled: bool = True
    secret: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WebhookListResponse(BaseModel):
    events: list[str]
    subscriptions: list[WebhookSubscriptionItem]


class WebhookCreateRequest(BaseModel):
    event: str
    url: str
    enabled: bool = True
    secret: str | None = None


class WebhookUpdateRequest(BaseModel):
    enabled: bool | None = None
    url: str | None = None
    secret: str | None = None
