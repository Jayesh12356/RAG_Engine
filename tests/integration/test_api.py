import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app
from app.ingestion.pipeline import IngestionResult
from app.models.query import QueryResponse

import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data

@pytest.mark.asyncio
async def test_ingest_rejects_non_pdf(client):
    file_content = b"Not a PDF"
    files = {"file": ("test.txt", file_content, "text/plain")}
    response = await client.post("/ingest", files=files)
    assert response.status_code == 400

@pytest.mark.asyncio
@patch("app.api.routes.IngestPipeline")
async def test_ingest_success_demo(mock_pipeline_class, client):
    mock_pipeline = mock_pipeline_class.return_value
    mock_pipeline.run = AsyncMock(return_value=IngestionResult(
        document_id="doc1",
        pdf_name="test.pdf",
        total_pages=5,
        total_chunks=10,
        service_name="VPN",
        status="success",
        error=None
    ))
    
    file_content = b"PDF dummy content"
    files = {"file": ("test.pdf", file_content, "application/pdf")}
    headers = {"X-Demo-Mode": "true"}
    
    response = await client.post("/ingest", files=files, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_chunks"] == 10

@pytest.mark.asyncio
@patch("app.api.routes.QueryPipeline")
async def test_query_success_demo(mock_pipeline_class, client):
    mock_pipeline = mock_pipeline_class.return_value
    mock_pipeline.run = AsyncMock(return_value=QueryResponse(
        question="how do I reset VPN password?",
        answer="Open Pulse...",
        confidence=0.91,
        confidence_label="high",
        sources=[],
        service_category="VPN",
        refused=False
    ))
    
    payload = {"question": "how do I reset VPN password?"}
    headers = {"X-Demo-Mode": "true"}
    
    response = await client.post("/query", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is False
    assert data["confidence"] == 0.91

@pytest.mark.asyncio
@patch("app.api.routes.QueryPipeline")
async def test_query_refused(mock_pipeline_class, client):
    mock_pipeline = mock_pipeline_class.return_value
    mock_pipeline.run = AsyncMock(return_value=QueryResponse(
        question="what is the meaning of life?",
        answer="I don't have information...",
        confidence=0.3,
        confidence_label="refused",
        sources=[],
        service_category="GENERAL",
        refused=True
    ))
    
    payload = {"question": "what is the meaning of life?"}
    response = await client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["refused"] is True


@pytest.mark.asyncio
@patch("app.api.routes.QueryPipeline")
async def test_query_stream_returns_events(mock_pipeline_class, client):
    async def stream_gen(_request):
        yield 'data: {"type":"delta","text":"Hello"}\n\n'
        yield 'data: {"type":"final","payload":{"question":"q","answer":"Hello","confidence":0.9,"confidence_label":"high","sources":[],"service_category":"GENERAL","refused":false}}\n\n'

    mock_pipeline = mock_pipeline_class.return_value
    mock_pipeline.run_stream = stream_gen
    payload = {"question": "hello"}
    response = await client.post("/query/stream", json=payload)
    assert response.status_code == 200
    assert 'data: {"type":"delta","text":"Hello"}' in response.text
    assert '"type":"final"' in response.text

@pytest.mark.asyncio
@patch("app.api.routes.session_maker")
async def test_documents_list_empty(mock_session_maker, client):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    response = await client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["documents"] == []

@pytest.mark.asyncio
async def test_pdf_not_found(client):
    response = await client.get("/pdfs/nonexistent.pdf")
    assert response.status_code == 404

@pytest.mark.asyncio
@patch("app.api.routes.session_maker")
async def test_delete_document_not_found(mock_session_maker, client):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    response = await client.delete("/documents/nonexistent-id")
    assert response.status_code == 404
