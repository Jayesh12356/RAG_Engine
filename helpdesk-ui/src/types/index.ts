export interface SourceChunk {
  chunk_id:      string
  text:          string
  pdf_name:      string
  pdf_url:       string
  page_number:   number
  section_title: string
  score:         number
}

export interface QueryResponse {
  question:         string
  answer:           string
  confidence:       number
  confidence_label: "high" | "moderate" | "low" | "refused"
  sources:          SourceChunk[]
  service_category: string
  refused:          boolean
}

export interface DocumentListItem {
  document_id:  string
  pdf_name:     string
  service_name: string
  total_pages:  number
  total_chunks: number
  created_at:   string
}

export interface HealthResponse {
  status:             string
  llm_provider:       string
  embedding_provider: string
  vector_db:          string
  relational_db:      string
  demo_mode:          boolean
}

export interface IngestResponse {
  document_id:  string
  pdf_name:     string
  total_pages:  number
  total_chunks: number
  service_name: string
  status:       string
  error:        string | null
  task_id:      string | null
}

export interface HistoryTurn {
  id:               string
  session_id:       string
  role:             "user" | "assistant"
  content:          string
  confidence:       number | null
  service_category: string | null
  sources:          SourceChunk[]
  created_at:       string
}

export interface ChatRequest {
  session_id:       string | null
  question:         string
  service_category: string | null
  top_k:            number
  rerank_top_n:     number | null
}

export interface ChatResponse {
  session_id:        string
  turn_id:           string
  question:          string
  answer:            string
  confidence:        number
  confidence_label:  "high" | "moderate" | "low" | "refused"
  sources:           SourceChunk[]
  service_category:  string
  refused:           boolean
  history:           HistoryTurn[]
}

export interface SessionSummary {
  session_id:     string
  turn_count:     number
  last_active:    string
  first_question: string
}
