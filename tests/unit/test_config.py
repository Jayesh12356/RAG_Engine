import pytest
from app.config import Settings
from app.db.vector_store import get_vector_store, QdrantVectorStore, MilvusVectorStore
from app.db.relational import get_engine
import os

def test_settings_load():
    settings = Settings(LLM_PROVIDER="groq", EMBEDDING_PROVIDER="openai", VECTOR_DB="qdrant", RELATIONAL_DB="postgres")
    assert settings.LLM_PROVIDER == "groq"
    assert settings.VECTOR_DB == "qdrant"

def test_provider_switching():
    settings = Settings(LLM_PROVIDER="openrouter", VECTOR_DB="milvus")
    assert settings.LLM_PROVIDER == "openrouter"
    assert settings.VECTOR_DB == "milvus"

def test_vector_db_switching(monkeypatch):
    from app.config import get_settings
    
    # Qdrant test
    monkeypatch.setenv("VECTOR_DB", "qdrant")
    settings = Settings()
    monkeypatch.setattr("app.db.vector_store.get_settings", lambda: settings)
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    
    vs = get_vector_store()
    assert isinstance(vs, QdrantVectorStore)
    
    # Milvus test
    monkeypatch.setenv("VECTOR_DB", "milvus")
    settings_m = Settings()
    monkeypatch.setattr("app.db.vector_store.get_settings", lambda: settings_m)
    monkeypatch.setattr("app.config.get_settings", lambda: settings_m)
    
    vs = get_vector_store()
    assert isinstance(vs, MilvusVectorStore)

def test_relational_db_switching(monkeypatch):
    # Postgres
    monkeypatch.setenv("RELATIONAL_DB", "postgres")
    settings = Settings()
    monkeypatch.setattr("app.db.relational.get_settings", lambda: settings)
    engine = get_engine()
    assert "asyncpg" in str(engine.url)
    
    # MySQL
    monkeypatch.setenv("RELATIONAL_DB", "mysql")
    settings_m = Settings()
    monkeypatch.setattr("app.db.relational.get_settings", lambda: settings_m)
    engine = get_engine()
    assert "aiomysql" in str(engine.url)


def test_database_url_precedence_and_normalization():
    settings = Settings(
        DATABASE_URL="postgres://user:pass@host:5432/dbname",
        RELATIONAL_DB="postgres",
        POSTGRES_URL="postgresql+asyncpg://local:local@localhost/localdb"
    )
    assert settings.relational_url.startswith("postgresql+asyncpg://")
    assert "host:5432/dbname" in settings.relational_url


def test_database_url_postgresql_normalization():
    settings = Settings(DATABASE_URL="postgresql://user:pass@host:5432/dbname")
    assert settings.relational_url.startswith("postgresql+asyncpg://")


def test_database_url_mysql_passthrough():
    settings = Settings(DATABASE_URL="mysql+aiomysql://user:pass@host:3306/dbname")
    assert settings.relational_url == "mysql+aiomysql://user:pass@host:3306/dbname"


def test_cors_origins_parsing():
    settings = Settings(CORS_ALLOW_ORIGINS="https://a.com, https://b.com ,http://localhost:3000")
    assert settings.cors_allow_origins == ["https://a.com", "https://b.com", "http://localhost:3000"]


def test_qdrant_client_receives_api_key(monkeypatch):
    captured = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("qdrant_client.AsyncQdrantClient", DummyClient)
    settings = Settings(QDRANT_URL="https://qdrant.example", QDRANT_API_KEY="secret-key")
    monkeypatch.setattr("app.db.vector_store.get_settings", lambda: settings)

    _ = QdrantVectorStore()

    assert captured["url"] == "https://qdrant.example"
    assert captured["api_key"] == "secret-key"


def test_db_schema_default_public():
    settings = Settings()
    assert settings.db_schema == "public"


def test_db_schema_custom_value():
    settings = Settings(DB_SCHEMA="helpdesk_chatbot")
    assert settings.db_schema == "helpdesk_chatbot"


def test_db_schema_invalid_value_raises():
    settings = Settings(DB_SCHEMA="bad-schema-name")
    with pytest.raises(ValueError):
        _ = settings.db_schema


def test_engine_url_unchanged_with_default_schema(monkeypatch):
    settings = Settings(
        RELATIONAL_DB="postgres",
        POSTGRES_URL="postgresql+asyncpg://user:pass@localhost:5432/dbname",
        DB_SCHEMA="public",
    )
    monkeypatch.setattr("app.db.relational.get_settings", lambda: settings)
    engine = get_engine()
    assert str(engine.url) == "postgresql+asyncpg://user:***@localhost:5432/dbname"
