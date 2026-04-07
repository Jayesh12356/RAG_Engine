import asyncio
import json
import time
import structlog
from app.models.query import QueryRequest, QueryResponse, SourceChunk
from app.query.router import QueryRouter
from app.query.hybrid_search import HybridSearch
from app.query.reranker import CohereReranker
from app.query.rag_generator import RAGGenerator, build_user_prompt, _clean_answer, _score_confidence, SYSTEM_PROMPT, _extractive_fallback_answer
from app.llm import client as llm_client
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()
REFUSAL = "I don't have information on this topic in our documentation."


def _has_sufficient_evidence(chunks: list) -> bool:
    if not chunks:
        return False
    top = chunks[0].score
    second = chunks[1].score if len(chunks) > 1 else 0.0
    gap = top - second
    if top < 0.22:
        return False
    if len(chunks) > 1 and second < 0.12 and top < 0.50:
        return False
    if len(chunks) > 1 and gap < settings.RELEVANCE_MIN_SCORE_GAP and top < 0.50:
        return False
    return True

class QueryPipeline:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        self.router = QueryRouter(demo_mode=demo_mode)
        self.searcher = HybridSearch(demo_mode=demo_mode)
        self.reranker = CohereReranker(demo_mode=demo_mode)
        self.generator = RAGGenerator()

    def _build_sources(self, reranked_chunks: list) -> list[SourceChunk]:
        sources = []
        for chunk in reranked_chunks:
            pdf_name = chunk.payload.get("pdf_name", "unknown.pdf")
            document_id = chunk.document_id or chunk.payload.get("document_id", "")
            if document_id:
                pdf_url = f"/pdfs/by-id/{document_id}"
            else:
                # Backward-compatible fallback for old chunks missing document_id payload.
                pdf_url = f"/pdfs/{pdf_name}"
            sources.append(SourceChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                pdf_name=pdf_name,
                pdf_url=pdf_url,
                page_number=chunk.payload.get("page_number", 0),
                section_title=chunk.payload.get("section_title", "Unknown"),
                score=chunk.score,
            ))
        return sources

    def _label_confidence(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "high"
        if confidence >= 0.60:
            return "moderate"
        return "low"

    async def run(self, request: QueryRequest) -> QueryResponse:
        start_time = time.time()
        logger.info("pipeline_start", question=request.question)
        
        try:
            # STEP 1+2: Router + Search in PARALLEL (router is instant now)
            top_k = request.top_k or settings.MAX_CHUNKS_RETURN
            router_task = self.router.detect(request.question)
            search_task = self.searcher.search(
                request.question,
                request.service_category,  # use explicit category if provided
                top_k
            )
            router_result, search_results = await asyncio.gather(
                router_task, search_task
            )
            service_category = request.service_category or router_result.service_category
            
            if not search_results:
                return QueryResponse(
                    question=request.question,
                    answer=REFUSAL,
                    confidence=0.0,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category,
                    refused=True
                )
                
            # STEP 3: Rerank
            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked_chunks = await self.reranker.rerank(request.question, search_results, top_n)
            
            # STEP 4: RAG generation
            if not _has_sufficient_evidence(reranked_chunks):
                logger.warning("pipeline_evidence_gate_failed")
                return QueryResponse(
                    question=request.question,
                    answer=REFUSAL,
                    confidence=0.15,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category,
                    refused=True
                )

            generation = await self.generator.generate(request.question, reranked_chunks, service_category)
            
            # STEP 5: Confidence gate
            if generation.confidence < settings.CONFIDENCE_THRESHOLD:
                logger.warning("pipeline_confidence_gate_failed", confidence=generation.confidence)
                return QueryResponse(
                    question=request.question,
                    answer=REFUSAL,
                    confidence=generation.confidence,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category,
                    refused=True
                )
                
            # STEP 6: Build sources
            sources = self._build_sources(reranked_chunks)
            # STEP 7: Confidence label
            confidence_label = self._label_confidence(generation.confidence)
            
            # STEP 8: Return
            elapsed = time.time() - start_time
            logger.info("pipeline_complete", elapsed_sec=round(elapsed, 3), num_sources=len(sources))
            return QueryResponse(
                question=request.question,
                answer=generation.answer,
                confidence=generation.confidence,
                confidence_label=confidence_label,
                sources=sources,
                service_category=service_category,
                refused=False
            )
            
        except Exception as e:
            logger.error("pipeline_error", error=str(e), exc_info=True)
            return QueryResponse(
                question=request.question,
                answer=str(e),
                confidence=0.0,
                confidence_label="refused",
                sources=[],
                service_category="GENERAL",
                refused=True
            )

    async def run_stream(self, request: QueryRequest):
        try:
            top_k = request.top_k or settings.MAX_CHUNKS_RETURN
            router_task = self.router.detect(request.question)
            search_task = self.searcher.search(request.question, request.service_category, top_k)
            router_result, search_results = await asyncio.gather(router_task, search_task)
            service_category = request.service_category or router_result.service_category

            if not search_results:
                final_payload = QueryResponse(
                    question=request.question,
                    answer=REFUSAL,
                    confidence=0.0,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category,
                    refused=True,
                )
                yield f"data: {json.dumps({'type': 'final', 'payload': final_payload.model_dump()})}\n\n"
                return

            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked_chunks = await self.reranker.rerank(request.question, search_results, top_n)
            if not _has_sufficient_evidence(reranked_chunks):
                final_payload = QueryResponse(
                    question=request.question,
                    answer=REFUSAL,
                    confidence=0.15,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category,
                    refused=True,
                )
                yield f"data: {json.dumps({'type': 'final', 'payload': final_payload.model_dump()})}\n\n"
                return

            prompt = build_user_prompt(request.question, reranked_chunks)
            parts: list[str] = []
            try:
                async for token in llm_client.complete_stream(prompt=prompt, system=SYSTEM_PROMPT):
                    parts.append(token)
                    yield f"data: {json.dumps({'type': 'delta', 'text': token})}\n\n"
                answer = _clean_answer("".join(parts))
            except Exception:
                answer = _extractive_fallback_answer(request.question, reranked_chunks)
            confidence = _score_confidence(answer, reranked_chunks)
            if confidence < settings.CONFIDENCE_THRESHOLD:
                final_payload = QueryResponse(
                    question=request.question,
                    answer=REFUSAL,
                    confidence=confidence,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category,
                    refused=True,
                )
            else:
                final_payload = QueryResponse(
                    question=request.question,
                    answer=answer,
                    confidence=confidence,
                    confidence_label=self._label_confidence(confidence),
                    sources=self._build_sources(reranked_chunks),
                    service_category=service_category,
                    refused=False,
                )
            yield f"data: {json.dumps({'type': 'final', 'payload': final_payload.model_dump()})}\n\n"
        except Exception as e:
            safe_error = str(e).encode("ascii", errors="ignore").decode("ascii")
            logger.error("pipeline_stream_error", error=safe_error, exc_info=True)
            payload = QueryResponse(
                question=request.question,
                answer=REFUSAL,
                confidence=0.0,
                confidence_label="refused",
                sources=[],
                service_category="GENERAL",
                refused=True,
            )
            yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
