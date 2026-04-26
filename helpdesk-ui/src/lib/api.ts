import {
  ChatResponse,
  DocumentListItem,
  HealthResponse,
  HistoryTurn,
  IngestResponse,
  QueryResponse,
  SessionSummary,
} from "@/types"

export const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

function buildHeaders(extra: Record<string, string> = {}, demoMode?: boolean): HeadersInit {
  const headers: Record<string, string> = { ...extra }
  if (demoMode) headers["X-Demo-Mode"] = "true"
  return headers
}

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${endpoint}`, options)
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
): Promise<QueryResponse> {
  const body: Record<string, string> = { question }
  if (serviceCategory && serviceCategory !== "GENERAL") {
    body.service_category = serviceCategory
  }
  const res = await fetch(`${BASE}/query/stream`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, demoMode),
    body: JSON.stringify(body),
  })
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
      }
      if (parsed.type === "delta" && parsed.text) {
        onDelta(parsed.text)
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

export function getDocuments(): Promise<{ documents: DocumentListItem[]; total: number }> {
  return fetchAPI("/documents")
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

export interface ChatStreamPayload {
  session_id: string | null
  question: string
  service_category: string | null
  top_k?: number
  rerank_top_n?: number | null
}

export async function postChatStream(
  payload: ChatStreamPayload,
  onDelta: (text: string) => void,
  demoMode?: boolean,
): Promise<{ history?: HistoryTurn[]; session_id?: string; final?: ChatResponse }> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, demoMode),
    body: JSON.stringify({ top_k: 20, ...payload }),
  })
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
      }
      if (parsed.type === "delta" && parsed.text) {
        onDelta(parsed.text)
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
