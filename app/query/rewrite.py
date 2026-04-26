"""Optional LLM-driven query rewriting.

Activated only when the initial retrieval is weak (top score below
``QUERY_REWRITE_TRIGGER_SCORE``) and the feature flag is on. The rewritten
query is plain English with acronym expansions sourced from the same
keyword sets the router uses, so behaviour is grounded in the corpus.
"""
from __future__ import annotations

import structlog

from app.config import get_settings
from app.llm import client as llm_client
from app.query.router import _CATEGORY_KEYWORDS

logger = structlog.get_logger(__name__)


_REWRITE_SYSTEM = (
    "You are a query reformulation assistant for an IT helpdesk RAG system. "
    "Rewrite the user's question to maximize retrieval recall while keeping "
    "the original intent. Expand obvious acronyms and add 2–4 closely "
    "related synonyms in parentheses. Return only the rewritten question."
)


def _acronym_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords[:3]):
            hints.append(category)
    return hints


async def maybe_rewrite_query(question: str, top_score: float | None) -> str:
    """Return either the original question or an LLM-rewritten variant."""
    settings = get_settings()
    if not settings.QUERY_REWRITE_ENABLED:
        return question
    if top_score is not None and top_score >= settings.QUERY_REWRITE_TRIGGER_SCORE:
        return question
    hints = _acronym_hints(question)
    user_prompt = (
        f"Original question: {question}\n"
        f"Likely topic hints: {', '.join(hints) if hints else 'none'}\n"
        "Rewritten question:"
    )
    try:
        raw = await llm_client.complete(prompt=user_prompt, system=_REWRITE_SYSTEM)
    except Exception as exc:
        logger.warning("query_rewrite.failed", error=str(exc))
        return question
    lines = (raw or "").strip().splitlines()
    if not lines:
        return question
    candidate = lines[0].strip().strip('"').strip()
    if not candidate or len(candidate) < 4:
        return question
    logger.info("query_rewrite.applied", original=question, rewritten=candidate)
    return candidate
