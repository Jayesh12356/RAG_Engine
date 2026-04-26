import {
  BranchSessionResponse,
  ChatResponse,
  Citation,
  DocumentListItem,
  HealthResponse,
  HistoryTurn,
  IngestResponse,
  QueryResponse,
  SessionSummary,
} from "@/types"

export interface StreamEventHandlers {
  onCitations?: (items: Citation[]) => void
  onProgress?: (stage: string, payload?: Record<string, unknown>) => void
}

export const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

function buildHeaders(extra: Record<string, string> = {}, demoMode?: boolean): HeadersInit {
  const headers: Record<string, string> = { ...extra }
  if (demoMode) headers["X-Demo-Mode"] = "true"
  return headers
}

export class RateLimitError extends Error {
  status = 429
  retryAfterSeconds: number
  scope: string

  constructor(message: string, retryAfterSeconds: number, scope: string) {
    super(message)
    this.name = "RateLimitError"
    this.retryAfterSeconds = Math.max(1, Math.round(retryAfterSeconds || 1))
    this.scope = scope
  }
}

export function isRateLimitError(err: unknown): err is RateLimitError {
  return err instanceof RateLimitError
}

async function parseRateLimit(res: Response): Promise<RateLimitError> {
  let retry = Number(res.headers.get("Retry-After") ?? "1")
  let scope = res.headers.get("X-RateLimit-Scope") ?? "request"
  let message = "You're sending requests a little too fast. Hang on a moment."
  try {
    const errJson = await res.json()
    const detail = errJson?.detail
    if (typeof detail === "object" && detail) {
      if (typeof detail.message === "string") message = detail.message
      if (typeof detail.retry_after_seconds === "number")
        retry = detail.retry_after_seconds
      if (typeof detail.scope === "string") scope = detail.scope
    } else if (typeof detail === "string") {
      message = detail
    }
  } catch {
    /* not JSON — keep the friendly default */
  }
  if (!Number.isFinite(retry) || retry <= 0) retry = 1
  return new RateLimitError(message, retry, scope)
}

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${endpoint}`, options)
  if (res.status === 429) {
    throw await parseRateLimit(res)
  }
  if (!res.ok) {
    let errMessage = `HTTP ${res.status} error`
    try {
      const errJson = await res.json()
      errMessage = errJson.detail || errJson.error || errMessage
    } catch {
      /* not json */
    }
    throw new Error(errMessage)
  }
  return (await res.json()) as T
}

// ── Health ──────────────────────────────────────────────────────────────────
export function getHealth(): Promise<HealthResponse> {
  return fetchAPI<HealthResponse>("/health")
}

// ── Single-shot Query ───────────────────────────────────────────────────────
export function postQuery(
  question: string,
  serviceCategory?: string,
  demoMode?: boolean,
): Promise<QueryResponse> {
  const body: Record<string, string> = { question }
  if (serviceCategory && serviceCategory !== "GENERAL") {
    body.service_category = serviceCategory
  }
  return fetchAPI<QueryResponse>("/query", {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, demoMode),
    body: JSON.stringify(body),
  })
}

export async function postQueryStream(
  question: string,
  onDelta: (text: string) => void,
  serviceCategory?: string,
  demoMode?: boolean,
  handlers?: StreamEventHandlers,
): Promise<QueryResponse> {
  const body: Record<string, string | boolean> = { question }
  if (serviceCategory && serviceCategory !== "GENERAL") {
    body.service_category = serviceCategory
  }
  if (handlers?.onCitations) {
    body.include_citations = true
  }
  const res = await fetch(`${BASE}/query/stream`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, demoMode),
    body: JSON.stringify(body),
  })
  if (res.status === 429) {
    throw await parseRateLimit(res)
  }
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status} error`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let finalPayload: QueryResponse | null = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() || ""
    for (const event of events) {
      if (!event.startsWith("data: ")) continue
      const parsed = JSON.parse(event.slice(6)) as {
        type: string
        text?: string
        payload?: QueryResponse
        items?: Citation[]
        stage?: string
        data?: Record<string, unknown>
      }
      if (parsed.type === "delta" && parsed.text) {
        onDelta(parsed.text)
      } else if (parsed.type === "citations" && parsed.items) {
        handlers?.onCitations?.(parsed.items)
      } else if (parsed.type === "progress" && parsed.stage) {
        handlers?.onProgress?.(parsed.stage, parsed.data)
      } else if (parsed.type === "final" && parsed.payload) {
        finalPayload = parsed.payload
      }
    }
  }
  if (!finalPayload) {
    throw new Error("Missing final response payload from stream")
  }
  return finalPayload
}

