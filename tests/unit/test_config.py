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
