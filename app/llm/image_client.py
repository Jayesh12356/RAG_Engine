"""Server-side image generation hook for visual-mode answers.

The RAG prompt (when the configured LLM is vision-capable) lets the model
emit ``image-request`` fenced blocks like:

    ```image-request
    {"prompt": "A simple flowchart of the deployment pipeline", "alt": "deploy flow"}
    ```

After the model finishes, we scan the answer for those blocks and replace
each with a real markdown image. Generation goes through OpenAI's image API
(if a key is present); when generation is disabled we strip the block but
keep a placeholder so the user is never confused by raw JSON in their answer.

This module is fail-soft: any exception (network, invalid JSON, missing key)
falls back to leaving the answer text intact minus the request block.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import openai
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Match a ```image-request fenced code block (case-insensitive language tag).
_IMAGE_REQUEST_RE = re.compile(
    r"```image-request[ \t]*\n(?P<body>.*?)\n```",
    re.IGNORECASE | re.DOTALL,
)

_MAX_IMAGES_PER_ANSWER = 2
_MAX_PROMPT_CHARS = 1200

_image_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI | None:
    global _image_client
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None
    if _image_client is None:
        _image_client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
        )
    return _image_client


def _parse_request(body: str) -> tuple[str, str]:
    """Return ``(prompt, alt)`` from a JSON request body. Tolerates a couple
    of common LLM mistakes (single quotes, missing ``alt``)."""
    body = body.strip()
    try:
        data: Any = json.loads(body)
    except json.JSONDecodeError:
        try:
            data = json.loads(body.replace("'", '"'))
        except Exception:
            return body[:_MAX_PROMPT_CHARS], "Generated image"
    if not isinstance(data, dict):
        return body[:_MAX_PROMPT_CHARS], "Generated image"
    prompt = str(data.get("prompt") or "").strip()[:_MAX_PROMPT_CHARS]
    alt = str(data.get("alt") or "Generated image").strip()[:160]
    return prompt, alt or "Generated image"


def _generate_data_url(prompt: str) -> str | None:
    """Generate a single image. Returns a data URL or ``None`` on failure."""
    client = _get_client()
    if client is None:
        return None
    settings = get_settings()
    try:
        response = client.images.generate(
            model=settings.IMAGE_GEN_MODEL,
            prompt=prompt,
            size=settings.IMAGE_GEN_SIZE,
            n=1,
            response_format="b64_json",
        )
    except TypeError:
        # ``response_format`` is not accepted by all model variants. Retry
        # without it and rely on whichever default the SDK picks.
        try:
            response = client.images.generate(
                model=settings.IMAGE_GEN_MODEL,
                prompt=prompt,
                size=settings.IMAGE_GEN_SIZE,
                n=1,
            )
        except Exception as exc:
            logger.warning("image_gen.failed", error=str(exc), prompt_preview=prompt[:120])
            return None
    except Exception as exc:
        logger.warning("image_gen.failed", error=str(exc), prompt_preview=prompt[:120])
        return None

    try:
        first = response.data[0]
        b64 = getattr(first, "b64_json", None)
        url = getattr(first, "url", None)
    except Exception as exc:
        logger.warning("image_gen.bad_response", error=str(exc))
        return None

    if b64:
        return f"data:image/png;base64,{b64}"
    if url:
        return url
    return None


def post_process_answer(answer: str) -> str:
    """Replace every ``image-request`` block in ``answer`` with an inline image.

    Cheap and synchronous (image generation is the slow part, but we already
    blocked on the LLM completion). Entire function is best-effort: on any
    failure we strip the request block and proceed.
    """
    if not answer or "image-request" not in answer:
        return answer

    settings = get_settings()
    matches = list(_IMAGE_REQUEST_RE.finditer(answer))
    if not matches:
        return answer

    if not settings.image_gen_active:
        # Strip the blocks so the user never sees the raw JSON.
        return _IMAGE_REQUEST_RE.sub("", answer).strip()

    out = answer
    generated = 0
    # Iterate in reverse so earlier substitutions don't shift later spans.
    for match in reversed(matches):
        if generated >= _MAX_IMAGES_PER_ANSWER:
            out = out[: match.start()] + out[match.end():]
            continue
        prompt, alt = _parse_request(match.group("body"))
        if not prompt:
            out = out[: match.start()] + out[match.end():]
            continue
        data_url = _generate_data_url(prompt)
        if data_url is None:
            out = out[: match.start()] + out[match.end():]
            continue
        replacement = f"![{alt}]({data_url})"
        out = out[: match.start()] + replacement + out[match.end():]
        generated += 1

    return out.strip()
