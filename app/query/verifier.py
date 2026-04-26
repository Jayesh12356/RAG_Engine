"""Optional groundedness verifier (extra LLM pass).

Pipelines normally trust :func:`app.query.rag_generator._score_confidence`
to gate weak answers, but a calibrated confidence number can still bless
plausible-looking hallucinations. The verifier is a stricter, opt-in
second opinion: it asks the LLM "is every claim in this answer supported
by the context?" and refuses if the score falls below
``ANSWER_VERIFIER_MIN_SCORE``.

The verifier fails open. Any LLM error or unparseable response returns
``passed=True`` with a sentinel reason so flaky infrastructure never
causes a false refusal.
"""
from __future__ import annotations

import json
import re

import structlog

from app.config import get_settings
from app.llm import client as llm_client
from app.models.query import SearchResult

logger = structlog.get_logger(__name__)


_VERIFIER_SYSTEM = (
    "You are a strict groundedness verifier for a retrieval-augmented "
    "answer. Given a user question, an answer, and the retrieval context, "
    "decide whether every factual claim in the answer is directly supported "
    "by the context. Score from 0.0 (unsupported / hallucinated) to 1.0 "
    "(fully grounded). Output ONE LINE of valid JSON: "
    '{"score": <float>, "reason": <short string>}'
)


def _parse_score(raw: str) -> tuple[float, str]:
    """Best-effort score extraction. Fails open with ``score=1.0``."""
    if not raw:
        return 1.0, "empty"
    text = raw.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "score" in obj:
            score = float(obj.get("score", 1.0))
            reason = str(obj.get("reason") or "ok")
            return max(0.0, min(1.0, score)), reason
    except Exception:
        pass

    m = re.search(r'"score"\s*:\s*([0-9]+\.?[0-9]*)', text)
    if m:
        try:
            return max(0.0, min(1.0, float(m.group(1)))), "regex"
        except Exception:
            pass

    m2 = re.search(r"\b([01](?:\.\d+)?)\b", text)
    if m2:
        try:
            return max(0.0, min(1.0, float(m2.group(1)))), "loose"
        except Exception:
            pass

    return 1.0, "unparseable"


async def verify_groundedness(
    question: str,
    answer: str,
    chunks: list[SearchResult],
) -> tuple[bool, float, str]:
    """Score how well ``answer`` is grounded in ``chunks``.

    Returns ``(passed, score, reason)``. ``passed`` is ``True`` whenever
    ``score >= ANSWER_VERIFIER_MIN_SCORE`` or any failure path triggers.
    """
    settings = get_settings()
    if not settings.ANSWER_VERIFIER_ENABLED:
        return True, 1.0, "disabled"
    if not (answer or "").strip() or not chunks:
        return True, 1.0, "trivial"

    context = "\n\n---\n\n".join((c.text or "") for c in chunks[:5])
    user_prompt = (
        f"Question: {question}\n\n"
        f"Context:\n{context[:6000]}\n\n"
        f"Answer:\n{answer}\n\n"
        "JSON verdict:"
    )
    try:
        raw = await llm_client.complete(prompt=user_prompt, system=_VERIFIER_SYSTEM)
    except Exception as exc:
        logger.warning("verifier.failed", error=str(exc))
        return True, 1.0, f"llm-error: {exc}"

    score, reason = _parse_score(raw or "")
    threshold = float(settings.ANSWER_VERIFIER_MIN_SCORE)
    passed = score >= threshold
    logger.info(
        "verifier.scored",
        score=score,
        threshold=threshold,
        passed=passed,
        reason=reason,
    )
    return passed, score, reason
