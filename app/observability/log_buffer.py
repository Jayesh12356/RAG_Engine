"""In-memory ring buffer of recent structured log events.

The buffer is a thread-safe deque keyed by monotonic insertion order. We
attach a ``structlog`` processor (:func:`install_structlog_capture`) so every
``logger.info / logger.warning / logger.error`` call automatically lands in
the ring without needing to refactor existing log sites.

The endpoint :func:`app.api.routes.recent_logs` exposes the buffer for the
``/app/status`` recent-activity tab.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Deque

# How many events to keep in memory. ~5KB per event * 500 = ~2.5MB worst case;
# adjust if the deployment becomes chattier.
_MAX_ENTRIES = 500


class LogEntry(dict):
    """Plain ``dict`` subclass so the buffer can serialise straight to JSON."""


_entries: Deque[LogEntry] = deque(maxlen=_MAX_ENTRIES)
_lock = threading.Lock()
_seq = 0


def add_log_entry(entry: dict[str, Any]) -> None:
    """Append a structured log event to the ring buffer.

    Adds a monotonic ``seq`` and unix ``ts`` so the UI can sort/dedupe even
    when several requests log the same event name in the same millisecond.
    """
    global _seq
    payload: dict[str, Any] = dict(entry)
    with _lock:
        _seq += 1
        payload.setdefault("ts", time.time())
        payload["seq"] = _seq
        _entries.append(LogEntry(payload))


def recent_log_entries(limit: int = 200, level: str | None = None) -> list[LogEntry]:
    """Return the latest ``limit`` log entries, newest last.

    ``level`` filters case-insensitively against the structlog ``level`` key
    (``info`` / ``warning`` / ``error``); pass ``None`` to keep everything.
    """
    with _lock:
        snapshot = list(_entries)
    if level:
        wanted = level.lower()
        snapshot = [e for e in snapshot if str(e.get("level", "")).lower() == wanted]
    if limit > 0:
        snapshot = snapshot[-limit:]
    return snapshot


def _structlog_processor(logger, method_name, event_dict):  # noqa: ARG001
    """structlog processor that mirrors each event into the ring buffer."""
    try:
        captured = dict(event_dict)
        captured.setdefault("level", method_name)
        # ``timestamp`` is added by structlog's TimeStamper, but mirror to ts
        # for a uniform schema.
        if "timestamp" in captured and "ts" not in captured:
            captured["ts"] = captured["timestamp"]
        add_log_entry(captured)
    except Exception:
        # Never let observability blow up a real log call.
        pass
    return event_dict


def install_structlog_capture() -> None:
    """Wire the buffer into structlog's processor chain (idempotent).

    Call once at application startup. We deliberately do not replace existing
    processors; we prepend ours so the captured events keep their full context.
    """
    try:
        import structlog  # local import keeps observability importable in tests
    except Exception:
        return

    config = structlog.get_config()
    processors = list(config.get("processors", []))
    if any(getattr(p, "__name__", "") == "_structlog_processor" for p in processors):
        return  # already installed
    processors.insert(0, _structlog_processor)
    structlog.configure(processors=processors)
