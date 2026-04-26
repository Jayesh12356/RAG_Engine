export interface SourceChunk {
  chunk_id:      string
  text:          string
  pdf_name:      string
  pdf_url:       string
  page_number:   number
  section_title: string
  score:         number
}

export interface TextSpan {
  text:  string
  start: number
  end:   number
}

export interface Citation {
  chunk_id:      string
  document_id:   string
  pdf_name:      string
  page_number:   number
  section_title: string
  score:         number
  text_span?:    TextSpan | null
}

export interface QueryResponse {
  question:         string
  answer:           string
  confidence:       number
  confidence_label: "high" | "moderate" | "low" | "refused"
  sources:          SourceChunk[]
  citations?:       Citation[]
  service_category: string
  refused:          boolean
  visual_capable?:  boolean
  cost_usd?:        number
  latency_ms?:      number
}

export interface DocumentListItem {
  document_id:  string
  pdf_name:     string
  service_name: string
  total_pages:  number
  total_chunks: number
  created_at:   string
  summary?:     string | null
  tags?:        string[]
  version?:     number
}

export interface HealthDbPoolStats {
  size?:         number | null
  checked_in?:   number | null
  checked_out?:  number | null
  overflow?:     number | null
}

export interface HealthResponse {
  status:             string
  llm_provider:       string
  embedding_provider: string
  vector_db:          string
  relational_db:      string
  demo_mode:          boolean
  visual_capable?:    boolean
  image_gen_active?:  boolean
  uptime_seconds?:    number | null
  db_pool?:           HealthDbPoolStats | null
  vector_index_size?: number | null
  queue_depth?:       number | null
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
  citations?:        Citation[]
  service_category:  string
  refused:           boolean
  history:           HistoryTurn[]
  visual_capable?:   boolean
  cost_usd?:         number
  latency_ms?:       number
}

export interface SessionSummary {
  session_id:        string
  turn_count:        number
  last_active:       string
  first_question:    string
  parent_session_id?: string | null
  parent_turn_id?:    string | null
  title?:             string | null
}

export interface BranchSessionResponse {
  session_id:        string
  parent_session_id: string
  parent_turn_id:    string
  copied_turns:      number
  title?:            string | null
}
