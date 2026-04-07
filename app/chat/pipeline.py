import asyncio
import json
from typing import Optional, List
from pydantic import BaseModel
from app.chat.session import SessionManager, HistoryTurn
from app.models.query import SourceChunk
from app.query.router import QueryRouter
from app.query.hybrid_search import HybridSearch
from app.query.reranker import CohereReranker
from app.llm import client as llm_client
from app.config import get_settings

from app.query.rag_generator import (
    SYSTEM_PROMPT, _clean_answer, _score_confidence, build_user_prompt, REFUSAL_PHRASE, _extractive_fallback_answer
)

import structlog

logger = structlog.get_logger(__name__)
settings = get_settings()


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
    if len(chunks) > 1 and gap < settings.RELEVANCE_MIN_SCORE_GAP and top < 0.55:
        return False
    return True


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    question: str
    service_category: Optional[str] = None
    top_k: int = 20
    rerank_top_n: Optional[int] = None


class ChatResponse(BaseModel):
    session_id: str
    turn_id: str
    question: str
    answer: str
    confidence: float
    confidence_label: str
    sources: List[SourceChunk]
    service_category: str
    refused: bool
    history: List[HistoryTurn]


class ChatPipeline:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        self.session_manager = SessionManager(demo_mode=demo_mode)
        self.router = QueryRouter(demo_mode=demo_mode)
        self.hybrid_search = HybridSearch(demo_mode=demo_mode)
        self.reranker = CohereReranker(demo_mode=demo_mode)
        self.llm_client = llm_client

    def _confidence_label(self, confidence: float) -> str:
        if confidence <= 0.15:
            return "refused"
        if confidence >= 0.8:
            return "high"
        if confidence >= 0.6:
            return "moderate"
        return "low"

    def _build_history_block(self, history: List[HistoryTurn]) -> str:
        if not history:
            return ""
        history_block = "Previous conversation:\n"
        for turn in history:
            if turn.role == "user":
                history_block += f"User: {turn.content}\n"
            elif turn.role == "assistant":
                content = turn.content[:300] + "..." if len(turn.content) > 300 else turn.content
                history_block += f"Assistant: {content}\n"
        return history_block

    def _build_sources(self, results: list) -> List[SourceChunk]:
        sources = []
        for r in results:
            pdf_name = r.metadata.get("pdf_name", "Unknown")
            document_id = r.document_id or r.metadata.get("document_id", "")
            if document_id:
                pdf_url = f"/pdfs/by-id/{document_id}"
            else:
                # Backward-compatible fallback for old chunks missing document_id payload.
                pdf_url = f"/pdfs/{pdf_name}"
            sources.append(SourceChunk(
                chunk_id=r.chunk_id,
                text=r.text,
                pdf_name=pdf_name,
                pdf_url=pdf_url,
                page_number=r.metadata.get("page_number", 0),
                section_title=r.metadata.get("section_title", "Unknown"),
                score=r.score,
            ))
        return sources

    def _demo_answer(self, question: str, results: list) -> str:
        if not results:
            return REFUSAL_PHRASE
        top_text = results[0].text.strip()
        if not top_text:
            return REFUSAL_PHRASE
        if len(question.split()) <= 8:
            return top_text[:220]
        if len(results) > 1 and results[1].text.strip():
            return f"{top_text}\n\n- {results[1].text.strip()[:180]}"
        return top_text

    async def run(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id
        if session_id is None:
            session_id = await self.session_manager.create_session()
            logger.info("new_session_created", session_id=session_id)

        # GET History
        limit = settings.CHAT_HISTORY_TURNS
        history = await self.session_manager.get_history(session_id, limit=limit)

        # PARALLEL: router + search
        top_k = request.top_k
        router_task = self.router.detect(request.question)
        search_task = self.hybrid_search.search(
            request.question, request.service_category, top_k
        )
        router_result, search_results = await asyncio.gather(
            router_task, search_task
        )
        service_category = request.service_category or router_result.service_category

        # Rerank
        top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
        reranked_results = await self.reranker.rerank(request.question, search_results, top_n)

        unique_results = reranked_results

        sources = self._build_sources(unique_results)

        if not _has_sufficient_evidence(unique_results):
            answer = REFUSAL_PHRASE
            confidence = 0.15
        elif self.demo_mode:
            answer = self._demo_answer(request.question, unique_results)
            answer = _clean_answer(answer)
            confidence = _score_confidence(answer, unique_results)
        else:
            history_block = self._build_history_block(history)
            enriched_prompt = build_user_prompt(request.question, unique_results, history_block=history_block)
            try:
                answer = await self.llm_client.complete(enriched_prompt, SYSTEM_PROMPT)
            except Exception:
                answer = _extractive_fallback_answer(request.question, unique_results)
            answer = _clean_answer(answer)
            confidence = _score_confidence(answer, unique_results)

        # Refused flag + label
        confidence_label = self._confidence_label(confidence)
        refused = confidence_label == "refused"

        # Add user turn
        await self.session_manager.add_turn(
            session_id=session_id,
            role="user",
            content=request.question,
            question=request.question
        )

        sources_dict = [s.model_dump() for s in sources]

        # Add assistant turn
        turn_id = await self.session_manager.add_turn(
            session_id=session_id,
            role="assistant",
            content=answer,
            answer=answer,
            confidence=confidence,
            sources=sources_dict,
            service_category=service_category
        )

        # Get full history (after new turns)
        full_history = await self.session_manager.get_history(session_id, limit=limit)

        return ChatResponse(
            session_id=session_id,
            turn_id=turn_id,
            question=request.question,
            answer=answer,
            confidence=confidence,
            confidence_label=confidence_label,
            sources=sources,
            service_category=service_category or "general",
            refused=refused,
            history=full_history
        )

    async def run_stream(self, request: ChatRequest):
        try:
            session_id = request.session_id
            if session_id is None:
                session_id = await self.session_manager.create_session()
                logger.info("new_session_created_stream", session_id=session_id)

            limit = settings.CHAT_HISTORY_TURNS
            history = await self.session_manager.get_history(session_id, limit=limit)

            top_k = request.top_k
            router_task = self.router.detect(request.question)
            search_task = self.hybrid_search.search(request.question, request.service_category, top_k)
            router_result, search_results = await asyncio.gather(router_task, search_task)
            service_category = request.service_category or router_result.service_category

            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked_results = await self.reranker.rerank(request.question, search_results, top_n)
            sources = self._build_sources(reranked_results)

            if not _has_sufficient_evidence(reranked_results):
                answer = REFUSAL_PHRASE
                confidence = 0.15
            elif self.demo_mode:
                answer = self._demo_answer(request.question, reranked_results)
                answer = _clean_answer(answer)
                confidence = _score_confidence(answer, reranked_results)
            else:
                history_block = self._build_history_block(history)
                prompt = build_user_prompt(request.question, reranked_results, history_block=history_block)
                parts: list[str] = []
                try:
                    async for token in self.llm_client.complete_stream(prompt, SYSTEM_PROMPT):
                        parts.append(token)
                        yield f"data: {json.dumps({'type': 'delta', 'text': token})}\n\n"
                    answer = _clean_answer("".join(parts))
                except Exception:
                    answer = _extractive_fallback_answer(request.question, reranked_results)
                confidence = _score_confidence(answer, reranked_results)

            confidence_label = self._confidence_label(confidence)
            refused = confidence_label == "refused"
            if refused:
                sources = []

            await self.session_manager.add_turn(
                session_id=session_id,
                role="user",
                content=request.question,
                question=request.question,
            )
            sources_dict = [s.model_dump() for s in sources]
            turn_id = await self.session_manager.add_turn(
                session_id=session_id,
                role="assistant",
                content=answer,
                answer=answer,
                confidence=confidence,
                sources=sources_dict,
                service_category=service_category,
            )
            full_history = await self.session_manager.get_history(session_id, limit=limit)
            payload = ChatResponse(
                session_id=session_id,
                turn_id=turn_id,
                question=request.question,
                answer=answer,
                confidence=confidence,
                confidence_label=confidence_label,
                sources=sources,
                service_category=service_category or "general",
                refused=refused,
                history=full_history,
            )
            yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
        except Exception as e:
            logger.error("chat_pipeline_stream_error", error=str(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'chat streaming failed'})}\n\n"
