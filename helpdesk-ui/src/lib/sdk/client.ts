// Auto-generated client for the helpdesk RAG API.
// Do not edit by hand — regenerate with `python -m scripts.gen_sdk`.

import type * as Models from "./models"

export interface HelpdeskClientOptions {
  baseUrl?: string
  fetchImpl?: typeof fetch
  cookie?: string
}

export class HelpdeskAPIError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request(
  baseUrl: string,
  fetchImpl: typeof fetch,
  cookie: string | undefined,
  method: string,
  path: string,
  params?: Record<string, unknown>,
  body?: unknown,
): Promise<unknown> {
  const url = new URL(baseUrl.replace(/\/$/, "") + path, baseUrl.includes("://") ? undefined : "http://localhost")
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue
      url.searchParams.set(k, String(v))
    }
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (cookie) headers["Cookie"] = cookie
  const response = await fetchImpl(url.toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
  })
  if (!response.ok) {
    let parsed: unknown = null
    try {
      parsed = await response.json()
    } catch {
      /* ignore */
    }
    throw new HelpdeskAPIError(response.status, parsed, `${method} ${path} failed: ${response.status}`)
  }
  if (response.status === 204) return null
  const contentType = response.headers.get("content-type") || ""
  if (contentType.includes("application/json")) return response.json()
  return response.text()
}

