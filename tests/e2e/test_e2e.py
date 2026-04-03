import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
import json
import os

from app.main import app as main_app
from app.config import get_settings

def create_test_app():
    return main_app

@pytest_asyncio.fixture
async def e2e_client():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.db.relational import Base
    
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    
    with patch("app.db.relational.get_engine", return_value=test_engine), \
         patch("app.db.relational.get_session_maker", return_value=test_session_maker), \
         patch("app.api.routes.session_maker", test_session_maker):
         
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        app = create_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

@pytest_asyncio.fixture
async def mock_externals():
    settings = get_settings()
    
    class MockVectorStore:
        def __init__(self):
            self.store = {}
        async def upsert(self, collection, id, vector, payload=None):
            self.store[id] = payload
        async def hybrid_search(self, collection, dense_vec, sparse_vec, top_k, filter=None):
            from app.models.query import SearchResult
            chunk = SearchResult(
                chunk_id="chunk1",
                document_id="doc1",
                text="Mocked text",
                score=0.95,
                metadata={"pdf_name": "VPN_Setup_Guide.pdf", "page_number": 1, "section_title": "Setup"}
            )
            return [chunk, chunk, chunk]
        async def delete(self, collection, chunk_ids):
            return 1
        async def ensure_collection(self, name, dim):
            pass

    mock_vs = MockVectorStore()

    with patch("app.llm.client.embed", new_callable=AsyncMock) as m_embed, \
         patch("app.llm.client.complete", new_callable=AsyncMock) as m_complete, \
         patch("app.query.reranker.CohereReranker.rerank", new_callable=AsyncMock) as m_rerank, \
         patch("app.api.routes.get_vector_store", return_value=mock_vs), \
         patch("app.query.hybrid_search.get_vector_store", return_value=mock_vs), \
         patch("app.ingestion.pipeline.get_vector_store", return_value=mock_vs):
         
        m_embed.return_value = [[0.1] * settings.EMBEDDING_DIM]
        m_complete.return_value = '{"answer": "Mocked answer", "confidence": 0.9, "refused": false, "sources": []}'
        
        from app.models.query import SearchResult
        chunk = SearchResult(chunk_id="chunk1", document_id="doc1", text="Mocked text", score=0.95, metadata={"pdf_name": "VPN_Setup_Guide.pdf", "page_number": 1, "section_title": "Setup"})
        m_rerank.return_value = [chunk, chunk, chunk]
        
        yield mock_vs, m_complete

@pytest.mark.asyncio
async def test_e2e_ingest_then_query(e2e_client, mock_externals):
    mock_vs, m_complete = mock_externals
    
    with open("data/sample_pdfs/VPN_Setup_Guide.pdf", "rb") as f:
        file_content = f.read()
    files = {"file": ("VPN_Setup_Guide.pdf", file_content, "application/pdf")}
    
    resp1 = await e2e_client.post("/ingest", files=files)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "success"
    assert data1["total_chunks"] > 0
    
    m_complete.return_value = '{"answer": "Use the VPN key", "confidence": 0.9, "refused": false, "sources": [{"chunk_id": "chunk1", "pdf_name": "VPN_Setup_Guide.pdf", "page_number": 1, "section_title": "", "score": 0.9, "text": ""}]}'
    
    resp2 = await e2e_client.post("/query", json={"question": "How do I reset my VPN password?"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["refused"] is False
    assert data2["confidence"] >= 0.6
    assert len(data2["sources"]) > 0
    assert data2["sources"][0]["pdf_name"] == "VPN_Setup_Guide.pdf"

@pytest.mark.asyncio
async def test_e2e_health_reflects_config(e2e_client):
    settings = get_settings()
    resp = await e2e_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == settings.LLM_PROVIDER
    assert data["vector_db"] == settings.VECTOR_DB

@pytest.mark.asyncio
async def test_e2e_document_lifecycle(e2e_client, mock_externals):
    with open("data/sample_pdfs/VPN_Setup_Guide.pdf", "rb") as f:
        file_content = f.read()
    files = {"file": ("VPN_Setup_Guide.pdf", file_content, "application/pdf")}
    
    resp1 = await e2e_client.post("/ingest", files=files)
    doc_id = resp1.json()["document_id"]
    
    resp2 = await e2e_client.get("/documents")
    assert any(d["document_id"] == doc_id for d in resp2.json()["documents"])
    
    resp3 = await e2e_client.get(f"/documents/{doc_id}/chunks")
    assert len(resp3.json()["chunks"]) > 0
    
    resp4 = await e2e_client.delete(f"/documents/{doc_id}")
    assert resp4.json()["status"] == "deleted"
    
    resp5 = await e2e_client.get("/documents")
    assert not any(d["document_id"] == doc_id for d in resp5.json()["documents"])

@pytest.mark.asyncio
async def test_e2e_confidence_gate_fires(e2e_client, mock_externals):
    mock_vs, m_complete = mock_externals
    m_complete.return_value = "I don't have information on this topic in our documentation."
    
    resp = await e2e_client.post("/query", json={"question": "what is the weather in Paris?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["confidence_label"] == "refused"
    assert data["sources"] == []

@pytest.mark.asyncio
async def test_e2e_demo_mode_header(e2e_client, mock_externals):
    mock_vs, m_complete = mock_externals
    
    with open("data/sample_pdfs/VPN_Setup_Guide.pdf", "rb") as f:
        file_content = f.read()
    files = {"file": ("VPN_Setup_Guide.pdf", file_content, "application/pdf")}
    headers = {"X-Demo-Mode": "true"}
    resp1 = await e2e_client.post("/ingest", files=files, headers=headers)
    assert resp1.status_code == 200
    
    resp2 = await e2e_client.post("/query", json={"question": "hello"}, headers=headers)
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_e2e_ingest_scanned_pdf_with_ocr_route(e2e_client, mock_externals):
    scanned_pdf_path = "image_pdfs/Increase_Laptop_Battery.pdf"
    if not os.path.exists(scanned_pdf_path):
        pytest.skip("image_pdfs sample is not available in this environment")

    with patch("app.ingestion.pdf_parser._detect_pdf_type", return_value=("image_pdf", {1})), \
         patch(
            "app.ingestion.pdf_parser.extract_page_text_with_ocr",
            return_value={
                "text": "Scanned page text from OCR",
                "confidence": 0.9,
                "used_vision": False,
                "fallback_attempted": False,
            },
         ):
        with open(scanned_pdf_path, "rb") as f:
            file_content = f.read()
        files = {"file": ("Increase_Laptop_Battery.pdf", file_content, "application/pdf")}
        resp = await e2e_client.post("/ingest", files=files)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "success"
    assert payload["total_chunks"] > 0

def test_e2e_provider_switching_config():
    with patch.dict("os.environ", {"VECTOR_DB": "qdrant"}):
        from app.config import get_settings
        from app.db.vector_store import get_vector_store, QdrantVectorStore
        get_settings.cache_clear()
        assert isinstance(get_vector_store(), QdrantVectorStore)
        
    with patch.dict("os.environ", {"VECTOR_DB": "milvus"}):
        get_settings.cache_clear()
        from app.db.vector_store import get_vector_store, MilvusVectorStore
        assert isinstance(get_vector_store(), MilvusVectorStore)
        
    with patch.dict("os.environ", {"RELATIONAL_DB": "mysql"}):
        get_settings.cache_clear()
        from app.db.relational import get_engine
        engine = get_engine()
        assert "aiomysql" in str(engine.url)
        
    with patch.dict("os.environ", {"LLM_PROVIDER": "groq"}):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.LLM_PROVIDER == "groq"
