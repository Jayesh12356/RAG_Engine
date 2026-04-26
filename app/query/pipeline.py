"""Single-shot Q&A pipeline.

The pipeline is intentionally linear and idempotent — each step has a
single responsibility, and every failure path returns a clean
``QueryResponse`` (never raises to the route handler).

Stages:
    1. Router + initial hybrid search (parallel)
    2. Optional LLM query rewrite when initial signal is weak
    3. Reranker (Cohere with lexical fallback)
    4. Diversification: per-document cap + MMR
    5. Evidence gate
    6. RAG generation (or extractive fallback)
    7. Confidence gate
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid

import structlog

from app.config import get_settings
from app.llm import client as llm_client
from app.llm.image_client import post_process_answer as _post_process_images
from app.models.query import (
    Citation,
    QueryRequest,
    QueryResponse,
    SearchResult,
    SourceChunk,
)
from app.query.diversify import diversify
from app.query.gates import confidence_label as confidence_label_fn
from app.query.gates import evidence_gate
from app.query.hybrid_search import HybridSearch
from app.query.rag_generator import (
    REFUSAL_PHRASE,
    RAGGenerator,
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
REFUSAL = REFUSAL_PHRASE


def _adjust_top_k(top_k: int, intent: str) -> int:
    s = get_settings()
    if intent == "troubleshoot":
        return top_k + s.INTENT_TROUBLESHOOT_TOP_K_BOOST
    if intent == "howto":
        return top_k + s.INTENT_HOWTO_TOP_K_BOOST
    return top_k


# ── Section-anchor recall ────────────────────────────────────────────────
# Cohere's reranker performs poorly on terse, header-heavy documents (CVs,
# datasheets, formal SOPs) where a single section header carries the entire
# answer to a noun-asked question ("list his projects", "education?",
# "what certifications?"). We compensate at the pipeline level: after
# rerank+diversify, if the question explicitly references one of these
# canonical section nouns, ensure at least one chunk whose first ~60 chars
# begin with that header is in the LLM's context — even if the reranker
# scored it low. Bounded so noise never dominates.
_SECTION_NOUN_ALIASES: dict[str, tuple[str, ...]] = {
    "projects":       ("project",),
    "education":      ("education", "educational"),
    "skills":         ("skill",),
    "experience":     ("experience", "work"),
    "summary":        ("summary", "profile"),
    "certifications": ("certificat",),
    "languages":      ("language",),
    "competencies":   ("competenc",),
    "publications":   ("publication",),
    "achievements":   ("achievement", "award"),
}


def _ensure_section_anchor(
    question: str,
    diversified: list[SearchResult],
    all_hits: list[SearchResult],
    max_extra: int = 3,
) -> list[SearchResult]:
    """Append section-header chunks the reranker missed.

    Looks at the question for canonical section nouns ("projects",
    "education", "skills", ...). For each noun present, if no diversified
    chunk's first 60 chars begin with the matching header (e.g. "PROJECTS"),
    pull the highest-scored hybrid-search chunk whose header matches into the
    context. Adds at most ``max_extra`` chunks total so noise stays bounded.
    """
    q_lower = (question or "").lower()
    target_headers: list[str] = []
    for header, aliases in _SECTION_NOUN_ALIASES.items():
        if any(alias in q_lower for alias in aliases):
            target_headers.append(header)
    if not target_headers:
        return diversified

    seen_ids = {(c.chunk_id or "") for c in diversified}
    have_header = {
        h for h in target_headers
        if any(h in (c.text or "")[:60].lower() for c in diversified)
    }
    missing_headers = [h for h in target_headers if h not in have_header]
    if not missing_headers:
        return diversified

    extras: list[SearchResult] = []
    for hit in all_hits:
        if (hit.chunk_id or "") in seen_ids:
            continue
        head = (hit.text or "")[:60].lower()
        match = next((h for h in missing_headers if h in head), None)
        if match is not None:
            extras.append(hit)
            missing_headers = [h for h in missing_headers if h != match]
            if len(extras) >= max_extra or not missing_headers:
                break

    if not extras:
        return diversified
    logger.info(
        "pipeline_section_anchor_recall",
        question=question,
        added=[(e.chunk_id, (e.text or "")[:60]) for e in extras],
    )
    return list(diversified) + extras


# ── PII precision pre-refusal ────────────────────────────────────────────
# When a question asks for highly specific personal identifiers (home/full
# street address, exact salary, phone number, date-of-birth, account/ID),
# even a strong RAG model is tempted to extrapolate from incidental partial
# data ("Panvel, Navi Mumbai, India" → claimed as a "home address"). The
# system prompt forbids this, but prompts are advisory; this is the hard
# guard rail. If the question maps to a PII intent and *no* retrieved chunk
# contains the structural marker for that PII (e.g. PIN/postal code for an
# address, currency figure for a salary), we refuse before reaching the LLM.
_PII_INTENTS: tuple[tuple[str, tuple[str, ...], re.Pattern[str]], ...] = (
    (
        "home_address",
        ("home address", "residential address", "full address", "street address"),
        # 6-digit PIN or 5-digit ZIP plus any of: house/flat/door, road/street/lane,
        # or a numbered street like "12 Foo Lane".
        re.compile(
            r"\b\d{6}\b"
            r"|\b\d{5}\b"
            r"|\b(?:house|flat|door|plot)\s*(?:no\.?|number)?\s*[\w\-/]+\b"
            r"|\b\d+[\w\-/]*\s+(?:road|street|lane|marg|avenue|boulevard|sector)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exact_salary",
        ("exact salary", "current salary", "ctc", "annual ctc", "take home", "in-hand salary"),
        re.compile(
            r"(?:rs\.?|inr|usd|eur|gbp|\$|₹|€|£)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lac|lakh|lakhs|cr|crore|k|m|mn|million|bn|billion))?\b"
            r"|\b\d[\d,]*\s*(?:lac|lakh|lakhs|cr|crore|lpa|usd|inr|per\s+annum|/year|/yr)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "phone_number",
        ("phone number", "mobile number", "contact number", "cell number"),
        re.compile(r"(?:\+?\d[\d\s\-().]{8,}\d)"),
    ),
    (
        "date_of_birth",
        ("date of birth", "birthday", "dob "),
        re.compile(
            r"\b\d{1,2}[/\-\s](?:0?[1-9]|1[0-2]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[/\-\s]\d{2,4}\b"
            r"|\b\d{4}-\d{2}-\d{2}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "id_account",
        ("aadhaar", "aadhar", "pan number", "passport number", "account number", "ssn"),
        re.compile(r"\b[A-Z0-9]{4,}\b"),
    ),
)


def _pii_pre_refusal(question: str, chunks: list[SearchResult]) -> str | None:
    """Return the matched PII intent name when the question asks for a strict
    PII value but no chunk carries the structural marker. ``None`` otherwise.
    """
    if not question:
        return None
    q_lower = question.lower()
    matched_intent: str | None = None
    matched_pattern: re.Pattern[str] | None = None
    for intent_name, triggers, pattern in _PII_INTENTS:
        if any(t in q_lower for t in triggers):
            matched_intent = intent_name
            matched_pattern = pattern
            break
    if matched_intent is None or matched_pattern is None:
        return None
    for ch in chunks:
        text = ch.text or ""
        if matched_pattern.search(text):
            return None
    return matched_intent


class QueryPipeline:
    def __init__(self, demo_mode: bool = False) -> None:
        self.demo_mode = demo_mode
        self.router = QueryRouter(demo_mode=demo_mode)
        self.searcher = HybridSearch(demo_mode=demo_mode)
        self.reranker = CohereReranker(demo_mode=demo_mode)
        self.generator = RAGGenerator()

    # ------------------------------------------------------------------ helpers
    def _build_sources(self, reranked_chunks: list[SearchResult]) -> list[SourceChunk]:
        sources: list[SourceChunk] = []
        for chunk in reranked_chunks:
            pdf_name = chunk.payload.get("pdf_name", "unknown.pdf")
            document_id = chunk.document_id or chunk.payload.get("document_id", "")
            pdf_url = f"/pdfs/by-id/{document_id}" if document_id else f"/pdfs/{pdf_name}"
            sources.append(
                SourceChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    pdf_name=pdf_name,
                    pdf_url=pdf_url,
                    page_number=chunk.payload.get("page_number", 0),
                    section_title=chunk.payload.get("section_title", "Unknown"),
                    score=chunk.score,
                )
            )
        return sources

    def _refusal_response(
        self,
        request: QueryRequest,
        confidence: float,
        service_category: str,
    ) -> QueryResponse:
        return QueryResponse(
            question=request.question,
            answer=REFUSAL_PHRASE,
            confidence=confidence,
            confidence_label="refused",
            sources=[],
            citations=[],
            service_category=service_category or "GENERAL",
            refused=True,
            visual_capable=settings.llm_is_visual_capable,
        )

    # ------------------------------------------------------------------ run
    async def run(self, request: QueryRequest) -> QueryResponse:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        logger.info("pipeline_start", request_id=request_id, question=request.question)

        try:
            top_k = request.top_k or settings.MAX_CHUNKS_RETURN
            router_task = self.router.detect(request.question)
            search_task = self.searcher.search(
                request.question, request.service_category, top_k
            )
            router_result, initial_search = await asyncio.gather(router_task, search_task)
            service_category = request.service_category or router_result.service_category

            if not initial_search:
                return self._refusal_response(request, 0.0, service_category)

            top_score = initial_search[0].score
            rewritten = await maybe_rewrite_query(request.question, top_score)
            search_question = rewritten if rewritten != request.question else request.question
            if rewritten != request.question:
                tuned_top_k = _adjust_top_k(top_k, router_result.intent)
                initial_search = await self.searcher.search(
                    search_question, request.service_category, tuned_top_k
                )
                if not initial_search:
                    return self._refusal_response(request, 0.0, service_category)

            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked_chunks = await self.reranker.rerank(search_question, initial_search, top_n)
            unique_chunks = diversify(reranked_chunks, top_k=top_n)
            unique_chunks = _ensure_section_anchor(
                request.question, unique_chunks, initial_search
            )

            pii_miss = _pii_pre_refusal(request.question, unique_chunks)
            if pii_miss is not None:
                logger.warning(
                    "pipeline_pii_pre_refusal",
                    request_id=request_id,
                    intent=pii_miss,
                )
                return self._refusal_response(request, 0.10, service_category)

            verdict = evidence_gate(unique_chunks, question=request.question)
            if not verdict.passed:
                logger.warning(
                    "pipeline_evidence_gate_failed",
                    request_id=request_id,
                    reason=verdict.reason,
                    top=verdict.top_score,
                    second=verdict.second_score,
                )
                return self._refusal_response(request, 0.10, service_category)
            logger.info(
                "pipeline_evidence_gate_passed",
                request_id=request_id,
                reason=verdict.reason,
                top=verdict.top_score,
                second=verdict.second_score,
            )

            generation = await self.generator.generate(
                request.question, unique_chunks, service_category
            )

            if generation.confidence < settings.CONFIDENCE_THRESHOLD:
                logger.warning(
                    "pipeline_confidence_gate_failed",
                    request_id=request_id,
                    confidence=generation.confidence,
                )
                return self._refusal_response(
                    request, generation.confidence, service_category
                )

            include_citations = (
                request.include_citations
                if request.include_citations is not None
                else settings.INCLUDE_CITATIONS_DEFAULT
            )
            sources = self._build_sources(unique_chunks)
            citations = generation.citations if include_citations else []
            label = confidence_label_fn(generation.confidence)

            elapsed = time.time() - start_time
            logger.info(
                "pipeline_complete",
                request_id=request_id,
                elapsed_sec=round(elapsed, 3),
                num_sources=len(sources),
                confidence=generation.confidence,
            )
            return QueryResponse(
                question=request.question,
                answer=generation.answer,
                confidence=generation.confidence,
                confidence_label=label,
                sources=sources,
                citations=citations,
                service_category=service_category,
                refused=False,
                visual_capable=settings.llm_is_visual_capable,
            )

        except Exception as exc:
            logger.error(
                "pipeline_error",
                request_id=request_id,
                error=str(exc),
                exc_info=True,
            )
            return self._refusal_response(request, 0.0, "GENERAL")

    # ------------------------------------------------------------------ stream
    async def run_stream(self, request: QueryRequest):
        request_id = str(uuid.uuid4())
        service_category = request.service_category or "GENERAL"
        try:
            top_k = request.top_k or settings.MAX_CHUNKS_RETURN
            router_task = self.router.detect(request.question)
            search_task = self.searcher.search(
                request.question, request.service_category, top_k
            )
            router_result, initial_search = await asyncio.gather(router_task, search_task)
            service_category = request.service_category or router_result.service_category

            if not initial_search:
                payload = self._refusal_response(request, 0.0, service_category)
                yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
                return

            top_score = initial_search[0].score
            rewritten = await maybe_rewrite_query(request.question, top_score)
            search_question = rewritten if rewritten != request.question else request.question
            if rewritten != request.question:
                tuned_top_k = _adjust_top_k(top_k, router_result.intent)
                initial_search = await self.searcher.search(
                    search_question, request.service_category, tuned_top_k
                )
                if not initial_search:
                    payload = self._refusal_response(request, 0.0, service_category)
                    yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
                    return

            top_n = max(request.rerank_top_n or settings.RERANK_TOP_N, 5)
            reranked_chunks = await self.reranker.rerank(search_question, initial_search, top_n)
            unique_chunks = diversify(reranked_chunks, top_k=top_n)
            unique_chunks = _ensure_section_anchor(
                request.question, unique_chunks, initial_search
            )

            pii_miss = _pii_pre_refusal(request.question, unique_chunks)
            if pii_miss is not None:
                payload = self._refusal_response(request, 0.10, service_category)
                yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
                return

            verdict = evidence_gate(unique_chunks, question=request.question)
            if not verdict.passed:
                payload = self._refusal_response(request, 0.10, service_category)
                yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"
                return

            include_citations = (
                request.include_citations
                if request.include_citations is not None
                else settings.INCLUDE_CITATIONS_DEFAULT
            )

            user_prompt = build_user_prompt(request.question, unique_chunks)
            system_prompt = build_system_prompt(service_category)
            parts: list[str] = []
            stream_failed = False
            try:
                async for token in llm_client.complete_stream(prompt=user_prompt, system=system_prompt):
                    parts.append(token)
                    yield f"data: {json.dumps({'type': 'delta', 'text': token})}\n\n"
            except Exception as exc:
                stream_failed = True
                logger.error(
                    "pipeline_stream_llm_failed",
                    request_id=request_id,
                    error=str(exc),
                    exc_info=True,
                )

            if parts and not stream_failed:
                answer = _clean_answer("".join(parts))
                answer = _post_process_images(answer)
                confidence = _score_confidence(answer, unique_chunks)
            else:
                fallback = _extractive_fallback_answer(request.question, unique_chunks)
                answer = _clean_answer(fallback)
                confidence = (
                    settings.EXTRACTIVE_FALLBACK_CONFIDENCE
                    if fallback != REFUSAL_PHRASE
                    else 0.10
                )

            if confidence < settings.CONFIDENCE_THRESHOLD:
                payload = self._refusal_response(request, confidence, service_category)
            else:
                citations: list[Citation] = (
                    build_citations(unique_chunks) if include_citations else []
                )
                payload = QueryResponse(
                    question=request.question,
                    answer=answer,
                    confidence=confidence,
                    confidence_label=confidence_label_fn(confidence),
                    sources=self._build_sources(unique_chunks),
                    citations=citations,
                    service_category=service_category,
                    refused=False,
                    visual_capable=settings.llm_is_visual_capable,
                )
            yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"

        except Exception as exc:
            logger.error(
                "pipeline_stream_error",
                request_id=request_id,
                error=str(exc),
                exc_info=True,
            )
            payload = self._refusal_response(request, 0.0, service_category)
            yield f"data: {json.dumps({'type': 'final', 'payload': payload.model_dump()})}\n\n"


def _has_sufficient_evidence(chunks: list) -> bool:
    """Backwards-compatible helper for tests; prefer evidence_gate()."""
    return evidence_gate(chunks).passed