// ── Ingest / Documents ──────────────────────────────────────────────────────
export function postIngest(
  file: File,
  serviceNameOverride?: string,
  background?: boolean,
  demoMode?: boolean,
): Promise<IngestResponse> {
  const formData = new FormData()
  formData.append("file", file)
  if (serviceNameOverride) formData.append("service_name_override", serviceNameOverride)
  if (background) formData.append("background", "true")
  return fetchAPI<IngestResponse>("/ingest", {
    method: "POST",
    headers: buildHeaders({}, demoMode),
    body: formData,
  })
}

export interface IngestTaskProgress {
  task_id: string
  document_id?: string | null
  filename?: string
  status: "queued" | "running" | "complete" | "failed" | string
  stage?: string | null
  progress?: number | null
  total_chunks?: number | null
  processed_chunks?: number | null
  message?: string | null
  error?: string | null
}

export function getIngestStatus(taskId: string): Promise<IngestTaskProgress> {
  return fetchAPI(`/ingest/${taskId}/status`)
}

// ── Observability ───────────────────────────────────────────────────────────
export interface LogEntryItem {
  seq: number
  ts: number
  level: string
  event: string | null
  extra: Record<string, unknown>
}

export function getRecentLogs(
  limit = 200,
  level?: string,
): Promise<{ entries: LogEntryItem[] }> {
  const qs = new URLSearchParams()
  qs.set("limit", String(limit))
  if (level) qs.set("level", level)
  return fetchAPI(`/logs/recent?${qs.toString()}`)
}

export interface MetricsRecentItem {
  minute: string
  total: number
  refusals: number
  p50_ms: number
  p95_ms: number
  mean_confidence: number
  cost_usd: number
}

export function getRecentMetrics(
  minutes = 60,
): Promise<{ points: MetricsRecentItem[] }> {
  return fetchAPI(`/metrics/recent?minutes=${encodeURIComponent(String(minutes))}`)
}

/**
 * Subscribe to /ingest/{task_id}/events SSE.  Resolves when the task hits a
 * terminal state ("complete" / "failed").
 */
export async function streamIngestEvents(
  taskId: string,
  onProgress: (event: IngestTaskProgress) => void,
): Promise<IngestTaskProgress> {
  const res = await fetch(`${BASE}/ingest/${taskId}/events`)
  if (!res.ok || !res.body) {
    throw new Error(`Stream HTTP ${res.status}`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let last: IngestTaskProgress | null = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""
    for (const evt of events) {
      const dataLines = evt
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim())
      if (!dataLines.length) continue
      try {
        const parsed = JSON.parse(dataLines.join("\n")) as IngestTaskProgress & {
          type?: string
        }
        if (parsed.type === "error") continue
        last = parsed
        onProgress(parsed)
        if (parsed.status === "complete" || parsed.status === "failed") {
          return parsed
        }
      } catch {
        /* skip malformed line */
      }
    }
  }
  if (!last) throw new Error("Stream ended without progress")
  return last
}

export function getDocuments(
  options: { tag?: string } = {},
): Promise<{ documents: DocumentListItem[]; total: number }> {
  const qs = options.tag ? `?tag=${encodeURIComponent(options.tag)}` : ""
  return fetchAPI(`/documents${qs}`)
}

export function getDocumentChunks(
  documentId: string,
): Promise<{ document_id: string; chunks: Record<string, unknown>[]; total: number }> {
  return fetchAPI(`/documents/${documentId}/chunks`)
}

export function deleteDocument(
  documentId: string,
): Promise<{ status: string; chunks_removed: number }> {
  return fetchAPI(`/documents/${documentId}`, { method: "DELETE" })
}

// ── Tags / Spaces ───────────────────────────────────────────────────────────
export function getTags(): Promise<{ tags: string[] }> {
  return fetchAPI("/tags")
}

export function setDocumentTags(
  documentId: string,
  tags: string[],
): Promise<{ document_id: string; tags: string[] }> {
  return fetchAPI(`/documents/${documentId}/tags`, {
    method: "PUT",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ tags }),
  })
}

// ── Chat sessions ───────────────────────────────────────────────────────────
export function getChatSessions(
  demoMode?: boolean,
): Promise<{ sessions: SessionSummary[]; total: number }> {
  return fetchAPI("/chat/sessions", { headers: buildHeaders({}, demoMode) })
}

export function getChatHistory(
  sessionId: string,
  demoMode?: boolean,
): Promise<{ session_id: string; turns: HistoryTurn[]; total: number }> {
  return fetchAPI(`/chat/${sessionId}/history`, { headers: buildHeaders({}, demoMode) })
}

