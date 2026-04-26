"""Observability primitives — tracing, in-memory log buffer, metrics.

Importing this package never imports OpenTelemetry; tracing is opt-in via the
``otel`` extra and the :func:`app.observability.tracing.setup_tracing` helper.
"""

from app.observability.log_buffer import (
    LogEntry,
    add_log_entry,
    install_structlog_capture,
    recent_log_entries,
)
from app.observability.webhooks import dispatch_webhook, fire_and_forget

__all__ = [
    "LogEntry",
    "add_log_entry",
    "dispatch_webhook",
    "fire_and_forget",
    "install_structlog_capture",
    "recent_log_entries",
]
