"""LLM + embedding client.

Provides:
  - complete: chat completion with multi-provider failover and per-attempt retries.
  - complete_stream: streaming chat completion with bounded retries on connection
    establishment and provider failover before any tokens are yielded.
  - embed_query / embed_documents: separate embedding helpers so providers that
    distinguish queries from passages (Cohere v3+) get the right input_type. Both
    have cross-provider failover.
  - embed: backwards-compatible wrapper around embed_documents.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal

import cohere
import openai
import structlog
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── Singleton clients (connection reuse = faster) ─────────────────────────
_llm_clients: dict[str, openai.AsyncOpenAI] = {}
_embed_clients: dict[str, openai.AsyncOpenAI | cohere.AsyncClient] = {}


# ──────────────────────────────────────────────────────────────────────────
# Chat / completion
# ──────────────────────────────────────────────────────────────────────────
def _get_llm_client_for(provider: str) -> openai.AsyncOpenAI:
    if provider not in _llm_clients:
        if provider == "groq":
            _llm_clients[provider] = openai.AsyncOpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
        elif provider == "openrouter":
            _llm_clients[provider] = openai.AsyncOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            _llm_clients[provider] = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url="https://api.openai.com/v1",
            )
    return _llm_clients[provider]


def _get_llm_client() -> openai.AsyncOpenAI:
    return _get_llm_client_for(settings.LLM_PROVIDER)


def _provider_model(provider: str) -> str:
    if provider == "groq":
        return settings.GROQ_MODEL
    if provider == "openrouter":
        return settings.OPENROUTER_MODEL
    return settings.OPENAI_MODEL


def _get_model() -> str:
    return _provider_model(settings.LLM_PROVIDER)


def _has_provider_key(provider: str) -> bool:
    if provider == "groq":
        return bool(settings.GROQ_API_KEY)
    if provider == "openrouter":
        return bool(settings.OPENROUTER_API_KEY)
    return bool(settings.OPENAI_API_KEY)


def _candidate_llm_providers(preferred: str) -> list[str]:
    ordered = [preferred, "openai", "openrouter", "groq"]
    seen: set[str] = set()
    out: list[str] = []
    for p in ordered:
        if p in seen:
            continue
        seen.add(p)
        if _has_provider_key(p):
            out.append(p)
    return out


async def complete(prompt: str, system: str = "", model_override: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    providers = _candidate_llm_providers(settings.LLM_PROVIDER)
    last_error: Exception | None = None
    for provider in providers:
        client = _get_llm_client_for(provider)
        model = model_override or _provider_model(provider)
        try:
            async for attempt in AsyncRetrying(
                wait=wait_exponential(multiplier=1, min=1, max=8),
                stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
                reraise=True,
            ):
                with attempt:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=1200,
                        timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
                    )
                    return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("llm.complete.provider_failed", provider=provider, error=str(exc))
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No available LLM provider configured")


async def complete_stream(
    prompt: str,
    system: str = "",
    model_override: str | None = None,
) -> AsyncIterator[str]:
    """Stream completion tokens.

    Retries are applied to *connection establishment* (the initial
    `chat.completions.create` call). Once a provider successfully starts
    streaming, partial output is yielded and any mid-stream failure triggers
    failover to the next provider only if no tokens have been yielded yet.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    providers = _candidate_llm_providers(settings.LLM_PROVIDER)
    last_error: Exception | None = None
    for provider in providers:
        client = _get_llm_client_for(provider)
        model = model_override or _provider_model(provider)

        # Retry connection establishment per provider.
        stream = None
        try:
            async for attempt in AsyncRetrying(
                wait=wait_exponential(multiplier=1, min=1, max=8),
                stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
                reraise=True,
            ):
                with attempt:
                    stream = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=1200,
                        timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
                        stream=True,
                    )
        except Exception as exc:
            logger.warning(
                "llm.complete_stream.connect_failed",
                provider=provider,
                error=str(exc),
            )
            last_error = exc
            continue

        # Connection established — iterate. If iteration fails before we
        # yield anything, fall over to next provider; otherwise re-raise.
        yielded_any = False
        try:
            async for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta.content or ""
                if delta:
                    yielded_any = True
                    yield delta
            return
        except Exception as exc:
            logger.warning(
                "llm.complete_stream.iter_failed",
                provider=provider,
                error=str(exc),
                yielded_any=yielded_any,
            )
            last_error = exc
            if yielded_any:
                # Already streamed partial output; do not switch providers
                # since the consumer would receive mixed tokens.
                raise
            continue

    if last_error:
        raise last_error
    raise RuntimeError("No available LLM provider configured")