export function deleteChatSession(
  sessionId: string,
  demoMode?: boolean,
): Promise<{ status: string }> {
  return fetchAPI(`/chat/${sessionId}`, {
    method: "DELETE",
    headers: buildHeaders({}, demoMode),
  })
}

export function branchChatSession(
  sessionId: string,
  parentTurnId: string,
  options?: { title?: string; demoMode?: boolean },
): Promise<BranchSessionResponse> {
  const body = JSON.stringify({
    parent_turn_id: parentTurnId,
    title: options?.title ?? null,
  })
  return fetchAPI(`/chat/sessions/${sessionId}/branch`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, options?.demoMode),
    body,
  })
}

export interface ChatStreamPayload {
  session_id: string | null
  question: string
  service_category: string | null
  top_k?: number
  rerank_top_n?: number | null
  include_citations?: boolean
}

export async function postChatStream(
  payload: ChatStreamPayload,
  onDelta: (text: string) => void,
  demoMode?: boolean,
  handlers?: StreamEventHandlers,
): Promise<{ history?: HistoryTurn[]; session_id?: string; final?: ChatResponse }> {
  const wantCitations = handlers?.onCitations !== undefined
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, demoMode),
    body: JSON.stringify({
      top_k: 20,
      ...payload,
      include_citations: payload.include_citations ?? wantCitations,
    }),
  })
  if (res.status === 429) {
    throw await parseRateLimit(res)
  }
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status} error`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let final: ChatResponse | null = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() || ""
    for (const event of events) {
      if (!event.startsWith("data: ")) continue
      const parsed = JSON.parse(event.slice(6)) as {
        type: string
        text?: string
        payload?: ChatResponse
        items?: Citation[]
        stage?: string
        data?: Record<string, unknown>
      }
      if (parsed.type === "delta" && parsed.text) {
        onDelta(parsed.text)
      } else if (parsed.type === "citations" && parsed.items) {
        handlers?.onCitations?.(parsed.items)
      } else if (parsed.type === "progress" && parsed.stage) {
        handlers?.onProgress?.(parsed.stage, parsed.data)
      } else if (parsed.type === "final" && parsed.payload) {
        final = parsed.payload
      }
    }
  }
  return {
    history: final?.history,
    session_id: final?.session_id,
    final: final ?? undefined,
  }
}

// ── User preferences ────────────────────────────────────────────────────────
export interface BookmarkPayload {
  id: string
  question: string
  answer?: string | null
  createdAt?: string | null
}

export interface UserPreferencesPayload {
  rag_engine_uid: string
  bookmarks: BookmarkPayload[]
  settings: Record<string, unknown>
  updated_at?: string | null
}

export function getPreferences(): Promise<UserPreferencesPayload> {
  return fetchAPI("/preferences")
}

export function putPreferences(
  patch: { bookmarks?: BookmarkPayload[]; settings?: Record<string, unknown> },
): Promise<UserPreferencesPayload> {
  return fetchAPI("/preferences", {
    method: "PUT",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(patch),
  })
}

export interface SettingsSchemaField {
  key: string
  type: "bool" | "int" | "float" | "string" | "enum"
  default: unknown
  current: unknown
  description?: string
  enum?: string[] | null
}

export interface SettingsSchemaResponse {
  fields: SettingsSchemaField[]
  overrides: Record<string, unknown>
}

export function getSettingsSchema(): Promise<SettingsSchemaResponse> {
  return fetchAPI("/settings/schema")
}

// ── Webhooks ────────────────────────────────────────────────────────────────
export interface WebhookSubscriptionItem {
  id: string
  event: string
  url: string
  enabled: boolean
  secret?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface WebhookListResponse {
  events: string[]
  subscriptions: WebhookSubscriptionItem[]
}

export function getWebhooks(): Promise<WebhookListResponse> {
  return fetchAPI("/webhooks")
}

export function createWebhook(payload: {
  event: string
  url: string
  enabled?: boolean
  secret?: string | null
}): Promise<WebhookSubscriptionItem> {
  return fetchAPI("/webhooks", {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  })
}

export function updateWebhook(
  id: string,
  payload: { enabled?: boolean; url?: string; secret?: string | null },
): Promise<WebhookSubscriptionItem> {
  return fetchAPI(`/webhooks/${id}`, {
    method: "PATCH",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  })
}

export function deleteWebhook(id: string): Promise<{ id: string; status: string }> {
  return fetchAPI(`/webhooks/${id}`, { method: "DELETE" })
}

export function testWebhook(id: string): Promise<{ id: string; delivered: number }> {
  return fetchAPI(`/webhooks/${id}/test`, { method: "POST" })
}
