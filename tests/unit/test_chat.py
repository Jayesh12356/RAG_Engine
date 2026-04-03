import pytest
from app.chat.session import SessionManager
from app.chat.pipeline import ChatPipeline, ChatRequest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_session_manager_demo_create():
    manager = SessionManager(demo_mode=True)
    session_id = await manager.create_session()
    assert session_id is not None
    assert type(session_id) is str
    assert len(session_id) > 0

@pytest.mark.asyncio
async def test_session_manager_demo_add_and_get():
    manager = SessionManager(demo_mode=True)
    session_id = await manager.create_session()
    await manager.add_turn(session_id, "user", "how do I reset VPN?")
    await manager.add_turn(session_id, "assistant", "Open Pulse Secure...")
    history = await manager.get_history(session_id, limit=5)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"

@pytest.mark.asyncio
async def test_session_history_limit():
    manager = SessionManager(demo_mode=True)
    session_id = await manager.create_session()
    for i in range(10):
        await manager.add_turn(session_id, "user", f"question {i}")
    history = await manager.get_history(session_id, limit=5)
    assert len(history) == 5
    assert history[-1].content == "question 9"

from app.models.query import SearchResult
@pytest.mark.asyncio
async def test_chat_pipeline_demo_new_session():
    pipeline = ChatPipeline(demo_mode=True)
    pipeline.router.detect = AsyncMock()
    pipeline.router.detect.return_value.service_category = "test_category"
    pipeline.hybrid_search.search = AsyncMock()
    pipeline.hybrid_search.search.return_value = []
    
    mock_chunk1 = SearchResult(chunk_id="1", document_id="1", text="abc", score=0.9, metadata={"pdf_name": "x.pdf", "page_number": 1, "section_title": "x", "pdf_url": "x.pdf"})
    mock_chunk2 = SearchResult(chunk_id="2", document_id="1", text="def", score=0.9, metadata={"pdf_name": "y.pdf", "page_number": 2, "section_title": "y", "pdf_url": "y.pdf"})
    
    pipeline.reranker.rerank = AsyncMock()
    pipeline.reranker.rerank.return_value = [mock_chunk1, mock_chunk2]
    pipeline.llm_client.complete = AsyncMock()
    pipeline.llm_client.complete.return_value = "This is a test answer"
    
    request = ChatRequest(question="how do I reset VPN?")
    response = await pipeline.run(request)
    assert response.session_id is not None
    assert len(response.session_id) > 0
    assert response.refused is False
    assert len(response.history) >= 1

@pytest.mark.asyncio
async def test_chat_pipeline_history_injected():
    pipeline = ChatPipeline(demo_mode=True)
    pipeline.router.detect = AsyncMock()
    pipeline.router.detect.return_value.service_category = "test_category"
    pipeline.hybrid_search.search = AsyncMock()
    pipeline.hybrid_search.search.return_value = []
    pipeline.reranker.rerank = AsyncMock()
    pipeline.reranker.rerank.return_value = []
    session_id = await pipeline.session_manager.create_session()
    await pipeline.session_manager.add_turn(session_id, "user", "turn 1")
    await pipeline.session_manager.add_turn(session_id, "assistant", "ans 1")
    
    request = ChatRequest(session_id=session_id, question="what about the second step?")
    response = await pipeline.run(request)
    assert response.session_id == session_id
    assert len(response.history) >= 4

@pytest.mark.asyncio
async def test_chat_pipeline_confidence_gate():
    pipeline = ChatPipeline(demo_mode=True)
    pipeline.router.detect = AsyncMock()
    pipeline.router.detect.return_value.service_category = "test_category"
    pipeline.hybrid_search.search = AsyncMock()
    pipeline.hybrid_search.search.return_value = []
    pipeline.reranker.rerank = AsyncMock()
    pipeline.reranker.rerank.return_value = []
    pipeline.llm_client.complete = AsyncMock()
    pipeline.llm_client.complete.return_value = "i cannot answer this based on the provided documents"
    
    request = ChatRequest(question="weather in Paris?")
    response = await pipeline.run(request)
    assert response.refused is True
    assert response.confidence_label == "refused"
