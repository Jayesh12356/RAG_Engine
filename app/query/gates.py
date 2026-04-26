"""Shared evidence + confidence gating helpers.

Both query and chat pipelines share these helpers so retrieval-quality and
answer-quality decisions stay consistent end-to-end.

The gate uses a hybrid signal: an *absolute* reranker-score floor (great for
long IT runbooks where Cohere rerank-english-v3 lands in 0.3-0.9), and a
*lexical-overlap* fallback that rescues corpora whose absolute scores cluster
low (CVs, CSVs, papers, short chunks, …). The lexical check makes the gate
robust enough that any legitimate question that finds a chunk containing one
of its content tokens lands in the LLM, while a question whose tokens never
appear in the corpus still refuses cleanly (e.g. "Albert Einstein" against an
IT/CV corpus).
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.config import get_settings

# Tokens shorter than 3 chars or in this stoplist do not count toward the
# lexical-overlap rescue. Keep in sync with rag_generator's tokenizer style.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "or", "the", "is", "are", "was", "were", "be", "been",
        "being", "of", "in", "on", "for", "to", "from", "by", "with", "as", "at",
        "this", "that", "these", "those", "it", "its", "i", "me", "my", "we",
        "our", "you", "your", "he", "him", "his", "she", "her", "they", "them",
        "their", "what", "who", "whom", "whose", "which", "where", "when", "why",
        "how", "do", "does", "did", "doing", "have", "has", "had", "having",
        "can", "could", "would", "should", "may", "might", "must", "shall",
        "will", "any", "some", "all", "no", "not", "but", "if", "then", "else",
        "than", "so", "such", "about", "over", "under", "into", "out", "up",
        "down", "off", "again", "very", "just", "more", "most", "other", "also",
        "tell", "give", "list", "show", "explain", "describe", "summarize",
        "based", "please", "kindly", "exactly", "really",
    }
)


def _content_tokens(text: str) -> set[str]:
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if len(t) >= 3 and t.lower() not in _STOPWORDS
    }


@dataclass(frozen=True)
class EvidenceVerdict:
    passed: bool
    reason: str
    top_score: float
    second_score: float


def evidence_gate(chunks: Sequence, question: str | None = None) -> EvidenceVerdict:
    """Decide whether the retrieved/reranked chunks carry enough signal.

    Reads thresholds from ``app.config.Settings``:
      - ``RELEVANCE_MIN_TOP_SCORE``      — minimum top-1 score
      - ``RELEVANCE_MIN_SECOND_SCORE``   — second hit floor when top is borderline
      - ``RELEVANCE_MIN_SCORE_GAP``      — minimum margin between top and second

    A lexical-overlap rescue path lets short-chunk corpora (CVs, CSV exports,
    papers) pass even when Cohere reranker absolute scores are in the
    1e-3 range. The rescue requires either (a) at least one of the top-3
    chunks sharing two or more content tokens with ``question``, or (b) the
    top chunk sharing a long content token (≥4 chars) — typically a name or
    domain-specific identifier. Stopwords and very short tokens never count.
    """
    settings = get_settings()
    if not chunks:
        return EvidenceVerdict(False, "no_chunks", 0.0, 0.0)

    top = float(getattr(chunks[0], "score", 0.0) or 0.0)
    second = float(getattr(chunks[1], "score", 0.0) or 0.0) if len(chunks) > 1 else 0.0
    gap = top - second

    floor = settings.RELEVANCE_MIN_TOP_SCORE
    second_floor = settings.RELEVANCE_MIN_SECOND_SCORE
    gap_floor = settings.RELEVANCE_MIN_SCORE_GAP

    above_floor = top >= floor

    # Lexical-overlap rescue (only when caller passes a question).
    lexical_anchor = False
    if question:
        q_tokens = _content_tokens(question)
        if q_tokens:
            for c in chunks[:3]:
                c_tokens = _content_tokens(getattr(c, "text", "") or "")
                shared = q_tokens & c_tokens
                if not shared:
                    continue
                # Two cheap rescues, either of which proves the chunk really
                # discusses the question's content tokens:
                #  • multiple shared content tokens (broad overlap), or
                #  • a single shared "long" token like a name (≥4 chars).
                long_hit = any(len(t) >= 4 for t in shared)
                if len(shared) >= 2 or long_hit:
                    lexical_anchor = True
                    break

    if not above_floor and not lexical_anchor:
        return EvidenceVerdict(False, "top_below_floor", top, second)

    # Lexical anchor short-circuits secondary margin checks: if the top chunk
    # really contains the question's content tokens (a name, an identifier, a
    # domain term ≥4 chars), we trust it regardless of how low the rest of
    # the rerank scores are. Single-document corpora (a CV, a runbook) often
    # produce one strong hit with a long tail of unrelated chunks, which is
    # exactly the shape ``second_too_weak`` was designed to catch but for the
    # wrong reason.
    if lexical_anchor:
        return EvidenceVerdict(True, "lexical_anchor", top, second)

    # Pure absolute-score path: apply the strict second/gap checks only when
    # the top is borderline (< 0.50) or the margin is suspicious.
    if (
        len(chunks) > 1
        and second < second_floor
        and top < 0.50
    ):
        return EvidenceVerdict(False, "second_too_weak", top, second)

    if (
        len(chunks) > 1
        and gap < gap_floor
        and top < 0.55
    ):
        return EvidenceVerdict(False, "margin_too_small", top, second)

    return EvidenceVerdict(True, "ok", top, second)


def confidence_label(confidence: float) -> str:
    """Map a calibrated confidence score onto a coarse user-facing label.

    Buckets stay aligned with ``CONFIDENCE_THRESHOLD`` so the refusal policy
    in pipelines is stable regardless of which path produced ``confidence``.
    """
    settings = get_settings()
    if confidence < settings.CONFIDENCE_THRESHOLD:
        return "refused"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "moderate"
    return "low"
