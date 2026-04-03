import openai
import cohere
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential
from app.config import get_settings

settings = get_settings()

# ── Singleton clients (connection reuse = faster) ──────────────────────
_llm_clients: dict[str, openai.AsyncOpenAI] = {}
_embed_clients: dict[str, openai.AsyncOpenAI | cohere.AsyncClient] = {}


def _get_llm_client() -> openai.AsyncOpenAI:
    provider = settings.LLM_PROVIDER
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


def _get_model() -> str:
    provider = settings.LLM_PROVIDER
    if provider == "groq":
        return settings.GROQ_MODEL
    elif provider == "openrouter":
        return settings.OPENROUTER_MODEL
    else:
        return settings.OPENAI_MODEL


def _provider_model(provider: str) -> str:
    if provider == "groq":
        return settings.GROQ_MODEL
    if provider == "openrouter":
        return settings.OPENROUTER_MODEL
    return settings.OPENAI_MODEL


def _has_provider_key(provider: str) -> bool:
    if provider == "groq":
        return bool(settings.GROQ_API_KEY)
    if provider == "openrouter":
        return bool(settings.OPENROUTER_API_KEY)
    return bool(settings.OPENAI_API_KEY)


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


def _candidate_llm_providers(preferred: str) -> list[str]:
    ordered = [preferred, "openai", "openrouter", "groq"]
    seen = set()
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
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No available LLM provider configured")


async def complete_stream(prompt: str, system: str = "", model_override: str | None = None):
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
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=1200,
                timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
                stream=True,
            )
            async for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta.content or ""
                if delta:
                    yield delta
            return
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No available LLM provider configured")


async def embed(texts: list[str]) -> list[list[float]]:
    provider = settings.EMBEDDING_PROVIDER
    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
        reraise=True,
    ):
        with attempt:
            if provider == "cohere":
                if "cohere" not in _embed_clients:
                    _embed_clients["cohere"] = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
                co = _embed_clients["cohere"]
                response = await co.embed(
                    texts=texts,
                    model=settings.COHERE_EMBEDDING_MODEL,
                    input_type="search_document"
                )
                return response.embeddings
            elif provider == "openrouter":
                if "openrouter_embed" not in _embed_clients:
                    _embed_clients["openrouter_embed"] = openai.AsyncOpenAI(
                        api_key=settings.OPENROUTER_API_KEY,
                        base_url="https://openrouter.ai/api/v1",
                    )
                client = _embed_clients["openrouter_embed"]
                response = await client.embeddings.create(
                    input=texts,
                    model=settings.OPENROUTER_EMBEDDING_MODEL,
                    timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
                )
                return [data.embedding for data in response.data]
            else:
                if "openai_embed" not in _embed_clients:
                    _embed_clients["openai_embed"] = openai.AsyncOpenAI(
                        api_key=settings.OPENAI_API_KEY,
                        base_url="https://api.openai.com/v1",
                    )
                client = _embed_clients["openai_embed"]
                response = await client.embeddings.create(
                    input=texts,
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    timeout=settings.LLM_REQUEST_TIMEOUT_SEC,
                )
                return [data.embedding for data in response.data]
    return []
