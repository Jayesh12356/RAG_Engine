// Auto-generated from /openapi.json — do not edit.

export interface Body_ingest_document_ingest_post {
  file: string;
  service_name_override?: string | null;
  background?: boolean;
}

export interface BookmarkItem {
  id: string;
  question: string;
  answer?: string | null;
  createdAt?: string | null;
}

export interface BranchSessionRequest {
  parent_turn_id: string;
  title?: string | null;
}

export interface BranchSessionResponse {
  session_id: string;
  parent_session_id: string;
  parent_turn_id: string;
  copied_turns: number;
  title?: string | null;
}

export interface ChatRequest {
  session_id?: string | null;
  question: string;
  service_category?: string | null;
  top_k?: number;
  rerank_top_n?: number | null;
  include_citations?: boolean | null;
  tags?: string[];
}

export interface ChatResponse {
  session_id: string;
  turn_id: string;
  question: string;
  answer: string;
  confidence: number;
  confidence_label: string;
  sources: SourceChunk[];
  citations?: Citation[];
  service_category: string;
  refused: boolean;
  history: HistoryTurn[];
  visual_capable?: boolean;
  cost_usd?: number;
  latency_ms?: number;
}

export interface ChunkListResponse {
  document_id: string;
  chunks: Record<string, unknown>[];
  total: number;
}

export interface Citation {
  chunk_id?: string;
  document_id?: string;
  pdf_name?: string;
  page_number?: number;
  section_title?: string;
  score?: number;
  text_span?: TextSpan | null;
}

export interface DeleteResponse {
  document_id: string;
  status: string;
  chunks_removed: number;
}

export interface DeleteSessionResponse {
  session_id: string;
  status: string;
  turns_removed: number;
}

export interface DocumentListItem {
  document_id: string;
  pdf_name: string;
  service_name: string;
  total_pages: number;
  total_chunks: number;
  created_at: string;
  summary?: string | null;
  tags?: string[];
  version?: number;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
  total: number;
}

export interface DocumentTagsRequest {
  tags: string[];
}

export interface DocumentTagsResponse {
  document_id: string;
  tags: string[];
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface HealthDbPoolStats {
  size?: number | null;
  checked_in?: number | null;
  checked_out?: number | null;
  overflow?: number | null;
}

export interface HealthResponse {
  status: string;
  llm_provider: string;
  embedding_provider: string;
  vector_db: string;
  relational_db: string;
  demo_mode: boolean;
  visual_capable?: boolean;
  image_gen_active?: boolean;
  uptime_seconds?: number | null;
  db_pool?: HealthDbPoolStats | null;
  vector_index_size?: number | null;
  queue_depth?: number | null;
}

export interface HistoryResponse {
  session_id: string;
  turns: unknown[];
  total: number;
}

export interface HistoryTurn {
  id: string;
  session_id: string;
  role: string;
  content: string;
  confidence?: number | null;
  service_category?: string | null;
  sources?: Record<string, unknown>[];
  created_at: string;
}

export interface IngestResponse {
  document_id?: string;
  pdf_name?: string;
  total_pages?: number;
  total_chunks?: number;
  service_name?: string;
  status: string;
  error?: string | null;
  task_id?: string | null;
}

export interface IngestTaskStatusResponse {
  task_id: string;
  document_id?: string | null;
  filename: string;
  status: string;
  stage: string;
  progress?: number;
  total_chunks?: number;
  processed_chunks?: number;
  message?: string | null;
  error?: string | null;
  started_at?: string;
  updated_at?: string;
}

export interface LogEntryItem {
  seq: number;
  ts: number;
  level: string;
  event?: string | null;
  extra?: Record<string, unknown>;
}

export interface MetricsRecentItem {
  minute: string;
  total?: number;
  refusals?: number;
  p50_ms?: number;
  p95_ms?: number;
  mean_confidence?: number;
  cost_usd?: number;
}

export interface MetricsRecentResponse {
  points: MetricsRecentItem[];
}

export interface QueryAPIRequest {
  question: string;
  service_category?: string | null;
  top_k?: number;
  rerank_top_n?: number | null;
  include_citations?: boolean | null;
  tags?: string[];
}

export interface RecentLogsResponse {
  entries: LogEntryItem[];
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface SessionSummary {
  session_id: string;
  turn_count: number;
  last_active: string;
  first_question: string;
  parent_session_id?: string | null;
  parent_turn_id?: string | null;
  title?: string | null;
}

export interface SettingsSchemaField {
  key: string;
  type: string;
  default: unknown;
  current: unknown;
  description?: string;
  enum?: string[] | null;
}

export interface SettingsSchemaResponse {
  fields: SettingsSchemaField[];
  overrides?: Record<string, unknown>;
}

export interface SourceChunk {
  chunk_id: string;
  text: string;
  pdf_name: string;
  pdf_url: string;
  page_number: number;
  section_title: string;
  score: number;
}

export interface TagsListResponse {
  tags: string[];
}

export interface TextSpan {
  text?: string;
  start?: number;
  end?: number;
}

export interface UserPreferencesResponse {
  rag_engine_uid: string;
  bookmarks?: BookmarkItem[];
  settings?: Record<string, unknown>;
  updated_at?: string | null;
}

export interface UserPreferencesUpdate {
  bookmarks?: BookmarkItem[] | null;
  settings?: Record<string, unknown> | null;
}

export interface ValidationError {
  loc: string | number[];
  msg: string;
  type: string;
}

export interface WebhookCreateRequest {
  event: string;
  url: string;
  enabled?: boolean;
  secret?: string | null;
}

export interface WebhookListResponse {
  events: string[];
  subscriptions: WebhookSubscriptionItem[];
}

export interface WebhookSubscriptionItem {
  id: string;
  event: string;
  url: string;
  enabled?: boolean;
  secret?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WebhookUpdateRequest {
  enabled?: boolean | null;
  url?: string | null;
  secret?: string | null;
}
