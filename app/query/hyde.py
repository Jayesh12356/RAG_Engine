"""Hypothetical Document Embeddings (HyDE).

Generates a short hypothetical answer to the user's question and uses it as
an additional retrieval probe. The hypothetical does not need to be
factually correct - its dense embedding tends to land near real, relevant
documents, which boosts recall on terse or under-specified questions.

Best-effort: any LLM failure returns ``None`` so the caller can fall back
to plain retrieval. Bounded by ``HYDE_TIMEOUT_SEC`` so a slow provider
never stalls the query pipeline.
"""
from __future__ import annotations

import asyncio

import structlog

from app.config import get_settings
from app.llm import client as llm_client

logger = structlog.get_logger(__name__)


_HYDE_SYSTEM = (
    "You are a retrieval-expansion assistant. Given a user question, write a "
    "short hypothetical answer (3-5 sentences) as if the topic were already "
    "well-documented. The answer does NOT need to be factually correct - its "
    "embedding is used to retrieve similar real documents. Use natural prose, "
    "include domain-specific terms and likely keywords. Do not preface with "
    '"Here is" or similar; output the hypothetical answer only.'
)


async def generate_hypothetical_answer(question: str, timeout_sec: float | None = None) -> str | None:
    """Return a hypothetical answer to ``question`` or ``None`` on failure."""
    settings = get_settings()
    if not (question or "").strip():
        return None
    timeout = timeout_sec if timeout_sec is not None else settings.HYDE_TIMEOUT_SEC

    user_prompt = (
        f"Question: {question}\n"
        "Hypothetical answer (3-5 sentences, plain prose, keyword-rich):"
    )

    try:
        coro = llm_client.complete(prompt=user_prompt, system=_HYDE_SYSTEM)
        raw = await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("hyde.timeout", timeout_sec=timeout)
        return None
    except Exception as exc:
        logger.warning("hyde.failed", error=str(exc))
        return None

    candidate = (raw or "").strip()
    if len(candidate) < 12:
        return None
    logger.info("hyde.generated", chars=len(candidate))
    return candidate
