import { HealthResponse, QueryResponse, IngestResponse, DocumentListItem } from '@/types'

export const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const res = await fetch(`${BASE}${endpoint}`, options)
  if (!res.ok) {
    let errMessage = `HTTP ${res.status} error`
    try {
      const errJson = await res.json()
      errMessage = errJson.detail || errJson.error || errMessage
    } catch {
      // Ignore if not json
    }
    throw new Error(errMessage)
  }
  return res.json()
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchAPI('/health')
}

export async function postQuery(question: string, serviceCategory?: string, demoMode?: boolean): Promise<QueryResponse> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  if (demoMode) {
    headers['X-Demo-Mode'] = 'true'
  }
  
  const body: Record<string, string> = { question }
  if (serviceCategory && serviceCategory !== 'GENERAL') {
    body.service_category = serviceCategory
  }
  
  return fetchAPI('/query', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
}

export async function postQueryStream(
  question: string,
  onDelta: (text: string) => void,
  serviceCategory?: string,
  demoMode?: boolean
): Promise<QueryResponse> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (demoMode) headers['X-Demo-Mode'] = 'true'
  const body: Record<string, string> = { question }
  if (serviceCategory && serviceCategory !== 'GENERAL') {
    body.service_category = serviceCategory
  }
  const res = await fetch(`${BASE}/query/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status} error`)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalPayload: QueryResponse | null = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const event of events) {
      if (!event.startsWith('data: ')) continue
      const raw = event.slice(6)
      const parsed = JSON.parse(raw) as { type: string; text?: string; payload?: QueryResponse }
      if (parsed.type === 'delta' && parsed.text) {
        onDelta(parsed.text)
      } else if (parsed.type === 'final' && parsed.payload) {
        finalPayload = parsed.payload
      }
    }
  }
  if (!finalPayload) {
    throw new Error('Missing final response payload from stream')
  }
  return finalPayload
}

export async function postIngest(file: File, serviceNameOverride?: string, background?: boolean, demoMode?: boolean): Promise<IngestResponse> {
  const headers: HeadersInit = {}
  if (demoMode) {
    headers['X-Demo-Mode'] = 'true'
  }
  
  const formData = new FormData()
  formData.append('file', file)
  if (serviceNameOverride) {
    formData.append('service_name_override', serviceNameOverride)
  }
  if (background) {
    formData.append('background', 'true')
  }
  
  return fetchAPI('/ingest', {
    method: 'POST',
    headers,
    body: formData,
  })
}

export async function getDocuments(): Promise<{ documents: DocumentListItem[]; total: number }> {
  return fetchAPI('/documents')
}

export async function getDocumentChunks(documentId: string): Promise<{ document_id: string; chunks: Record<string, unknown>[]; total: number }> {
  return fetchAPI(`/documents/${documentId}/chunks`)
}

export async function deleteDocument(documentId: string): Promise<{ status: string; chunks_removed: number }> {
  return fetchAPI(`/documents/${documentId}`, {
    method: 'DELETE',
  })
}