export function createHelpdeskClient(opts: HelpdeskClientOptions = {}) {
  const baseUrl = (opts.baseUrl || "").replace(/\/$/, "")
  const fetchImpl = opts.fetchImpl || fetch
  const cookie = opts.cookie

  return {
    /** Health Check */
    async healthCheckHealthGet(): Promise<Models.HealthResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/health`, undefined, undefined)) as Models.HealthResponse
    },
    /** Ingest Document */
    async ingestDocumentIngestPost(body?: unknown): Promise<Models.IngestResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/ingest`, undefined, body)) as Models.IngestResponse
    },
    /** Get Ingest Status */
    async getIngestStatusIngestTaskIdStatusGet(task_id: string): Promise<Models.IngestTaskStatusResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/ingest/${task_id}/status`, undefined, undefined)) as Models.IngestTaskStatusResponse
    },
    /** Stream Ingest Events */
    async streamIngestEventsIngestTaskIdEventsGet(task_id: string): Promise<unknown> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/ingest/${task_id}/events`, undefined, undefined)) as unknown
    },
    /** Query Pipeline */
    async queryPipelineQueryPost(body?: unknown): Promise<unknown> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/query`, undefined, body)) as unknown
    },
    /** Query Pipeline Stream */
    async queryPipelineStreamQueryStreamPost(body?: unknown): Promise<unknown> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/query/stream`, undefined, body)) as unknown
    },
    /** Chat Endpoint */
    async chatEndpointChatPost(body?: unknown): Promise<Models.ChatResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/chat`, undefined, body)) as Models.ChatResponse
    },
    /** Chat Stream Endpoint */
    async chatStreamEndpointChatStreamPost(body?: unknown): Promise<unknown> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/chat/stream`, undefined, body)) as unknown
    },
    /** Get Chat History */
    async getChatHistoryChatSessionIdHistoryGet(session_id: string, limit?: number): Promise<Models.HistoryResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/chat/${session_id}/history`, { limit: limit }, undefined)) as Models.HistoryResponse
    },
    /** Delete Chat Session */
    async deleteChatSessionChatSessionIdDelete(session_id: string): Promise<Models.DeleteSessionResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'DELETE', `/chat/${session_id}`, undefined, undefined)) as Models.DeleteSessionResponse
    },
    /** Get Chat Sessions */
    async getChatSessionsChatSessionsGet(): Promise<Models.SessionListResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/chat/sessions`, undefined, undefined)) as Models.SessionListResponse
    },
    /** Settings Schema */
    async settingsSchemaSettingsSchemaGet(): Promise<Models.SettingsSchemaResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/settings/schema`, undefined, undefined)) as Models.SettingsSchemaResponse
    },
    /** Get Preferences */
    async getPreferencesPreferencesGet(): Promise<Models.UserPreferencesResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/preferences`, undefined, undefined)) as Models.UserPreferencesResponse
    },
    /** Update Preferences */
    async updatePreferencesPreferencesPut(body?: unknown): Promise<Models.UserPreferencesResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'PUT', `/preferences`, undefined, body)) as Models.UserPreferencesResponse
    },
    /** Branch Chat Session */
    async branchChatSessionChatSessionsSessionIdBranchPost(session_id: string, body?: unknown): Promise<Models.BranchSessionResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/chat/sessions/${session_id}/branch`, undefined, body)) as Models.BranchSessionResponse
    },
    /** Serve Pdf */
    async servePdfPdfsPdfNameGet(pdf_name: string): Promise<unknown> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/pdfs/${pdf_name}`, undefined, undefined)) as unknown
    },
    /** Serve Pdf By Document Id */
    async servePdfByDocumentIdPdfsByIdDocumentIdGet(document_id: string): Promise<unknown> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/pdfs/by-id/${document_id}`, undefined, undefined)) as unknown
    },
    /** List Documents */
    async listDocumentsDocumentsGet(tag?: string | null): Promise<Models.DocumentListResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/documents`, { tag: tag }, undefined)) as Models.DocumentListResponse
    },
    /** List Tags */
    async listTagsTagsGet(): Promise<Models.TagsListResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/tags`, undefined, undefined)) as Models.TagsListResponse
    },
    /** List Recent Metrics */
    async listRecentMetricsMetricsRecentGet(minutes?: number): Promise<Models.MetricsRecentResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/metrics/recent`, { minutes: minutes }, undefined)) as Models.MetricsRecentResponse
    },
    /** List Webhook Subscriptions */
    async listWebhookSubscriptionsWebhooksGet(): Promise<Models.WebhookListResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/webhooks`, undefined, undefined)) as Models.WebhookListResponse
    },
    /** Create Webhook Subscription */
    async createWebhookSubscriptionWebhooksPost(body?: unknown): Promise<Models.WebhookSubscriptionItem> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/webhooks`, undefined, body)) as Models.WebhookSubscriptionItem
    },
    /** Patch Webhook Subscription */
    async patchWebhookSubscriptionWebhooksWebhookIdPatch(webhook_id: string, body?: unknown): Promise<Models.WebhookSubscriptionItem> {
      return (await request(baseUrl, fetchImpl, cookie, 'PATCH', `/webhooks/${webhook_id}`, undefined, body)) as Models.WebhookSubscriptionItem
    },
    /** Delete Webhook Subscription */
    async deleteWebhookSubscriptionWebhooksWebhookIdDelete(webhook_id: string): Promise<Record<string, unknown>> {
      return (await request(baseUrl, fetchImpl, cookie, 'DELETE', `/webhooks/${webhook_id}`, undefined, undefined)) as Record<string, unknown>
    },
    /** Test Webhook Subscription */
    async testWebhookSubscriptionWebhooksWebhookIdTestPost(webhook_id: string): Promise<Record<string, unknown>> {
      return (await request(baseUrl, fetchImpl, cookie, 'POST', `/webhooks/${webhook_id}/test`, undefined, undefined)) as Record<string, unknown>
    },
    /** List Recent Logs */
    async listRecentLogsLogsRecentGet(limit?: number, level?: string | null): Promise<Models.RecentLogsResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/logs/recent`, { limit: limit, level: level }, undefined)) as Models.RecentLogsResponse
    },
    /** Update Document Tags */
    async updateDocumentTagsDocumentsDocumentIdTagsPut(document_id: string, body?: unknown): Promise<Models.DocumentTagsResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'PUT', `/documents/${document_id}/tags`, undefined, body)) as Models.DocumentTagsResponse
    },
    /** List Chunks */
    async listChunksDocumentsDocumentIdChunksGet(document_id: string): Promise<Models.ChunkListResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'GET', `/documents/${document_id}/chunks`, undefined, undefined)) as Models.ChunkListResponse
    },
    /** Delete Document */
    async deleteDocumentDocumentsDocumentIdDelete(document_id: string): Promise<Models.DeleteResponse> {
      return (await request(baseUrl, fetchImpl, cookie, 'DELETE', `/documents/${document_id}`, undefined, undefined)) as Models.DeleteResponse
    },
  }
}