# ──────────────────────────────────────────────────────────────────────────
# Embeddings — query vs documents
# ──────────────────────────────────────────────────────────────────────────
EmbedKind = Literal["query", "document"]


# Known embedding model dimensions. Used to pre-filter providers during
# failover so we never silently store vectors of a different dimension into
# Qdrant (which would corrupt the index). Extend this map when new models
# are added to ``app/config.py``.
_EMBED_MODEL_DIMS: dict[str, int] = {
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # Cohere
    "embed-english-v3.0": 1024,
    "embed-english-light-v3.0": 384,
    "embed-multilingual-v3.0": 1024,
    "embed-multilingual-light-v3.0": 384,
    # OpenRouter / Google
    # NOTE: As routed via OpenRouter, gemini-embedding-001 currently returns
    # 3072-dim vectors (validated 2026-04-26). Google's docs list 768/1536
    # as configurable output sizes, but OpenRouter does not expose that knob.
    "google/gemini-embedding-001": 3072,
}


def _provider_embed_model(provider: str) -> str:
    if provider == "cohere":
        return settings.COHERE_EMBEDDING_MODEL
    if provider == "openrouter":
        return settings.OPENROUTER_EMBEDDING_MODEL
    return settings.OPENAI_EMBEDDING_MODEL


def _provider_embed_dim(provider: str) -> int | None:
    """Return the known dimension for a provider's configured embedding model.

    Returns ``None`` when the model is not in :data:`_EMBED_MODEL_DIMS` so the
    caller can decide whether to trust the configured ``EMBEDDING_DIM`` or
    refuse the provider.
    """
    return _EMBED_MODEL_DIMS.get(_provider_embed_model(provider))


def _has_embed_provider_key(provider: str) -> bool:
    if provider == "cohere":
        return bool(settings.COHERE_API_KEY)
    if provider == "openrouter":
        return bool(settings.OPENROUTER_API_KEY)
    return bool(settings.OPENAI_API_KEY)


def _candidate_embed_providers(preferred: str) -> list[str]:
    """Return embedding providers whose configured model dim matches settings.

    The preferred provider MUST match ``settings.EMBEDDING_DIM``; if its
    configured model has a known mismatching dim we raise immediately so a
    misconfigured deployment is caught at startup rather than silently
    corrupting the Qdrant collection during failover.
    """
    expected_dim = settings.EMBEDDING_DIM
    ordered = [preferred, "openai", "openrouter", "cohere"]
    seen: set[str] = set()
    out: list[str] = []
    for p in ordered:
        if p in seen:
            continue
        seen.add(p)
        if not _has_embed_provider_key(p):
            continue
        dim = _provider_embed_dim(p)
        if dim is not None and dim != expected_dim:
            if p == preferred:
                raise RuntimeError(
                    "Preferred embedding provider "
                    f"'{p}' uses model '{_provider_embed_model(p)}' with "
                    f"dim={dim}, but EMBEDDING_DIM={expected_dim}. Refusing "
                    "to start: set EMBEDDING_DIM to match the model or pick a "
                    "model with the matching dimension."
                )
            logger.warning(
                "llm.embed.provider_dim_mismatch_skipped",
                provider=p,
                model=_provider_embed_model(p),
                provider_dim=dim,
                expected_dim=expected_dim,
            )
            continue
        out.append(p)
    return out


