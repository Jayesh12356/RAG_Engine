import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.query.router import QueryRouter
from app.query.hybrid_search import HybridSearch
from app.query.reranker import CohereReranker
from app.query.rag_generator import RAGGenerator, GenerationResult, build_user_prompt, REFUSAL_PHRASE
from app.query.pipeline import QueryPipeline
from app.models.query import SearchResult, QueryRequest
from app.config import get_settings

settings = get_settings()

@pytest.mark.asyncio
async def test_router_demo_vpn():
    router = QueryRouter(demo_mode=True)
    result = await router.detect("how do I reset my VPN password?")
    assert result.service_category == "VPN"
    assert len(result.intent) > 0
    assert "vpn" in result.key_terms

@pytest.mark.asyncio
async def test_router_demo_general():
    router = QueryRouter(demo_mode=True)
    result = await router.detect("hello")
    assert result.service_category == "GENERAL"

@pytest.mark.asyncio
async def test_hybrid_search_demo():
    searcher = HybridSearch(demo_mode=True)
    results = await searcher.search("vpn password", "VPN", top_k=20)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)

@pytest.mark.asyncio
async def test_reranker_demo():
    reranker = CohereReranker(demo_mode=True)
    mock_results = [
        SearchResult(chunk_id="1", document_id="d1", text="text1", score=0.9),
        SearchResult(chunk_id="2", document_id="d2", text="text2", score=0.8),
        SearchResult(chunk_id="3", document_id="d3", text="text3", score=0.7)
    ]
    results = await reranker.rerank("vpn", mock_results, top_n=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score

@pytest.mark.asyncio
@patch("app.query.rag_generator.llm_client.complete", new_callable=AsyncMock)
async def test_rag_generator_refusal(mock_complete):
    mock_complete.return_value = "I don't have information on this topic in our documentation."
    generator = RAGGenerator()
    result = await generator.generate("unknown question", [], "GENERAL")
    assert result.confidence < settings.CONFIDENCE_THRESHOLD

@pytest.mark.asyncio
@patch("app.query.pipeline.RAGGenerator.generate", new_callable=AsyncMock)
async def test_pipeline_demo_success(mock_generate):
    mock_generate.return_value = GenerationResult(answer="Open Pulse Secure...", confidence=0.91)
    
    pipeline = QueryPipeline(demo_mode=True)
    request = QueryRequest(question="how do I reset my VPN password?")
    response = await pipeline.run(request)
    
    assert response.refused == False
    assert response.confidence >= 0.6
    assert len(response.sources) > 0
    assert response.sources[0].pdf_url.startswith("/pdfs/by-id/")

@pytest.mark.asyncio
@patch("app.query.pipeline.RAGGenerator.generate", new_callable=AsyncMock)
async def test_pipeline_confidence_gate(mock_generate):
    mock_generate.return_value = GenerationResult(answer="...", confidence=0.3)
    
    pipeline = QueryPipeline(demo_mode=True)
    request = QueryRequest(question="anything")
    response = await pipeline.run(request)
    
    assert response.refused == True
    assert response.confidence_label == "refused"


def test_build_user_prompt_short_mode():
    chunks = [SearchResult(chunk_id="1", document_id="d1", text="VPN uses MFA.", score=0.9)]
    prompt = build_user_prompt("What is VPN?", chunks)
    assert "Expected answer length: SHORT" in prompt


def test_build_user_prompt_long_mode():
    chunks = [SearchResult(chunk_id="1", document_id="d1", text="Reset steps...", score=0.9)]
    prompt = build_user_prompt("How do I reset my VPN password step by step?", chunks)
    assert "Expected answer length: LONG" in prompt


def test_source_url_fallback_for_missing_document_id():
    from app.query.pipeline import QueryPipeline

    class DummyChunk:
        chunk_id = "c1"
        document_id = ""
        text = "text"
        score = 0.9
        payload = {"pdf_name": "legacy.pdf", "page_number": 1, "section_title": "S"}

    sources = QueryPipeline(demo_mode=True)._build_sources([DummyChunk()])
    assert len(sources) == 1
    assert sources[0].pdf_url == "/pdfs/legacy.pdf"


@pytest.mark.asyncio
@patch("app.query.pipeline.CohereReranker.rerank", new_callable=AsyncMock)
@patch("app.query.pipeline.HybridSearch.search", new_callable=AsyncMock)
@patch("app.query.pipeline.QueryRouter.detect", new_callable=AsyncMock)
async def test_pipeline_relevance_gate_refusal(mock_detect, mock_search, mock_rerank):
    mock_detect.return_value = MagicMock(service_category="GENERAL")
    mock_search.return_value = [SearchResult(chunk_id="1", document_id="d1", text="weak", score=0.20)]
    mock_rerank.return_value = [SearchResult(chunk_id="1", document_id="d1", text="weak", score=0.20)]
    pipeline = QueryPipeline(demo_mode=True)
    request = QueryRequest(question="unknown policy")
    response = await pipeline.run(request)
    assert response.refused is True
    assert response.answer == REFUSAL_PHRASE
