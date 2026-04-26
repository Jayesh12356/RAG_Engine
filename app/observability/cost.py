"""Per-request cost estimation.

These prices are deliberately conservative defaults — they're used only for
the "$ / question" gauge in the UI. Operators can override them at runtime
via environment variables (``LLM_COST_PER_1K_INPUT_USD`` /
``LLM_COST_PER_1K_OUTPUT_USD``).
"""
from __future__ import annotations

import os
import re
from typing import Optional


_TOKEN_RE = re.compile(r"\w+|\S")


def _approx_tokens(text: str | None) -> int:
    if not text:
        return 0
    # Roughly 4 chars per token across modern tokenizers; faster than
    # importing tiktoken and good enough for cost estimation.
    return max(1, int(len(text) / 4))


def _model_pricing(model: str) -> tuple[float, float]:
    """Best-effort lookup of $/1K input + $/1K output for known models.

    Returns ``(input_per_1k, output_per_1k)``. Unknown models fall through to
    a conservative blended price (~$5/M input, $15/M output).
    """
    key = (model or "").lower()
    table: tuple[tuple[str, float, float], ...] = (
        # OpenAI
        ("gpt-4o-mini", 0.00015, 0.00060),
        ("gpt-4o", 0.00250, 0.01000),
        ("gpt-4-turbo", 0.01000, 0.03000),
        ("gpt-4.1-mini", 0.00040, 0.00160),
        ("gpt-4.1", 0.00200, 0.00800),
        ("o1-mini", 0.00300, 0.01200),
        ("o3-mini", 0.00110, 0.00440),
        ("o3", 0.01500, 0.06000),
        # Groq (very cheap inference)
        ("llama-3.3-70b", 0.00059, 0.00079),
        ("llama-3.1-70b", 0.00059, 0.00079),
        ("llama-3.1-8b", 0.00005, 0.00008),
        # Anthropic Claude
        ("claude-3-5-sonnet", 0.00300, 0.01500),
        ("claude-3-5-haiku", 0.00080, 0.00400),
        ("claude-3-haiku", 0.00025, 0.00125),
        ("claude-sonnet-4", 0.00300, 0.01500),
        # Google Gemini
        ("gemini-2.0-flash", 0.00010, 0.00040),
        ("gemini-1.5-pro", 0.00125, 0.00500),
        ("gemini-1.5-flash", 0.00007, 0.00030),
    )
    for prefix, inp, out in table:
        if prefix in key:
            return inp, out
    # Fallback: env override or sensible default
    try:
        inp = float(os.getenv("LLM_COST_PER_1K_INPUT_USD") or "0.005")
        out = float(os.getenv("LLM_COST_PER_1K_OUTPUT_USD") or "0.015")
        return inp, out
    except ValueError:
        return 0.005, 0.015


def estimate_cost_usd(
    *,
    prompt_text: Optional[str],
    answer_text: Optional[str],
    model: str | None = None,
) -> float:
    """Estimate request cost in USD given the active LLM and input/output text."""
    inp_per_1k, out_per_1k = _model_pricing(model or "")
    inp_tokens = _approx_tokens(prompt_text)
    out_tokens = _approx_tokens(answer_text)
    return round((inp_tokens / 1000.0) * inp_per_1k + (out_tokens / 1000.0) * out_per_1k, 6)
