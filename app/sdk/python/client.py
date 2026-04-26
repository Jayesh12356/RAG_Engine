"""Auto-generated synchronous + async client for the helpdesk RAG API.

Do not edit by hand — regenerate with ``python -m scripts.gen_sdk``.
"""
from __future__ import annotations

from typing import Any

import httpx


class HelpdeskClient:
    """Thin httpx-based wrapper around the helpdesk RAG API.

    The client mirrors the cookie-based auth stub used by the FastAPI
    backend: pass ``cookie="rag_engine_uid=…"`` (or attach an existing
    ``httpx.Cookies`` jar) to keep per-user preferences in scope.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        cookie: str | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        headers = {"User-Agent": "helpdesk-sdk/1.0"}
        if cookie:
            headers["Cookie"] = cookie
        self._client = client or httpx.Client(
            base_url=self.base_url, timeout=timeout, headers=headers
        )

    def __enter__(self) -> "HelpdeskClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        response = self._client.request(method, path, params=params, json=json_body)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        ctype = response.headers.get("content-type", "")
        if "application/json" in ctype:
            return response.json()
        return response.content

    def health_check_health_get(self) -> dict[str, Any]:
        """Health Check"""
        path = f"/health"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def ingest_document_ingest_post(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ingest Document"""
        path = f"/ingest"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def get_ingest_status_ingest_task_id_status_get(self, task_id: str) -> dict[str, Any]:
        """Get Ingest Status"""
        path = f"/ingest/{task_id}/status"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def stream_ingest_events_ingest_task_id_events_get(self, task_id: str) -> Any:
        """Stream Ingest Events"""
        path = f"/ingest/{task_id}/events"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def query_pipeline_query_post(self, body: dict[str, Any] | None = None) -> Any:
        """Query Pipeline"""
        path = f"/query"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def query_pipeline_stream_query_stream_post(self, body: dict[str, Any] | None = None) -> Any:
        """Query Pipeline Stream"""
        path = f"/query/stream"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def chat_endpoint_chat_post(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Chat Endpoint"""
        path = f"/chat"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def chat_stream_endpoint_chat_stream_post(self, body: dict[str, Any] | None = None) -> Any:
        """Chat Stream Endpoint"""
        path = f"/chat/stream"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def get_chat_history_chat_session_id_history_get(self, session_id: str, limit: int | None = None) -> dict[str, Any]:
        """Get Chat History"""
        path = f"/chat/{session_id}/history"
        params: dict[str, Any] = {}
        if limit is not None: params['limit'] = limit
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def delete_chat_session_chat_session_id_delete(self, session_id: str) -> dict[str, Any]:
        """Delete Chat Session"""
        path = f"/chat/{session_id}"
        params = None
        json_body = None
        return self._request('DELETE', path, params=params, json_body=json_body)

    def get_chat_sessions_chat_sessions_get(self) -> dict[str, Any]:
        """Get Chat Sessions"""
        path = f"/chat/sessions"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def settings_schema_settings_schema_get(self) -> dict[str, Any]:
        """Settings Schema"""
        path = f"/settings/schema"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def get_preferences_preferences_get(self) -> dict[str, Any]:
        """Get Preferences"""
        path = f"/preferences"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def update_preferences_preferences_put(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Update Preferences"""
        path = f"/preferences"
        params = None
        json_body = body
        return self._request('PUT', path, params=params, json_body=json_body)

    def branch_chat_session_chat_sessions_session_id_branch_post(self, session_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Branch Chat Session"""
        path = f"/chat/sessions/{session_id}/branch"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def serve_pdf_pdfs_pdf_name_get(self, pdf_name: str) -> Any:
        """Serve Pdf"""
        path = f"/pdfs/{pdf_name}"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def serve_pdf_by_document_id_pdfs_by_id_document_id_get(self, document_id: str) -> Any:
        """Serve Pdf By Document Id"""
        path = f"/pdfs/by-id/{document_id}"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def list_documents_documents_get(self, tag: str | None | None = None) -> dict[str, Any]:
        """List Documents"""
        path = f"/documents"
        params: dict[str, Any] = {}
        if tag is not None: params['tag'] = tag
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def list_tags_tags_get(self) -> dict[str, Any]:
        """List Tags"""
        path = f"/tags"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def list_recent_metrics_metrics_recent_get(self, minutes: int | None = None) -> dict[str, Any]:
        """List Recent Metrics"""
        path = f"/metrics/recent"
        params: dict[str, Any] = {}
        if minutes is not None: params['minutes'] = minutes
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def list_webhook_subscriptions_webhooks_get(self) -> dict[str, Any]:
        """List Webhook Subscriptions"""
        path = f"/webhooks"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def create_webhook_subscription_webhooks_post(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create Webhook Subscription"""
        path = f"/webhooks"
        params = None
        json_body = body
        return self._request('POST', path, params=params, json_body=json_body)

    def patch_webhook_subscription_webhooks_webhook_id_patch(self, webhook_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Patch Webhook Subscription"""
        path = f"/webhooks/{webhook_id}"
        params = None
        json_body = body
        return self._request('PATCH', path, params=params, json_body=json_body)

    def delete_webhook_subscription_webhooks_webhook_id_delete(self, webhook_id: str) -> dict[str, Any]:
        """Delete Webhook Subscription"""
        path = f"/webhooks/{webhook_id}"
        params = None
        json_body = None
        return self._request('DELETE', path, params=params, json_body=json_body)

    def test_webhook_subscription_webhooks_webhook_id_test_post(self, webhook_id: str) -> dict[str, Any]:
        """Test Webhook Subscription"""
        path = f"/webhooks/{webhook_id}/test"
        params = None
        json_body = None
        return self._request('POST', path, params=params, json_body=json_body)

    def list_recent_logs_logs_recent_get(self, limit: int | None = None, level: str | None | None = None) -> dict[str, Any]:
        """List Recent Logs"""
        path = f"/logs/recent"
        params: dict[str, Any] = {}
        if limit is not None: params['limit'] = limit
        if level is not None: params['level'] = level
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def update_document_tags_documents_document_id_tags_put(self, document_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Update Document Tags"""
        path = f"/documents/{document_id}/tags"
        params = None
        json_body = body
        return self._request('PUT', path, params=params, json_body=json_body)

    def list_chunks_documents_document_id_chunks_get(self, document_id: str) -> dict[str, Any]:
        """List Chunks"""
        path = f"/documents/{document_id}/chunks"
        params = None
        json_body = None
        return self._request('GET', path, params=params, json_body=json_body)

    def delete_document_documents_document_id_delete(self, document_id: str) -> dict[str, Any]:
        """Delete Document"""
        path = f"/documents/{document_id}"
        params = None
        json_body = None
        return self._request('DELETE', path, params=params, json_body=json_body)
