from functools import lru_cache
from typing import Literal
import re
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    LLM_PROVIDER: Literal["groq", "openrouter", "openai"] = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Embeddings
    EMBEDDING_PROVIDER: Literal["openai", "openrouter", "cohere"] = "openai"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENROUTER_EMBEDDING_MODEL: str = "google/gemini-embedding-001"
    COHERE_API_KEY: str = ""
    COHERE_EMBEDDING_MODEL: str = "embed-english-v3.0"
    EMBEDDING_DIM: int = 1536

    # Vector DB
    VECTOR_DB: Literal["qdrant", "milvus"] = "qdrant"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "helpdesk_chunks"
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_COLLECTION: str = "helpdesk_chunks"

    # Relational DB
    DATABASE_URL: str = ""
    DB_SCHEMA: str = "public"
    RELATIONAL_DB: Literal["postgres", "mysql"] = "postgres"
    POSTGRES_URL: str = "postgresql+asyncpg://user:pass@localhost/helpdesk"
    MYSQL_URL: str = "mysql+aiomysql://user:pass@localhost/helpdesk"

    # Re-ranking
    COHERE_RERANK_MODEL: str = "rerank-english-v3.0"

    # App
    DEMO_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    MAX_CHUNKS_RETURN: int = 20
    RERANK_TOP_N: int = 10
    CONFIDENCE_THRESHOLD: float = 0.40
    RELEVANCE_MIN_TOP_SCORE: float = 0.35
    RELEVANCE_MIN_SECOND_SCORE: float = 0.20
    RELEVANCE_MIN_SCORE_GAP: float = 0.03
    QUERY_STREAM_CHUNK_SIZE: int = 40
    LLM_REQUEST_TIMEOUT_SEC: float = 25.0
    LLM_RETRY_ATTEMPTS: int = 2
    # Chat History
    CHAT_HISTORY_TURNS: int = 5
    MAX_SESSIONS: int = 100

    # Ingestion
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    EMBED_BATCH_SIZE: int = 32
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

@lru_cache()
def get_settings() -> Settings:
    return Settings()
