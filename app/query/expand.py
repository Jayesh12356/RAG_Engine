"""Retrieval expansion orchestrator.

Combines HyDE (:mod:`app.query.hyde`) and multi-query paraphrases
(:mod:`app.query.multiquery`) with the original question, runs hybrid
search across all variants in parallel, and fuses the unioned candidates
with reciprocal-rank fusion (RRF, ``HYBRID_RRF_K``).

When both flags are off, behaviour is byte-identical to a single
``searcher.search(question, service_category, top_k)`` call - no extra
LLM calls, no extra searches. Failures during expansion always degrade
gracefully to plain search.
"""
from __future__ import annotations

import asyncio

import structlog

from app.config import get_settings
from app.models.query import SearchResult
from app.query.hybrid_search import HybridSearch
from app.query.hyde import generate_hypothetical_answer
from app.query.multiquery import generate_paraphrases

logger = structlog.get_logger(__name__)


def _rrf_fuse(
    results_per_query: list[list[SearchResult]],
    rrf_k: int,
    top_k: int,
) -> list[SearchResult]:
    """Reciprocal-rank fusion across multiple ranked result lists."""
    fused: dict[str, tuple[SearchResult, float]] = {}
    for results in results_per_query:
        for rank, hit in enumerate(results):
            cid = hit.chunk_id or ""
            if not cid:
                continue
            contribution = 1.0 / (rrf_k + rank + 1)
            stored = fused.get(cid)
            if stored is None:
                fused[cid] = (hit, contribution)
            else:
                fused[cid] = (stored[0], stored[1] + contribution)
    items = sorted(fused.values(), key=lambda x: x[1], reverse=True)
    return [hit.model_copy(update={"score": total}) for hit, total in items[:top_k]]


async def _gather_expansions(question: str) -> list[str]:
    """Concurrently call configured expansion strategies.

    Returns the additional queries to fan out over (without the original).
    Best-effort: each strategy individually swallows its errors.
    """
    settings = get_settings()
    tasks: list[asyncio.Task] = []
    if settings.HYDE_ENABLED:
        tasks.append(asyncio.create_task(generate_hypothetical_answer(question)))
    if settings.MULTI_QUERY_ENABLED:
        tasks.append(
            asyncio.create_task(
                generate_paraphrases(question, settings.MULTI_QUERY_VARIANTS)
            )
        )
    if not tasks:
        return []
    out: list[str] = []
    for result in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(result, str) and result.strip():
            out.append(result.strip())
        elif isinstance(result, list):
            out.extend(s for s in result if isinstance(s, str) and s.strip())
    return out


def _dedupe(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = (q or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(q.strip())
    return out


async def expanded_search(
    searcher: HybridSearch,
    question: str,
    service_category: str | None,
    top_k: int,
    tags: list[str] | None = None,
) -> list[SearchResult]:
    """Run hybrid search, optionally expanded by HyDE and/or multi-query.

    Returns up to ``top_k`` results. With both expansion flags off this is
    equivalent to
    ``await searcher.search(question, service_category, top_k, tags=tags)``.
    """
    settings = get_settings()
    if not settings.HYDE_ENABLED and not settings.MULTI_QUERY_ENABLED:
        return await searcher.search(question, service_category, top_k, tags=tags)

    expansions = await _gather_expansions(question)
    queries = _dedupe([question, *expansions])

    if len(queries) == 1:
        return await searcher.search(question, service_category, top_k, tags=tags)

    logger.info("expand.fanout", variants=len(queries))
    search_tasks = [
        searcher.search(q, service_category, top_k, tags=tags) for q in queries
    ]
    results_per_query: list[list[SearchResult]] = []
    raw_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    for r in raw_results:
        if isinstance(r, list):
            results_per_query.append(r)

    if not results_per_query:
        return []
    if len(results_per_query) == 1:
        return results_per_query[0][:top_k]

    return _rrf_fuse(results_per_query, settings.HYBRID_RRF_K, top_k)
