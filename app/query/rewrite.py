"""Optional LLM-driven query rewriting.

Two modes are exposed:

* :func:`maybe_rewrite_query` — single-shot rewrite for sparse retrieval.
  Activated only when the initial retrieval is weak (top score below
  ``QUERY_REWRITE_TRIGGER_SCORE``) and the feature flag is on. The rewritten
  query is plain English with acronym expansions sourced from the same
  keyword sets the router uses, so behaviour is grounded in the corpus.

* :func:`maybe_rewrite_with_history` — coreference resolution for chat.
  Detects pronouns/follow-ups ("it", "that", "why?") and uses the recent
  conversation history to rewrite the question into a standalone form
  that retrieves correctly out of context.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from app.config import get_settings
from app.llm import client as llm_client
from app.query.router import _CATEGORY_KEYWORDS

if TYPE_CHECKING:
    from app.chat.session import HistoryTurn

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


# ── Conversational coreference rewrite ────────────────────────────────────

_COREFERENCE_SYSTEM = (
    "You resolve coreferences in chat follow-ups. Given a short conversation "
    "history and a follow-up question, rewrite the follow-up so it stands on "
    "its own and can be searched without context. Keep the user's intent, "
    "preserve original entities, and DO NOT invent facts. If the follow-up is "
    "already standalone, return it unchanged. Output ONE rewritten question, "
    "nothing else."
)

_PRONOUN_RX = re.compile(
    r"\b(it|its|this|that|these|those|they|them|their|theirs|he|him|his|"
    r"she|her|hers|the same|that one|the previous|above|earlier)\b",
    re.IGNORECASE,
)
_FOLLOWUP_RX = re.compile(
    r"^\s*(why|how|when|where|who|what|and\b|but\b|so\b|then\b|also\b|"
    r"more\b|tell me more|continue|elaborate|explain that|clarify)",
    re.IGNORECASE,
)


def _looks_like_followup(question: str) -> bool:
    """Heuristic for "this question depends on prior turns to make sense"."""
    q = (question or "").strip()
    if not q:
        return False
    if _PRONOUN_RX.search(q):
        return True
    word_count = len(re.findall(r"\w+", q))
    if word_count <= 5 and _FOLLOWUP_RX.match(q):
        return True
    return False


def _format_history_for_prompt(history: list["HistoryTurn"], max_turns: int = 4) -> str:
    """Compact, single-string view of the most recent ``max_turns`` turns."""
    if not history:
        return ""
    tail = history[-max_turns:]
    lines: list[str] = []
    for turn in tail:
        role = "User" if turn.role == "user" else "Assistant"
        content = (turn.content or "").strip()
        if not content:
            continue
        if role == "Assistant" and len(content) > 240:
            content = content[:240].rstrip() + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def maybe_rewrite_with_history(
    question: str,
    history: list["HistoryTurn"] | None,
) -> str:
    """Resolve coreferences in ``question`` using ``history``.

    Flag-gated by ``CHAT_COREFERENCE_REWRITE``. Returns ``question`` unchanged
    when the flag is off, history is empty, the follow-up looks standalone,
    or the LLM call fails.
    """
    settings = get_settings()
    if not settings.CHAT_COREFERENCE_REWRITE:
        return question
    if not history:
        return question
    if not _looks_like_followup(question):
        return question

    history_block = _format_history_for_prompt(history)
    if not history_block:
        return question

    user_prompt = (
        f"Conversation so far:\n{history_block}\n\n"
        f"Follow-up question: {question}\n"
        "Standalone rewrite:"
    )
    try:
        raw = await llm_client.complete(prompt=user_prompt, system=_COREFERENCE_SYSTEM)
    except Exception as exc:
        logger.warning("chat_coref_rewrite.failed", error=str(exc))
        return question

    lines = (raw or "").strip().splitlines()
    if not lines:
        return question
    candidate = lines[0].strip().strip('"').strip().rstrip(".") or ""
    if len(candidate) < 4:
        return question
    if candidate.lower() == question.strip().lower():
        return question
    logger.info(
        "chat_coref_rewrite.applied",
        original=question,
        rewritten=candidate,
    )
    return candidate
