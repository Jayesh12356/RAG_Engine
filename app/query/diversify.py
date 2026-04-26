"""Post-rerank diversification.

Implements two cheap, dependency-free diversification primitives applied
*after* reranking:

1. ``per_document_cap`` — at most ``MAX_PER_DOC`` chunks from any single source
   document survive (keeps the highest-scored ones, preserving order).
2. ``mmr_select`` — Maximal Marginal Relevance over chunk text (token-set
   Jaccard as the cheap similarity proxy). Returns ``top_k`` items balancing
   relevance vs novelty using ``MMR_LAMBDA``.

Both are pure functions; tests mock the search/rerank stack so behaviour is
deterministic.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from app.config import get_settings
from app.models.query import SearchResult

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b) or 1
    return inter / union


def per_document_cap(chunks: Sequence[SearchResult], max_per_doc: int | None = None) -> list[SearchResult]:
    settings = get_settings()
    cap = max_per_doc if max_per_doc is not None else settings.MAX_PER_DOC
    if cap <= 0 or not chunks:
        return list(chunks)
    counts: dict[str, int] = {}
    out: list[SearchResult] = []
    for c in chunks:
        key = (
            getattr(c, "document_id", "")
            or (c.metadata or {}).get("document_id")
            or (c.metadata or {}).get("pdf_name")
            or ""
        )
        counts[key] = counts.get(key, 0)
        if counts[key] >= cap:
            continue
        counts[key] += 1
        out.append(c)
    return out


def mmr_select(
    chunks: Sequence[SearchResult],
    top_k: int,
    lambda_: float | None = None,
) -> list[SearchResult]:
    """Select up to ``top_k`` chunks using textual MMR.

    Cosine over real embeddings would be ideal, but rerank inputs do not carry
    embeddings; token-set Jaccard is a fast, robust proxy that materially
    reduces near-duplicate snippets in practice.
    """
    settings = get_settings()
    if not chunks:
        return []
    lam = settings.MMR_LAMBDA if lambda_ is None else lambda_
    lam = max(0.0, min(1.0, lam))
    candidates = list(chunks)
    selected: list[SearchResult] = [candidates.pop(0)]
    selected_tokens: list[set[str]] = [_tokens(selected[0].text)]

    while candidates and len(selected) < top_k:
        best_idx = 0
        best_score = float("-inf")
        for i, c in enumerate(candidates):
            tok = _tokens(c.text)
            relevance = float(c.score or 0.0)
            redundancy = max(_jaccard(tok, st) for st in selected_tokens) if selected_tokens else 0.0
            mmr = lam * relevance - (1.0 - lam) * redundancy
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        chosen = candidates.pop(best_idx)
        selected.append(chosen)
        selected_tokens.append(_tokens(chosen.text))
    return selected


def diversify(chunks: Iterable[SearchResult], top_k: int) -> list[SearchResult]:
    """Apply per-document cap then MMR (when enabled)."""
    settings = get_settings()
    items = per_document_cap(list(chunks))
    if settings.MMR_ENABLED and len(items) > top_k:
        items = mmr_select(items, top_k=top_k)
    return items[:top_k]
