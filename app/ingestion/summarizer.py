"""Per-document summary generation.

Produces a short (2-3 sentence) abstract that surfaces in the documents
list and makes it easier for users to recognise an uploaded file at a
glance. Operates on a budget of *one* LLM call per document — we only
look at the first ~3,000 characters of concatenated chunk text, which
is plenty for an abstract and keeps cost bounded for huge corpora.

The summarizer fails open: any exception returns ``None`` and the
ingestion pipeline simply omits the column. Generation is therefore
strictly additive — flipping the feature flag off (or running offline)
keeps everything else green.
"""
from __future__ import annotations

import asyncio
import re

import structlog

from app.config import get_settings
from app.llm import client as llm_client

logger = structlog.get_logger(__name__)


_SUMMARY_SYSTEM = (
    "You are a librarian. Given the start of a document, write a "
    "concise 2-3 sentence summary aimed at someone deciding whether the "
    "document answers their question. Focus on topic, scope, and "
    "audience. Do not preface with 'This document'; output the summary "
    "directly."
)


def _coalesce_text(snippets: list[str], cap_chars: int) -> str:
    out: list[str] = []
    used = 0
    for raw in snippets:
        s = (raw or "").strip()
        if not s:
            continue
        remaining = cap_chars - used
        if remaining <= 0:
            break
        if len(s) > remaining:
            out.append(s[:remaining])
            used = cap_chars
            break
        out.append(s)
        used += len(s) + 2
    return "\n\n".join(out)


def _clean_summary(raw: str) -> str:
    """Trim filler, collapse whitespace, and bound length."""
    if not raw:
        return ""
    text = raw.strip().strip('"').strip()
    text = re.sub(r"^(here(?:'s| is)|sure|certainly|the document)[:,]?\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text[:600]


async def summarize_document(
    snippets: list[str],
    *,
    timeout_sec: float | None = None,
) -> str | None:
    """Return a short summary string or ``None`` on any failure.

    ``snippets`` is a small ordered list of chunk texts (typically the
    first 6-8 chunks). They are concatenated and truncated to
    ``cap_chars`` before the LLM call so we never blow the prompt
    budget on huge documents.
    """
    settings = get_settings()
    cap_chars = 3000
    text = _coalesce_text(snippets, cap_chars)
    if not text:
        return None

    user_prompt = f"Document excerpt:\n\n{text}\n\nSummary:"
    timeout = timeout_sec if timeout_sec is not None else float(settings.LLM_REQUEST_TIMEOUT_SEC)
    try:
        raw = await asyncio.wait_for(
            llm_client.complete(prompt=user_prompt, system=_SUMMARY_SYSTEM),
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("summarizer.failed", error=str(exc))
        return None

    cleaned = _clean_summary(raw or "")
    return cleaned or None
