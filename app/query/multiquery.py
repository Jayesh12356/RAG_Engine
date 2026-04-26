"""Multi-query paraphrase expansion.

Asks the LLM to produce N diverse paraphrases of the user's question, then
returns them so retrieval can fan out across all variants. Combined with
the original question and (optionally) HyDE, the union of hits is fused
with RRF in :mod:`app.query.expand`.

Best-effort: parsing failures or LLM errors return ``[]`` so the caller
falls back to plain retrieval. Bounded by ``HYDE_TIMEOUT_SEC`` (shared
with HyDE) so a slow provider never stalls the pipeline.
"""
from __future__ import annotations

import asyncio
import re

import structlog

from app.config import get_settings
from app.llm import client as llm_client

logger = structlog.get_logger(__name__)


_PARAPHRASE_SYSTEM = (
    "You generate diverse paraphrases of a search query. Each paraphrase MUST "
    "preserve the original intent but vary wording, synonym choice and phrasing. "
    "Output ONE paraphrase per line, no numbering, no quotes, no commentary - "
    "the consumer parses your output line-by-line."
)


_NUMBER_PREFIX = re.compile(r"^\s*(?:[-*\u2022]|\d+[\.\)])\s+")


def _parse_paraphrases(raw: str, original: str, n: int) -> list[str]:
    """Pull at most ``n`` clean lines from the model output, dropping the
    original question if echoed back and any number/bullet prefixes."""
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = {(original or "").strip().lower()}
    for line in raw.splitlines():
        line = _NUMBER_PREFIX.sub("", line.strip()).strip().strip('"').strip("'")
        if not line or len(line) < 4:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
        if len(out) >= n:
            break
    return out


async def generate_paraphrases(
    question: str,
    n: int = 3,
    timeout_sec: float | None = None,
) -> list[str]:
    """Return up to ``n`` paraphrases of ``question`` or ``[]`` on failure."""
    settings = get_settings()
    if not (question or "").strip() or n <= 0:
        return []
    timeout = timeout_sec if timeout_sec is not None else settings.HYDE_TIMEOUT_SEC

    user_prompt = (
        f"Original query: {question}\n"
        f"Generate {n} paraphrase(s), one per line:"
    )

    try:
        coro = llm_client.complete(prompt=user_prompt, system=_PARAPHRASE_SYSTEM)
        raw = await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("multiquery.timeout", timeout_sec=timeout)
        return []
    except Exception as exc:
        logger.warning("multiquery.failed", error=str(exc))
        return []

    paraphrases = _parse_paraphrases(raw, question, n)
    if paraphrases:
        logger.info("multiquery.generated", count=len(paraphrases))
    return paraphrases
