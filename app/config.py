import re
from contextvars import ContextVar
from functools import lru_cache
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Visual-capable model allowlist ────────────────────────────────────────
# These substrings, when found inside the configured model id (case-insensitive),
# mark the active LLM as "visual capable". Unlocks rich answer formatting in
# the prompt (mermaid diagrams, recharts JSON, KaTeX math, image-request hooks).
# No env var is added — adding a new vision-capable model = adding a substring
# below. Keep substrings short and unambiguous.
_VISUAL_MODEL_PATTERNS: tuple[str, ...] = (
    # OpenAI
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4-vision",
    "gpt-4.1",
    "gpt-5",
    "o1",
    "o3",
    "o4",
    # Anthropic Claude (3.x and later are all multimodal)
    "claude-3",
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-haiku-4",
    "claude-4",
    "claude-3-5",
    # Google Gemini
    "gemini-1.5",
    "gemini-2",
    "gemini-pro-vision",
    "gemini-flash",
    # Open-weight vision models
    "qwen2-vl",
    "qwen-vl",
    "llava",
    "pixtral",
    "internvl",
    "molmo",
    "phi-3-vision",
    "phi-3.5-vision",
    "phi-4-multimodal",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── LLM ───────────────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["groq", "openrouter", "openai"] = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Embeddings ────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: Literal["openai", "openrouter", "cohere"] = "openai"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENROUTER_EMBEDDING_MODEL: str = "google/gemini-embedding-001"
    COHERE_API_KEY: str = ""
    COHERE_EMBEDDING_MODEL: str = "embed-english-v3.0"
    EMBEDDING_DIM: int = 1536

    # ── Vector DB ─────────────────────────────────────────────────────────
    VECTOR_DB: Literal["qdrant", "milvus"] = "qdrant"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "helpdesk_chunks"
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_COLLECTION: str = "helpdesk_chunks"

    # ── Relational DB ─────────────────────────────────────────────────────
    DATABASE_URL: str = ""
    DB_SCHEMA: str = "public"
    RELATIONAL_DB: Literal["postgres", "mysql"] = "postgres"
    POSTGRES_URL: str = "postgresql+asyncpg://user:pass@localhost/helpdesk"
    MYSQL_URL: str = "mysql+aiomysql://user:pass@localhost/helpdesk"

    # ── Re-ranking ────────────────────────────────────────────────────────
    COHERE_RERANK_MODEL: str = "rerank-english-v3.0"

    # ── Local cross-encoder rerank fallback ───────────────────────────────
    # When Cohere is unreachable, optionally rescore with a local
    # ``sentence-transformers`` cross-encoder. Default OFF and lazy-loaded
    # so the package stays usable without the heavy ML deps.
    LOCAL_RERANKER_ENABLED: bool = False
    LOCAL_RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # ── App ───────────────────────────────────────────────────────────────
    DEMO_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    MAX_CHUNKS_RETURN: int = 20
    RERANK_TOP_N: int = 10
    CONFIDENCE_THRESHOLD: float = 0.40
    RELEVANCE_MIN_TOP_SCORE: float = 0.22
    RELEVANCE_MIN_SECOND_SCORE: float = 0.12
    RELEVANCE_MIN_SCORE_GAP: float = 0.03
    QUERY_STREAM_CHUNK_SIZE: int = 40
    LLM_REQUEST_TIMEOUT_SEC: float = 25.0
    LLM_RETRY_ATTEMPTS: int = 2

    # ── Hybrid retrieval ──────────────────────────────────────────────────
    HYBRID_RRF_K: int = 60
    HYBRID_DENSE_LIMIT: int = 50
    HYBRID_SPARSE_LIMIT: int = 50
    SPARSE_INDEX_DIR: str = "data/sparse_index"

    # ── Diversification (MMR) ─────────────────────────────────────────────
    MMR_ENABLED: bool = True
    MMR_LAMBDA: float = 0.7
    # Per-document cap. Default of 2 was tuned for multi-document IT runbook
    # corpora; for single-document Q&A (a CV, a CSV export, a research paper)
    # it would cap context at 2 chunks and starve the LLM. 6 still keeps
    # answers diversified across multiple sections while preventing one large
    # document from drowning out a smaller one.
    MAX_PER_DOC: int = 6

    # ── Citations ─────────────────────────────────────────────────────────
    INCLUDE_CITATIONS_DEFAULT: bool = False

    # ── Calibrated confidence + extractive fallback ───────────────────────
    MIN_FALLBACK_OVERLAP: float = 0.20
    EXTRACTIVE_FALLBACK_CONFIDENCE: float = 0.45

    # ── Query rewriting ───────────────────────────────────────────────────
    QUERY_REWRITE_ENABLED: bool = False
    QUERY_REWRITE_TRIGGER_SCORE: float = 0.40

    # ── Retrieval expansion (HyDE + multi-query) ──────────────────────────
    # Both default OFF so existing deployments keep their latency profile.
    # When enabled, the pipeline runs an extra LLM expansion call concurrent
    # with retrieval and fuses the variants with RRF (HYBRID_RRF_K).
    HYDE_ENABLED: bool = False
    MULTI_QUERY_ENABLED: bool = False
    MULTI_QUERY_VARIANTS: int = 3
    HYDE_TIMEOUT_SEC: float = 6.0

    # ── Chat: conversational coreference rewrite ──────────────────────────
    # When enabled, follow-up questions like "why?" or "tell me more about it"
    # are rewritten into self-contained queries using the recent history,
    # then sent to retrieval. Default OFF (one extra LLM call per follow-up).
    CHAT_COREFERENCE_REWRITE: bool = False

    # ── Groundedness verifier ─────────────────────────────────────────────
    # An opt-in second LLM pass that scores how well an answer is supported
    # by retrieved context. Below ``ANSWER_VERIFIER_MIN_SCORE`` we regenerate
    # once and refuse if the regeneration is also weak. Adds latency.
    ANSWER_VERIFIER_ENABLED: bool = False
    ANSWER_VERIFIER_MIN_SCORE: float = 0.55

    # ── Answer cache ──────────────────────────────────────────────────────
    # Process-local LRU cache that returns prior answers for identical
    # ``(question, top_k, service_category)`` requests at the current
    # corpus version. Set ``ANSWER_CACHE_BACKEND=redis`` to swap in the
    # Redis adapter (requires the ``redis`` package and ``REDIS_URL``).
    # Caching is best for fan-out demos and refresh storms; defaults are
    # conservative so the cache is invisible at low volume.
    ANSWER_CACHE_ENABLED: bool = True
    ANSWER_CACHE_BACKEND: Literal["memory", "redis"] = "memory"
    ANSWER_CACHE_MAXSIZE: int = 256
    ANSWER_CACHE_TTL_SEC: int = 600
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auto-summary on ingest ────────────────────────────────────────────
    # Single LLM call after a successful ingest to populate
    # ``documents.summary`` (a 2-3 sentence abstract). Failure is silent
    # so disabling the LLM doesn't break ingestion.
    AUTO_SUMMARY_ENABLED: bool = True

    # ── Intent-driven retrieval tuning ────────────────────────────────────
    INTENT_TROUBLESHOOT_TOP_K_BOOST: int = 6
    INTENT_HOWTO_TOP_K_BOOST: int = 4

    # ── Chat History ──────────────────────────────────────────────────────
    CHAT_HISTORY_TURNS: int = 5
    MAX_SESSIONS: int = 100

    # ── Ingestion ─────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    EMBED_BATCH_SIZE: int = 32
    HEADING_AWARE_CHUNKING: bool = True
    PDF_STORAGE_BACKEND: Literal["relational", "vector"] = "relational"
    PDF_VECTOR_COLLECTION: str = "helpdesk_pdf_files"
    PDF_VECTOR_CHUNK_BYTES: int = 60000
    PDF_IMAGE_PAGE_CHAR_THRESHOLD: int = 60
    PDF_IMAGE_RATIO_THRESHOLD: float = 0.6
    OCR_ENABLED: bool = True
    # OCR_MODE controls how OCR is performed when OCR_ENABLED is true:
    # - "tesseract": local Tesseract only
    # - "vision": Vision model only (falls back to Tesseract if Vision is unavailable)
    # - "hybrid": Tesseract first, then optional Vision fallback on low confidence
    OCR_MODE: Literal["tesseract", "vision", "hybrid"] = "hybrid"
    OCR_LANGUAGES: str = "eng+hin"
    OCR_RENDER_DPI: int = 300
    OCR_TEXT_CONFIDENCE_THRESHOLD: float = 0.35
    OCR_VISION_FALLBACK_ENABLED: bool = False
    OCR_VISION_MODEL: str = "gpt-4o-mini"
    TESSERACT_CMD: str = ""
    CORS_ALLOW_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Image generation hook ─────────────────────────────────────────────
    # "auto" = enabled iff the active LLM is visual-capable AND an OpenAI key
    # is configured. "true" forces on (still requires a key); "false" disables.
    IMAGE_GEN_ENABLED: Literal["auto", "true", "false"] = "auto"
    IMAGE_GEN_MODEL: str = "gpt-image-1"
    IMAGE_GEN_SIZE: str = "1024x1024"

    @property
    def llm_is_visual_capable(self) -> bool:
        """Auto-detect visual capability from the configured model id.

        Reads the active provider's model name and matches it against
        :data:`_VISUAL_MODEL_PATTERNS`. No env var is required — drop a model
        in ``OPENAI_MODEL`` / ``OPENROUTER_MODEL`` / ``GROQ_MODEL`` and the
        rest of the stack picks up the new capability automatically.
        """
        provider = self.LLM_PROVIDER
        if provider == "groq":
            model = self.GROQ_MODEL
        elif provider == "openrouter":
            model = self.OPENROUTER_MODEL
        else:
            model = self.OPENAI_MODEL
        m = (model or "").lower()
        if not m:
            return False
        return any(p in m for p in _VISUAL_MODEL_PATTERNS)

    @property
    def image_gen_active(self) -> bool:
        """Resolved truth value for image generation.

        ``auto`` requires both a visual-capable LLM and an OpenAI key (the
        image generation API). ``true`` forces on but still requires the key.
        """
        if self.IMAGE_GEN_ENABLED == "false":
            return False
        if not self.OPENAI_API_KEY:
            return False
        if self.IMAGE_GEN_ENABLED == "true":
            return True
        return self.llm_is_visual_capable

    @property
    def vector_collection(self) -> str:
        if self.VECTOR_DB == "milvus":
            return self.MILVUS_COLLECTION
        return self.QDRANT_COLLECTION

    @property
    def cors_allow_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ALLOW_ORIGINS.split(",") if x.strip()]

    @property
    def relational_url(self) -> str:
        if self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if url.startswith("postgres://"):
                return "postgresql+asyncpg://" + url[len("postgres://"):]
            if url.startswith("postgresql://"):
                return "postgresql+asyncpg://" + url[len("postgresql://"):]
            return url
        if self.RELATIONAL_DB == "mysql":
            return self.MYSQL_URL
        return self.POSTGRES_URL

    @property
    def db_schema(self) -> str:
        schema = self.DB_SCHEMA.strip() or "public"
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
            raise ValueError("DB_SCHEMA must match ^[A-Za-z_][A-Za-z0-9_]*$")
        return schema