async def verify_embedding_consistency() -> None:
    """Health-check: confirm the active embedding provider returns vectors of
    ``settings.EMBEDDING_DIM`` so the rest of the stack (Qdrant, reranker,
    BM25 corpus stats) stays internally consistent.

    Raises :class:`RuntimeError` on dimension mismatch; the FastAPI lifespan
    treats this as fatal.
    """
    expected = settings.EMBEDDING_DIM
    provider = settings.EMBEDDING_PROVIDER
    model = _provider_embed_model(provider)
    try:
        vector = await _embed_with_provider(provider, ["healthcheck"], kind="document")
    except Exception as exc:
        logger.error(
            "embedding.consistency_check_failed",
            provider=provider,
            model=model,
            error=str(exc),
        )
        raise RuntimeError(
            f"Embedding healthcheck failed for provider '{provider}' "
            f"(model='{model}'): {exc}"
        ) from exc
    if not vector or not vector[0]:
        raise RuntimeError(
            f"Embedding provider '{provider}' (model='{model}') returned an "
            "empty vector during healthcheck"
        )
    actual = len(vector[0])
    if actual != expected:
        raise RuntimeError(
            f"Embedding dim mismatch: provider '{provider}' "
            f"(model='{model}') returned dim={actual}, expected "
            f"EMBEDDING_DIM={expected}. Update EMBEDDING_DIM in .env or pick "
            "a model whose dim matches."
        )
    logger.info(
        "embedding.consistency_ok",
        provider=provider,
        model=model,
        dim=actual,
    )


async def _embed_with_provider(
    provider: str,
    texts: list[str],
    kind: EmbedKind,
) -> list[list[float]]:
    if provider == "cohere":
        if "cohere" not in _embed_clients:
            _embed_clients["cohere"] = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
        co = _embed_clients["cohere"]
        # Cohere v3+ requires correct input_type for highest retrieval quality.
        input_type = "search_query" if kind == "query" else "search_document"
        response = await co.embed(
            texts=texts,
            model=settings.COHERE_EMBEDDING_MODEL,
            input_type=input_type,
        )
        return list(response.embeddings)
    if provider == "openrouter":
        key = "openrouter_embed"
        if key not in _embed_clients:
            _embed_clients[key] = openai.AsyncOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )
        client = _embed_clients[key]
        response = await client.embeddings.create(
            input=texts,
            model=settings.OPENROUTER_EMBEDDING_MODEL,
            timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
        )
        return [data.embedding for data in response.data]
    # default: openai
    key = "openai_embed"
    if key not in _embed_clients:
        _embed_clients[key] = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
        )
    client = _embed_clients[key]
    response = await client.embeddings.create(
        input=texts,
        model=settings.OPENAI_EMBEDDING_MODEL,
        timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
    )
    return [data.embedding for data in response.data]


async def _embed_with_failover(texts: list[str], kind: EmbedKind) -> list[list[float]]:
    if not texts:
        return []
    providers = _candidate_embed_providers(settings.EMBEDDING_PROVIDER)
    if not providers:
        raise RuntimeError("No available embedding provider configured")
    last_error: Exception | None = None
    for provider in providers:
        try:
            async for attempt in AsyncRetrying(
                wait=wait_exponential(multiplier=1, min=1, max=8),
                stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
                reraise=True,
            ):
                with attempt:
                    return await _embed_with_provider(provider, texts, kind)
        except Exception as exc:
            logger.warning(
                "llm.embed.provider_failed",
                provider=provider,
                kind=kind,
                error=str(exc),
            )
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("Embedding failed across all providers")


async def embed_query(text: str) -> list[float]:
    vectors = await _embed_with_failover([text], kind="query")
    return vectors[0] if vectors else []


async def embed_documents(texts: list[str]) -> list[list[float]]:
    return await _embed_with_failover(list(texts), kind="document")


async def embed(texts: list[str]) -> list[list[float]]:
    """Backwards-compatible alias for embedding documents.

    Older code paths and tests patch ``app.llm.client.embed`` directly. New
    code should call ``embed_query``/``embed_documents`` so Cohere-style
    providers get the correct ``input_type``.
    """
    return await embed_documents(texts)
