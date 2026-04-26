"""Chat pipeline (multi-turn conversational RAG).

Differences from ``QueryPipeline``:
- Persists turns through ``SessionManager``.
- Builds a short ``Previous conversation`` block to prefix the user prompt.
- Otherwise mirrors the same gating semantics: shared ``evidence_gate``,
  ``CONFIDENCE_THRESHOLD`` refusal, optional MMR + citations, no raw
  exceptions ever reach the wire.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from pydantic import BaseModel

from app.chat.session import HistoryTurn, SessionManager
from app.config import get_settings
from app.llm import client as llm_client
from app.llm.image_client import post_process_answer as _post_process_images
from app.models.query import Citation, SearchResult, SourceChunk
from app.query.diversify import diversify
from app.query.gates import confidence_label as confidence_label_fn
from app.query.gates import evidence_gate
from app.query.hybrid_search import HybridSearch
from app.query.pipeline import _ensure_section_anchor, _pii_pre_refusal
from app.query.rag_generator import (
    REFUSAL_PHRASE,
    _clean_answer,
    _extractive_fallback_answer,
    _score_confidence,
    build_citations,
    build_system_prompt,
    build_user_prompt,
)
from app.query.reranker import CohereReranker
from app.query.rewrite import maybe_rewrite_query
from app.query.router import QueryRouter

logger = structlog.get_logger(__name__)
settings = get_settings()


class ChatRequest(BaseModel):
    session_id: str | None = None
    question: str
    service_category: str | None = None
    top_k: int = 20
    rerank_top_n: int | None = None
    include_citations: bool | None = None


class ChatResponse(BaseModel):
    session_id: str
    turn_id: str
    question: str
    answer: str
    confidence: float
    confidence_label: str
    sources: list[SourceChunk]
    citations: list[Citation] = []
    service_category: str
    refused: bool
    history: list[HistoryTurn]
    visual_capable: bool = False


def _adjust_top_k(top_k: int, intent: str) -> int:
    s = get_settings()
    if intent == "troubleshoot":
        return top_k + s.INTENT_TROUBLESHOOT_TOP_K_BOOST
    if intent == "howto":
        return top_k + s.INTENT_HOWTO_TOP_K_BOOST
    return top_k


class ChatPipeline:
    def __init__(self, demo_mode: bool = False) -> None:
        self.demo_mode = demo_mode
        self.session_manager = SessionManager(demo_mode=demo_mode)
        self.router = QueryRouter(demo_mode=demo_mode)
        self.hybrid_search = HybridSearch(demo_mode=demo_mode)
        self.reranker = CohereReranker(demo_mode=demo_mode)
        self.llm_client = llm_client

    # ------------------------------------------------------------------ helpers
    def _build_history_block(self, history: list[HistoryTurn]) -> str:
        if not history:
            return ""
        block = "Previous conversation:\n"
        for turn in history:
            if turn.role == "user":
                block += f"User: {turn.content}\n"
            elif turn.role == "assistant":
                snippet = turn.content[:300] + "..." if len(turn.content) > 300 else turn.content
                block += f"Assistant: {snippet}\n"
        return block

    def _build_sources(self, results: list[SearchResult]) -> list[SourceChunk]:
        sources: list[SourceChunk] = []
        for r in results:
            pdf_name = r.metadata.get("pdf_name", "Unknown")
            document_id = r.document_id or r.metadata.get("document_id", "")
            pdf_url = f"/pdfs/by-id/{document_id}" if document_id else f"/pdfs/{pdf_name}"
            sources.append(
                SourceChunk(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    pdf_name=pdf_name,
                    pdf_url=pdf_url,
                    page_number=r.metadata.get("page_number", 0),
                    section_title=r.metadata.get("section_title", "Unknown"),
                    score=r.score,
                )
            )
        return sources

    def _demo_answer(self, question: str, results: list[SearchResult]) -> str:
        if not results:
            return REFUSAL_PHRASE
        top_text = (results[0].text or "").strip()
        if not top_text:
            return REFUSAL_PHRASE
        if len(question.split()) <= 8:
            return top_text[:220]
        if len(results) > 1 and (results[1].text or "").strip():
            return f"{top_text}\n\n- {results[1].text.strip()[:180]}"
        return top_text

    def _refusal_response(
        self,
        *,
        session_id: str,
        turn_id: str,
        question: str,
        service_category: str,
        confidence: float,
        history: list[HistoryTurn],
    ) -> ChatResponse:
        return ChatResponse(
            session_id=session_id,
            turn_id=turn_id,
            question=question,
            answer=REFUSAL_PHRASE,
            confidence=confidence,
            confidence_label="refused",
            sources=[],
            citations=[],
            service_category=service_category or "GENERAL",
            refused=True,
            history=history,
            visual_capable=settings.llm_is_visual_capable,
        )

    # ------------------------------------------------------------------ run
    async def run(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid.uuid4())
        session_id = request.session_id or await self.session_manager.create_session()
        if request.session_id is None:
            logger.info("chat_new_session", session_id=session_id, request_id=request_id)

        try:
            limit = settings.CHAT_HISTORY_TURNS
            history = await self.session_manager.get_history(session_id, limit=limit)

            top_k = request.top_k
            router_task = self.router.detect(request.question)
            search_task = self.hybrid_search.search(
                request.question, request.service_category, top_k
            )
            router_result, initial_search = await asyncio.gather(router_task, search_task)
            service_category = request.service_category or router_result.service_category

            # Optional query rewrite — only if initial signal is weak.
            top_score = initial_search[0].score if initial_search else None
            rewritten = await maybe_rewrite_query(request.question, top_score)
            search_question = rewritten if rewritten != request.question else request.question
            if rewritten != request.question:
                tuned_top_k = _adjust_top_k(top_k, router_result.intent)
                initial_search = await self.hybrid_search.search(
                    search_question, request.service_category, tuned_top_k
                )

            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked = await self.reranker.rerank(search_question, initial_search, top_n)
            unique_results = diversify(reranked, top_k=top_n)
            unique_results = _ensure_section_anchor(
                request.question, unique_results, initial_search
            )
            sources = self._build_sources(unique_results)

            pii_miss = _pii_pre_refusal(request.question, unique_results)
            verdict = evidence_gate(unique_results, question=request.question)
            include_citations = (
                request.include_citations
                if request.include_citations is not None
                else settings.INCLUDE_CITATIONS_DEFAULT
            )

            if pii_miss is not None:
                logger.warning(
                    "chat_pii_pre_refusal",
                    request_id=request_id,
                    intent=pii_miss,
                )
                sources = []
                answer = REFUSAL_PHRASE
                confidence = 0.10
                citations: list[Citation] = []
            elif not verdict.passed:
                logger.warning(
                    "chat_evidence_gate_failed",
                    request_id=request_id,
                    reason=verdict.reason,
                    top=verdict.top_score,
                    second=verdict.second_score,
                )
                answer = REFUSAL_PHRASE
                confidence = 0.10
                citations = []
            elif self.demo_mode:
                answer = _clean_answer(self._demo_answer(request.question, unique_results))
                confidence = _score_confidence(answer, unique_results)
                citations = build_citations(unique_results) if include_citations else []
            else:
                history_block = self._build_history_block(history)
                user_prompt = build_user_prompt(
                    request.question, unique_results, history_block=history_block
                )
                system_prompt = build_system_prompt(service_category)
                try:
                    answer = await self.llm_client.complete(user_prompt, system_prompt)
                except Exception as exc:
                    logger.error(
                        "chat_llm_failed",
                        request_id=request_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    answer = _extractive_fallback_answer(request.question, unique_results)
                    if answer == REFUSAL_PHRASE:
                        confidence = 0.10
                    else:
                        confidence = settings.EXTRACTIVE_FALLBACK_CONFIDENCE
                    answer = _clean_answer(answer)
                    citations = build_citations(unique_results) if include_citations else []
                    return await self._persist_and_respond(
                        request=request,
                        request_id=request_id,
                        session_id=session_id,
                        history_limit=limit,
                        answer=answer,
                        confidence=confidence,
                        sources=sources,
                        citations=citations,
                        service_category=service_category,
                    )

                answer = _clean_answer(answer)
                answer = _post_process_images(answer)
                confidence = _score_confidence(answer, unique_results)
                citations = build_citations(unique_results) if include_citations else []

            label = confidence_label_fn(confidence)
            if label == "refused":
                sources = []
                citations = []
                answer = REFUSAL_PHRASE if answer != REFUSAL_PHRASE else answer

            return await self._persist_and_respond(
                request=request,
                request_id=request_id,
                session_id=session_id,
                history_limit=limit,
                answer=answer,
                confidence=confidence,
                sources=sources,
                citations=citations,
                service_category=service_category,
            )

        except Exception as exc:
            logger.error(
                "chat_pipeline_error",
                request_id=request_id,
                session_id=session_id,
                error=str(exc),
                exc_info=True,
            )
            return self._refusal_response(
                session_id=session_id,
                turn_id="",
                question=request.question,
                service_category="GENERAL",
                confidence=0.0,
                history=[],
            )

    async def _persist_and_respond(
        self,
        *,
        request: ChatRequest,
        request_id: str,
        session_id: str,
        history_limit: int,
        answer: str,
        confidence: float,
        sources: list[SourceChunk],
        citations: list[Citation],
        service_category: str,
    ) -> ChatResponse:
        label = confidence_label_fn(confidence)
        refused = label == "refused"
        if refused:
            sources = []
            citations = []
            if answer != REFUSAL_PHRASE:
                answer = REFUSAL_PHRASE

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
        full_history = await self.session_manager.get_history(session_id, limit=history_limit)
        return ChatResponse(
            session_id=session_id,
            turn_id=turn_id,
            question=request.question,
            answer=answer,
            confidence=confidence,
            confidence_label=label,
            sources=sources,
            citations=citations,
            service_category=service_category or "GENERAL",
            refused=refused,
            history=full_history,
            visual_capable=settings.llm_is_visual_capable,
        )

    # ------------------------------------------------------------------ stream
    async def run_stream(self, request: ChatRequest):
        request_id = str(uuid.uuid4())
        try:
            session_id = request.session_id or await self.session_manager.create_session()
            if request.session_id is None:
                logger.info("chat_stream_new_session", session_id=session_id, request_id=request_id)

            limit = settings.CHAT_HISTORY_TURNS
            history = await self.session_manager.get_history(session_id, limit=limit)

            top_k = request.top_k
            router_task = self.router.detect(request.question)
            search_task = self.hybrid_search.search(
                request.question, request.service_category, top_k
            )
            router_result, initial_search = await asyncio.gather(router_task, search_task)
            service_category = request.service_category or router_result.service_category

            top_score = initial_search[0].score if initial_search else None
            rewritten = await maybe_rewrite_query(request.question, top_score)
            search_question = rewritten if rewritten != request.question else request.question
            if rewritten != request.question:
                tuned_top_k = _adjust_top_k(top_k, router_result.intent)
                initial_search = await self.hybrid_search.search(
                    search_question, request.service_category, tuned_top_k
                )

            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked = await self.reranker.rerank(search_question, initial_search, top_n)
            unique_results = diversify(reranked, top_k=top_n)
            unique_results = _ensure_section_anchor(
                request.question, unique_results, initial_search
            )
            sources = self._build_sources(unique_results)

            pii_miss_stream = _pii_pre_refusal(request.question, unique_results)

            include_citations = (
                request.include_citations
                if request.include_citations is not None
                else settings.INCLUDE_CITATIONS_DEFAULT
            )
            verdict = evidence_gate(unique_results, question=request.question)

            if pii_miss_stream is not None:
                logger.warning(
                    "chat_stream_pii_pre_refusal",
                    request_id=request_id,
                    intent=pii_miss_stream,
                )
                sources = []
                answer = REFUSAL_PHRASE
                confidence = 0.10
                citations: list[Citation] = []
            elif not verdict.passed:
                answer = REFUSAL_PHRASE
                confidence = 0.10
                citations = []
            elif self.demo_mode:
                answer = _clean_answer(self._demo_answer(request.question, unique_results))
                confidence = _score_confidence(answer, unique_results)
                citations = build_citations(unique_results) if include_citations else []
            else:
                history_block = self._build_history_block(history)
                user_prompt = build_user_prompt(
                    request.question, unique_results, history_block=history_block
                )
                system_prompt = build_system_prompt(service_category)
                parts: list[str] = []
                stream_failed = False
                try:
                    async for token in self.llm_client.complete_stream(user_prompt, system_prompt):
                        parts.append(token)
                        yield f"data: {json.dumps({'type': 'delta', 'text': token})}\n\n"
                except Exception as exc:
                    stream_failed = True
                    logger.error(
                        "chat_stream_llm_failed",
                        request_id=request_id,
                        error=str(exc),
                        exc_info=True,
                    )
                if parts and not stream_failed:
                    answer = _clean_answer("".join(parts))
                    answer = _post_process_images(answer)
                    confidence = _score_confidence(answer, unique_results)
                else:
                    fallback = _extractive_fallback_answer(request.question, unique_results)
                    answer = _clean_answer(fallback)
                    confidence = (
                        settings.EXTRACTIVE_FALLBACK_CONFIDENCE
                        if fallback != REFUSAL_PHRASE
                        else 0.10
                    )
                citations = build_citations(unique_results) if include_citations else []

            label = confidence_label_fn(confidence)
            refused = label == "refused"
            if refused:
                sources = []
                citations = []
                if answer != REFUSAL_PHRASE:
                    answer = REFUSAL_PHRASE

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
                confidence_label=label,
                sources=sources,
                citations=citations,
                service_category=service_category or "GENERAL",
                refused=refused,
                history=full_history,
                visual_capable=settings.llm_is_visual_capable,
            )
            yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
        except Exception as exc:
            logger.error(
                "chat_pipeline_stream_error",
                request_id=request_id,
                error=str(exc),
                exc_info=True,
            )
            yield f"data: {json.dumps({'type': 'error', 'message': 'chat streaming failed', 'request_id': request_id})}\n\n"


def _has_sufficient_evidence(chunks: list) -> bool:
    """Backwards-compatible helper retained for callers/tests.

    Prefer ``app.query.gates.evidence_gate`` for new code.
    """
    return evidence_gate(chunks).passed