# ── Per-request override channel ────────────────────────────────────────────
# A ContextVar populated by the FastAPI middleware in
# :mod:`app.api.middleware`. Each web request sees the global ``Settings``
# singleton with these keys overlaid on top, so a user with
# ``user_preferences.settings = {"LLM_PROVIDER": "openai"}`` can switch their
# own pipeline without altering the process-wide config.
#
# We expose an explicit allowlist (``OVERRIDABLE_SETTINGS``) so a malicious or
# misguided override cannot poke at things like database URLs, CORS, secret
# keys, or timeouts.
_settings_overrides: ContextVar[dict[str, Any]] = ContextVar(
    "settings_overrides", default={}
)

OVERRIDABLE_SETTINGS: frozenset[str] = frozenset(
    {
        # LLM choice
        "LLM_PROVIDER",
        "GROQ_MODEL",
        "OPENROUTER_MODEL",
        "OPENAI_MODEL",
        # Retrieval shape
        "MAX_CHUNKS_RETURN",
        "RERANK_TOP_N",
        "MAX_PER_DOC",
        "MMR_ENABLED",
        "MMR_LAMBDA",
        # Quality knobs
        "HYDE_ENABLED",
        "MULTI_QUERY_ENABLED",
        "MULTI_QUERY_VARIANTS",
        "ANSWER_VERIFIER_ENABLED",
        "ANSWER_VERIFIER_MIN_SCORE",
        "QUERY_REWRITE_ENABLED",
        "CHAT_COREFERENCE_REWRITE",
        "LOCAL_RERANKER_ENABLED",
        # UX
        "INCLUDE_CITATIONS_DEFAULT",
        "AUTO_SUMMARY_ENABLED",
        # Cache
        "ANSWER_CACHE_ENABLED",
        "ANSWER_CACHE_TTL_SEC",
    }
)


def set_settings_overrides(values: dict[str, Any] | None):
    """Install per-request settings overrides (filtered against the allowlist).

    Returns the ``Token`` from ``ContextVar.set`` so callers (the middleware)
    can ``reset`` it after the request finishes.
    """
    cleaned: dict[str, Any] = {}
    for key, value in (values or {}).items():
        if key in OVERRIDABLE_SETTINGS:
            cleaned[key] = value
    return _settings_overrides.set(cleaned)


def reset_settings_overrides(token) -> None:
    try:
        _settings_overrides.reset(token)
    except (LookupError, ValueError):
        # Already reset by some other path — harmless.
        pass


@lru_cache
def _base_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Return the active :class:`Settings`, merged with per-request overrides.

    Without overrides this is the same cached singleton (no copy cost). When
    a middleware has set per-cookie overrides, we ``model_copy(update=…)`` so
    the call site sees a mutated view without disturbing other concurrent
    requests.
    """
    base = _base_settings()
    overrides = _settings_overrides.get()
    if not overrides:
        return base
    return base.model_copy(update=overrides)
