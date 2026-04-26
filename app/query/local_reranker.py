"""Local cross-encoder rerank fallback.

Loads a small Hugging Face cross-encoder (default ``BAAI/bge-reranker-base``)
on first use and re-scores retrieved chunks against the query. Used as the
preferred fallback when the Cohere reranker is unavailable - quality is
much closer to Cohere than the lexical-overlap fallback.

* The model + ``sentence-transformers`` are lazy-imported and the import is
  optional. Install with ``pip install 'helpdesk-chatbot[local-rerank]'``.
* Off by default: enable via ``LOCAL_RERANKER_ENABLED=true``.
* Inference runs on a thread executor so the asyncio loop never blocks.
* Any failure (missing dependency, model load error, runtime error) returns
  ``None`` so the caller falls back further to the lexical rescore.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.config import get_settings
from app.models.query import SearchResult

logger = structlog.get_logger(__name__)

_model_cache: dict[str, Any] = {}
_load_failed: bool = False


def _try_load() -> Any | None:
    """Return a cached :class:`CrossEncoder`, ``None`` if unavailable.

    Side-effect-free except for the in-process cache. Subsequent calls after
    a failed load short-circuit immediately.
    """
    global _load_failed
    settings = get_settings()
    if not settings.LOCAL_RERANKER_ENABLED:
        return None
    if _load_failed:
        return None

    model_name = settings.LOCAL_RERANKER_MODEL
    cached = _model_cache.get(model_name)
    if cached is not None:
        return cached

    try:
        from sentence_transformers import CrossEncoder
    except Exception as exc:
        logger.info(
            "local_reranker.import_unavailable",
            error=str(exc),
            hint="pip install 'helpdesk-chatbot[local-rerank]'",
        )
        _load_failed = True
        return None

    try:
        model = CrossEncoder(model_name)
    except Exception as exc:
        logger.warning(
            "local_reranker.load_failed", model=model_name, error=str(exc)
        )
        _load_failed = True
        return None

    _model_cache[model_name] = model
    logger.info("local_reranker.loaded", model=model_name)
    return model


def _score_sync(model: Any, query: str, texts: list[str]) -> list[float] | None:
    try:
        pairs = [[query, t] for t in texts]
        scores = model.predict(
            pairs, convert_to_numpy=True, show_progress_bar=False
        )
        return [float(s) for s in scores]
    except Exception as exc:
        logger.warning("local_reranker.score_failed", error=str(exc))
        return None


async def maybe_local_rerank(
    question: str,
    results: list[SearchResult],
    top_n: int,
) -> list[SearchResult] | None:
    """Score ``results`` with a local cross-encoder.

    Returns:
        * ``[]`` when ``results`` is empty.
        * ``None`` when local reranking is disabled, unavailable, or fails.
        * The reranked top-``top_n`` ``SearchResult`` list otherwise.
    """
    if not results:
        return []
    model = _try_load()
    if model is None:
        return None

    texts = [r.text or "" for r in results]
    loop = asyncio.get_running_loop()
    try:
        scores = await loop.run_in_executor(None, _score_sync, model, question, texts)
    except Exception as exc:
        logger.warning("local_reranker.executor_failed", error=str(exc))
        return None

    if scores is None or len(scores) != len(results):
        return None

    rescored: list[SearchResult] = []
    for r, s in zip(results, scores, strict=False):
        r.score = float(s)
        rescored.append(r)
    rescored.sort(key=lambda x: x.score, reverse=True)
    logger.info("local_reranker.applied", returned=min(top_n, len(rescored)))
    return rescored[:top_n]


def _reset_cache_for_tests() -> None:
    """Test helper: forget any cached model + failure state."""
    global _load_failed
    _model_cache.clear()
    _load_failed = False
