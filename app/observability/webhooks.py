"""Webhook dispatch for ``ingestion.complete`` / ``query.completed`` / ``query.refused``.

Each webhook subscription is a row in :class:`WebhookSubscriptionModel`. The
public entry point is :func:`dispatch_webhook`, called by the ingestion and
query/chat pipelines as fire-and-forget background tasks. The dispatcher:

* Looks up the enabled subscriptions for the event.
* Posts the JSON payload (with a ``X-Helpdesk-Event`` header and an optional
  HMAC-SHA256 signature when the subscription has a ``secret``).
* Swallows network errors per-subscription so one bad URL never affects the
  others or the pipeline that fired the event.

Outbound traffic is gated by the ``WEBHOOKS_ENABLED`` environment variable
(default ``true``) so operators can globally pause delivery without touching
the database.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SEC = float(os.getenv("WEBHOOKS_TIMEOUT_SEC") or 5.0)


def _enabled() -> bool:
    raw = (os.getenv("WEBHOOKS_ENABLED") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def _post(subscription: dict, body: bytes, headers: dict[str, str]) -> bool:
    """Best-effort HTTP POST to a single subscription URL.

    Returns ``True`` when the remote responded with a 2xx, ``False`` for
    every other outcome (network error, non-2xx, missing httpx).
    """
    try:
        import httpx  # type: ignore
    except Exception:
        # ``httpx`` ships in the dev extra; fall back to no-op when missing
        # so production-only installs don't crash.
        logger.debug("webhook.httpx_unavailable")
        return False

    url = subscription.get("url")
    if not url:
        return False

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SEC) as client:
            response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
            logger.info(
                "webhook.delivered",
                webhook_event=subscription.get("event"),
                url=url,
                status=response.status_code,
            )
            return True
    except Exception as exc:
        logger.warning(
            "webhook.delivery_failed",
            webhook_event=subscription.get("event"),
            url=url,
            error=str(exc),
        )
        return False


async def deliver_to_subscription(
    subscription: dict,
    payload: dict[str, Any],
    *,
    event_override: str | None = None,
) -> bool:
    """Deliver a payload to a single subscription, ignoring the global gate.

    Used by the "Test webhook" management endpoint so operators can verify
    a subscription URL even when the subscription is paused.
    """
    event = event_override or subscription.get("event") or "webhook.test"
    body = json.dumps({"event": event, "payload": payload}, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Helpdesk-Event": event,
        "User-Agent": "helpdesk-chatbot/webhooks",
    }
    secret = subscription.get("secret")
    if secret:
        headers["X-Helpdesk-Signature"] = _sign(secret, body)
    return await _post(subscription, body, headers)


async def dispatch_webhook(event: str, payload: dict[str, Any]) -> int:
    """Fan-out a single ``event`` to every enabled subscription.

    Returns the number of subscriptions that received a delivery attempt.
    Looks up subscriptions on every call (fine for low-volume webhooks), so
    operators can add or disable subscriptions without restarting the app.
    """
    if not _enabled():
        return 0

    try:
        from app.db.relational import list_webhooks
    except Exception as exc:
        logger.debug("webhook.db_unavailable", error=str(exc))
        return 0

    try:
        subscriptions = await list_webhooks(event)
    except Exception as exc:
        logger.debug("webhook.list_failed", webhook_event=event, error=str(exc))
        return 0

    if not subscriptions:
        return 0

    body = json.dumps({"event": event, "payload": payload}, default=str).encode("utf-8")
    base_headers = {
        "Content-Type": "application/json",
        "X-Helpdesk-Event": event,
        "User-Agent": "helpdesk-chatbot/webhooks",
    }

    coros = []
    for sub in subscriptions:
        headers = dict(base_headers)
        secret = sub.get("secret")
        if secret:
            headers["X-Helpdesk-Signature"] = _sign(secret, body)
        coros.append(_post(sub, body, headers))

    if coros:
        await asyncio.gather(*coros, return_exceptions=True)
    return len(coros)


def fire_and_forget(event: str, payload: dict[str, Any]) -> None:
    """Schedule a webhook dispatch without awaiting it.

    Safe to call from synchronous contexts and from inside the running event
    loop. When no event loop is active the call becomes a no-op so test
    harnesses don't accidentally start background tasks.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(dispatch_webhook(event, payload))
