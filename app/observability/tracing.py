"""OpenTelemetry tracing helpers.

Tracing is **opt-in**: callers must install the ``otel`` extra
(``pip install -e ".[otel]"``) and set ``OTEL_TRACING_ENABLED=true`` to
activate. When unavailable, every helper here is a no-op so the rest of the
codebase can import :func:`stage_span` unconditionally.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import structlog

logger = structlog.get_logger()

_INITIALISED = False
_TRACER: Any = None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def setup_tracing(app: Any) -> bool:
    """Install OpenTelemetry tracing on the FastAPI app, if enabled.

    Returns ``True`` when tracing was wired up successfully. Falls back
    silently when:

    * ``OTEL_TRACING_ENABLED`` is not truthy.
    * The OpenTelemetry packages are not installed.
    """
    global _INITIALISED, _TRACER
    if _INITIALISED:
        return _TRACER is not None
    _INITIALISED = True

    if not _truthy(os.getenv("OTEL_TRACING_ENABLED")):
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except Exception as exc:  # pragma: no cover - exercised only with extra installed
        logger.info("otel.unavailable", error=str(exc))
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", "rag-engine")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter: Any
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint)
        except Exception as exc:
            logger.warning("otel.otlp_unavailable", error=str(exc))
            exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer("app")

    try:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    except Exception as exc:  # pragma: no cover
        logger.warning("otel.fastapi_instrumentation_failed", error=str(exc))

    logger.info("otel.tracing_enabled", service=service_name, exporter=type(exporter).__name__)
    return True


def get_tracer() -> Any | None:
    return _TRACER


@contextmanager
def stage_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Context manager that opens a span when tracing is on, no-op otherwise.

    Designed to wrap per-stage logic in :class:`QueryPipeline` and
    :class:`ChatPipeline`. Attribute values are coerced to strings to avoid
    OTel's "unsupported attribute type" warnings.
    """
    tracer = _TRACER
    if tracer is None:
        yield None
        return
    try:
        with tracer.start_as_current_span(name) as span:
            for k, v in attributes.items():
                try:
                    if isinstance(v, (str, int, float, bool)):
                        span.set_attribute(k, v)
                    else:
                        span.set_attribute(k, str(v))
                except Exception:
                    pass
            yield span
    except Exception:
        # Never let tracing failure break the app.
        yield None
