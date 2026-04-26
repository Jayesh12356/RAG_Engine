# IT Helpdesk RAG System — User & Technical Manual

This manual reflects the current implementation in this repository, including:

- True hybrid retrieval (Qdrant dense + sparse with server-side RRF fusion).
- Optional LLM-driven query rewriting when initial signal is weak.
- MMR diversification + per-document caps.
- Calibrated confidence scoring and shared evidence/confidence gates across query and chat.
- Provider failover for completion **and** embeddings (with bounded retries on streaming).
- Optional grounded citations on `/query` and `/chat`.
- OCR (Tesseract + optional Vision LLM fallback) for image PDFs and standalone image files.
- Heading-aware chunking and BM25 corpus persistence between ingest and query.
- Universal document ingestion through a single format router — PDF, DOCX, XLSX/XLS/CSV, PPTX, TXT/Markdown/HTML/JSON, and images (PNG/JPG/WEBP/TIFF/BMP).

---

## 1) System Overview

The platform is a document-grounded assistant:

- Upload documents — PDFs, Word, Excel/CSV, PowerPoint, text, Markdown, HTML, JSON or images.
- Ask questions in Query mode or Chat mode.
- Receive structured answers with calibrated confidence, source chunks, and (optionally) grounded citations.
- Refuse cleanly when evidence is insufficient.

Core design goal: **accuracy over speed**. Latency is acceptable when it improves grounding.

---

## 2) End-to-End Data Flow

### Ingestion flow

1. Frontend uploads a document to `POST /ingest` (any format the router accepts — see [`app/ingestion/router.py`](../../app/ingestion/router.py)).
2. The format router dispatches by file extension to the right extractor: `pdf`, `docx`, `spreadsheet` (xlsx/xls/csv), `pptx`, `text` (txt/md/markdown/html/htm/json), or `image` (png/jpg/jpeg/webp/tiff/tif/bmp).
3. PDFs are sub-classified (`text_pdf`, `image_pdf`, `mixed_pdf`) and parsed with PyMuPDF for text plus Tesseract OCR for image pages, with an optional Vision-LLM fallback for low-confidence pages. Other formats use their dedicated extractor (python-docx, openpyxl/xlrd/pandas, python-pptx, beautifulsoup4 + markdown + chardet, Pillow + OCR).
4. Heading-aware chunking splits content while keeping headings attached to their first paragraph and preserving tables/lists.
5. Dense embeddings are generated via the configured provider (`embed_documents` with provider-failover for OpenAI / OpenRouter / Cohere; Cohere uses `input_type=search_document`).
6. Sparse BM25 vectors are computed; corpus statistics (idf, avgdl, k1, b) are persisted under `SPARSE_INDEX_DIR/bm25.json` so query-time encoding stays consistent.
7. Vectors and metadata are upserted into the configured vector DB. On Qdrant the collection uses **named dense + sparse vectors** so server-side hybrid retrieval can fuse them.
8. Document/chunk metadata persists to the relational DB.
9. Raw document bytes are stored through the configured PDF storage backend (relational table `document_files` or vector payload chunks); the same backend serves the original asset on demand for source links.

### Query flow (non-streaming)

1. `POST /query` receives the question.
2. Router classifies likely category and intent (keyword-based fast path).
3. Initial hybrid search runs concurrently with the router (dense + sparse + RRF on Qdrant, dense-only on Milvus).
4. **Optional query rewrite** (when `QUERY_REWRITE_ENABLED=true` and the top initial score < `QUERY_REWRITE_TRIGGER_SCORE`): an LLM rewrites the question with acronym expansions sourced from the same router keywords; the search re-runs with `top_k` boosted by intent (`troubleshoot` / `howto`).
5. Reranker scores the candidates (Cohere primary, lexical-overlap fallback).
6. **Diversification**: per-document cap (`MAX_PER_DOC`) followed by MMR (`MMR_LAMBDA`) when `MMR_ENABLED=true`.
7. Shared **evidence gate** (`app/query/gates.py`) checks `RELEVANCE_MIN_TOP_SCORE`, `RELEVANCE_MIN_SECOND_SCORE`, and `RELEVANCE_MIN_SCORE_GAP`.
8. Generator builds a category-aware system prompt and produces an answer with strict grounding rules.
9. **Calibrated confidence** blends top reranker score, top↔second margin, answer↔context Jaccard overlap, refusal phrase detection, and a length penalty.
10. Confidence gate refuses below `CONFIDENCE_THRESHOLD`; otherwise returns `QueryResponse` with optional `citations`.

### Query flow (streaming)

1. `POST /query/stream` runs the same retrieval / gating pipeline.
2. While the LLM streams, each chunk is emitted as `data: {"type":"delta","text":"…"}`.
3. After completion the server emits `data: {"type":"final","payload": QueryResponse}` with the calibrated confidence and (optional) citations.
4. If the streaming connection fails after bounded retries, the server falls back to extractive synthesis from the top reranked chunks and still emits a `final` event.

### Chat flow (non-streaming and streaming)

1. Session is created or resumed; recent history (`CHAT_HISTORY_TURNS`) is loaded.
2. Retrieval, rewrite, rerank, and diversification mirror the query flow.
3. The user prompt is prefixed with a compact `Previous conversation` block.
4. Generation runs with the same calibrated confidence + shared `confidence_label` mapping. Refusals never expose raw exceptions.
5. User and assistant turns are persisted; the response includes the updated history.
6. `POST /chat/stream` emits the same `delta` + `final` SSE protocol.

---

## 3) Accuracy and Grounding Strategy

| Layer | Mechanism |
| --- | --- |
| Retrieval | Hybrid dense + sparse with server-side RRF (Qdrant); BM25 stats persisted to disk so query-time encoding matches ingest-time. |
| Rewrite | Optional LLM rewrite, gated on weak initial top score and `QUERY_REWRITE_ENABLED`. |
| Rerank | Cohere primary with lexical-overlap fallback when the API is unavailable. |
| Diversification | Per-document cap + MMR balance relevance with novelty before generation. |
| Evidence gate | Shared verdict using top, second, and margin thresholds; both pipelines use the same code path. |
| Generation | Strict grounding prompt + service-category domain hint; preamble/header noise is stripped post-generation. |
| Confidence gate | Calibrated `[0.10, 0.98]` confidence with refusal phrase short-circuit and uncertainty penalty. |
| Fallback | Tightened extractive answer (requires `MIN_FALLBACK_OVERLAP` token-set coverage); refuses cleanly otherwise. |
| Citations | Optional structured citation list (`include_citations: true` or `INCLUDE_CITATIONS_DEFAULT`). |

No LLM system can guarantee 100% literal correctness. This stack is engineered to maximise grounded correctness and **fail safely when uncertain** — the refusal phrase is a deliberate signal, not a defect.

---

## 4) Streaming Contract (SSE)

Both `/query/stream` and `/chat/stream` emit lines in SSE format:

```text
data: {"type":"delta","text":"..."}

data: {"type":"final","payload":{...}}
```

Frontend behaviour:

- Render deltas immediately for fast perceived response.
- Replace with the authoritative `final` payload at stream end.
- Treat any `{"type":"error",...}` event as a refusal — show the canonical refusal copy.

---

## 5) Provider and Fallback Behaviour

### LLM completion

- Preferred provider from `LLM_PROVIDER`, then automatic failover across providers with valid keys (`groq`, `openai`, `openrouter`).
- Per-provider `LLM_REQUEST_TIMEOUT_SEC` and `LLM_RETRY_ATTEMPTS` apply.
- Streaming completion uses bounded retries on connection establishment (failures fall through to extractive synthesis without leaking stack traces to clients).

### Embeddings

- Same cross-provider failover list (OpenAI, OpenRouter, Cohere).
- Cohere queries use `input_type=search_query` for `embed_query` and `search_document` for `embed_documents`.

### Reranking

- Cohere rerank when configured.
- Lexical-overlap fallback (token Jaccard + retrieval score) on rerank failure or rate limit.

### Final fallback

- Extractive fallback synthesises an answer from the top reranked chunks when the LLM is unavailable.
- If overlap < `MIN_FALLBACK_OVERLAP`, the extractive path refuses cleanly with `confidence=0.10` instead of stitching unrelated text.

---

## 6) API Endpoints

### Health

- `GET /health`

### Ingestion and documents

- `POST /ingest`
- `GET /documents`
- `GET /documents/{document_id}/chunks`
- `DELETE /documents/{document_id}`
- `GET /pdfs/{pdf_name}`
- `GET /pdfs/by-id/{document_id}` (primary source link endpoint)

### Query

- `POST /query` — accepts `question`, `service_category?`, `top_k?`, `rerank_top_n?`, `include_citations?`.
- `POST /query/stream` — same payload, SSE response.

### Chat

- `POST /chat` — accepts `session_id?`, `question`, `service_category?`, `top_k?`, `rerank_top_n?`, `include_citations?`.
- `POST /chat/stream`
- `GET /chat/sessions`
- `GET /chat/{session_id}/history`
- `DELETE /chat/{session_id}`
- `POST /chat/sessions/{session_id}/branch` — fork a session from a specific turn into a new conversation. The new session row carries `parent_session_id` and `parent_turn_id` so the UI can render lineage.

### Operator surfaces

- `GET /metrics/recent` / `GET /logs/recent` — paginated metrics samples and structured-log entries used by `/app/status`.
- `GET /preferences` / `PUT /preferences` — persist per-cookie UI preferences (theme, layout, default service category, etc.).
- `GET /settings/schema` — declarative form schema rendered by `/app/settings`.
- `GET /webhooks` / `POST /webhooks` / `PATCH /webhooks/{id}` / `DELETE /webhooks/{id}` / `POST /webhooks/{id}/test` — subscription CRUD plus a test-delivery endpoint. Valid event types are `ingestion.complete`, `query.completed`, `query.refused` (the canonical list lives in `app.db.relational.WEBHOOK_EVENTS`). The test endpoint uses a dedicated `deliver_to_subscription` helper that bypasses the global `WEBHOOKS_ENABLED` gate and the per-subscription `enabled` flag, so operators can verify signatures without un-pausing the subscription.
- `GET /tags` / `POST /documents/{document_id}/tags` — tag and Spaces management surfaced on `/app/documents`.

`QueryResponse` and `ChatResponse` both expose `citations: list[Citation]` when requested. A `Citation` carries `chunk_id`, `document_id`, `pdf_name`, `page_number`, `section_title`, and `score`.

`/health` returns:

```json
{
  "status": "ok",
  "llm_provider": "openrouter",
  "embedding_provider": "openai",
  "vector_db": "qdrant",
  "relational_db": "postgres",
  "demo_mode": false,
  "visual_capable": false,
  "image_gen_active": false,
  "uptime_seconds": 485.27,
  "db_pool": { "size": 5, "checked_in": 0, "checked_out": 0, "overflow": -5 },
  "vector_index_size": 211,
  "queue_depth": 0
}
```

`vector_index_size` is collected by `app.observability.runtime.vector_index_size`. The helper transparently awaits async clients (`AsyncQdrantClient.get_collection` returns a coroutine) and falls back to a defensive `0` when the upstream call fails — it never raises into the request handler.

---

## 7) Key Configuration (`.env` + `app/config.py`)

### LLM and embeddings

- `LLM_PROVIDER` ∈ `{groq, openrouter, openai}`; `*_MODEL` per provider.
- `LLM_REQUEST_TIMEOUT_SEC`, `LLM_RETRY_ATTEMPTS`.
- `EMBEDDING_PROVIDER` ∈ `{openai, openrouter, cohere}`; `*_EMBEDDING_MODEL`, `EMBEDDING_DIM`.

### Vector / relational DB

- `VECTOR_DB` ∈ `{qdrant, milvus}`.
- Qdrant: `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`.
- Milvus: `MILVUS_URI`, `MILVUS_COLLECTION` (dense-only).
- `RELATIONAL_DB` ∈ `{postgres, mysql}`; `DATABASE_URL`, `DB_SCHEMA`.

### Retrieval and confidence

- `MAX_CHUNKS_RETURN`, `RERANK_TOP_N`, `CONFIDENCE_THRESHOLD`.
- `RELEVANCE_MIN_TOP_SCORE`, `RELEVANCE_MIN_SECOND_SCORE`, `RELEVANCE_MIN_SCORE_GAP`.
- Hybrid: `HYBRID_RRF_K`, `HYBRID_DENSE_LIMIT`, `HYBRID_SPARSE_LIMIT`, `SPARSE_INDEX_DIR`.
- Diversification: `MMR_ENABLED`, `MMR_LAMBDA`, `MAX_PER_DOC`.
- Citations: `INCLUDE_CITATIONS_DEFAULT`.
- Fallback: `MIN_FALLBACK_OVERLAP`, `EXTRACTIVE_FALLBACK_CONFIDENCE`.
- Query rewrite: `QUERY_REWRITE_ENABLED`, `QUERY_REWRITE_TRIGGER_SCORE`.
- Intent tuning: `INTENT_TROUBLESHOOT_TOP_K_BOOST`, `INTENT_HOWTO_TOP_K_BOOST`.

### Ingestion

- `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EMBED_BATCH_SIZE`.
- `HEADING_AWARE_CHUNKING`.
- `PDF_STORAGE_BACKEND` ∈ `{relational, vector}`; `PDF_VECTOR_COLLECTION`, `PDF_VECTOR_CHUNK_BYTES`.
- `PDF_IMAGE_PAGE_CHAR_THRESHOLD`, `PDF_IMAGE_RATIO_THRESHOLD`.

### OCR

- `OCR_ENABLED`, `OCR_MODE` ∈ `{tesseract, vision, hybrid}`.
- `OCR_LANGUAGES`, `OCR_RENDER_DPI`, `OCR_TEXT_CONFIDENCE_THRESHOLD`.
- `OCR_VISION_FALLBACK_ENABLED`, `OCR_VISION_MODEL`, `TESSERACT_CMD`.

### Chat / session

- `CHAT_HISTORY_TURNS`, `MAX_SESSIONS`.

### Rate limiting, PII redaction, webhooks

- `RATE_LIMIT_PER_IP_PER_MIN` (default `60`) — sliding-window per-IP cap on `/query` + `/chat`.
- `RATE_LIMIT_PER_COOKIE_PER_MIN` (default `600`) — per-`rag_engine_uid` cap. Both scopes are enforced on every hot request.
- `INGEST_REDACT_PII` (default off) — toggle the regex/presidio scrub in `app.ingestion.redact`.
- `INGEST_REDACT_BACKEND` ∈ `{regex, presidio}` — `regex` is built-in, `presidio` requires `pip install -e ".[pii]"` and is unioned with the regex pass.
- `WEBHOOKS_ENABLED` (default `true`) — global outbound gate.
- `WEBHOOKS_TIMEOUT_SEC` (default `5.0`) — per-call timeout for webhook deliveries.

### Auto-summary, answer cache, retrieval expansion

- `AUTO_SUMMARY_ENABLED` (default `true`) — populates `documents.summary` after each successful ingest.
- `ANSWER_CACHE_ENABLED` / `ANSWER_CACHE_BACKEND` / `ANSWER_CACHE_MAXSIZE` / `ANSWER_CACHE_TTL_SEC` — process-LRU or Redis answer cache keyed by `(question, top_k, service_category, corpus_version)`. The cache is bumped automatically on ingest, delete, and CLI `clear-cache`.
- `HYDE_ENABLED` / `MULTI_QUERY_ENABLED` / `MULTI_QUERY_VARIANTS` / `HYDE_TIMEOUT_SEC` — opt-in retrieval expansion.
- `CHAT_COREFERENCE_REWRITE` — resolves "it"/"that" follow-ups into a standalone search query using recent history.
- `ANSWER_VERIFIER_ENABLED` / `ANSWER_VERIFIER_MIN_SCORE` — second LLM pass that scores groundedness; regenerates once when weak. Streaming endpoints skip the verifier.

### Open PDF source behaviour

- Source links resolve via `/pdfs/by-id/{document_id}` against the configured PDF storage backend.
- Page navigation uses the browser fragment (`#page={n}`) appended by the frontend.

---

## 8) Migrations

### Qdrant hybrid migration

Existing dense-only Qdrant collections are not compatible with the new server-side RRF flow. Run the destructive recreation script and re-ingest:

```bash
python scripts/migrate_qdrant_hybrid.py --confirm
```

The script recreates the collection with named `dense` and `sparse` vector configs. Without `--confirm` it prints the plan and exits.

### BM25 sparse index

`BM25SparseEncoder.save` writes `bm25.json` under `SPARSE_INDEX_DIR` after each ingest run. Query-time encoding loads the same snapshot via `BM25SparseEncoder.load_or_default`. If the file is missing, the encoder falls back to a deterministic default and the system emits a warning log line.

### Lightweight in-place migrations

`app.db.relational.init_db()` runs on startup and, after `metadata.create_all`, executes an idempotent migration helper (`_apply_lightweight_migrations`) that adds the following columns when an older schema is encountered:

| Table | Columns |
| --- | --- |
| `documents` | `summary` (TEXT), `tags` (TEXT/JSON), `version` (INTEGER) |
| `chat_sessions` | `title` (TEXT), `parent_session_id` (TEXT), `parent_turn_id` (TEXT) |

This keeps deploys against pre-existing databases zero-downtime — newer columns simply appear the first time a newer build boots. Schema-level changes that rename, drop, or re-type columns still go through dedicated `scripts/migrate_*.py` scripts.

### Document versioning

Document versioning hinges on the *user-facing* filename. The `/ingest` route stores uploads at `/tmp/{task_id}_{filename}` for cleanup safety, so the ingestion pipeline accepts an explicit `original_filename` argument and uses it for both:

1. The relational `_next_document_version(filename)` lookup (so re-uploads always increment instead of forking a new lineage).
2. The canonical `pdf_name` written into every chunk's vector payload (so citation labels never expose the temp prefix).

If you ingest programmatically via `IngestPipeline.run`, pass `original_filename="my_file.pdf"` whenever the path on disk differs from what the user uploaded.

### Operator endpoints (CLI + SDKs)

- **Admin CLI** — `python -m app.cli {ingest,query,clear-cache,export-corpus,eval}` covers ingest, retrieval, cache invalidation, corpus export to JSONL, and golden-set evaluation. Each subcommand imports lazily so cold-start cost matches the workload.
- **SDK generation** — `python -m scripts.gen_sdk` (or `--url http://localhost:8000/openapi.json`) regenerates a Python (`app/sdk/python`) and TypeScript (`helpdesk-ui/src/lib/sdk`) client from the live OpenAPI schema. Both clients are checked into the repo and round-tripped through CI.

---

## 9) Project Structure

- `app/main.py` — FastAPI entrypoint.
- `app/api/routes.py` — HTTP routes + SSE endpoints.
- `app/config.py` — Pydantic settings (single source of truth).
- `app/llm/client.py` — completion, streaming, embedding + provider failover.
- `app/query/`
  - `router.py` — fast category/intent routing.
  - `hybrid_search.py` — dense + sparse retrieval + RRF on Qdrant.
  - `reranker.py` — Cohere rerank with lexical fallback.
  - `rag_generator.py` — prompts, calibrated confidence, citations, extractive fallback.
  - `diversify.py` — MMR + per-document cap.
  - `gates.py` — shared evidence + confidence gate logic.
  - `rewrite.py` — optional LLM query rewrite.
  - `pipeline.py` — query orchestration and streaming.
- `app/chat/`
  - `session.py` — session/history persistence.
  - `pipeline.py` — chat orchestration and streaming.
- `app/ingestion/`
  - `pdf_parser.py` — text/OCR extraction.
  - `ocr_parser.py` — Tesseract + optional Vision OCR.
  - `chunker.py` — heading-aware splitting.
  - `sparse.py` — BM25 encoder with persistence.
  - `pipeline.py` — full ingest pipeline.
- `app/db/`
  - `vector_store.py` — Qdrant (named hybrid) + Milvus (dense) adapters.
  - `relational.py` — Postgres / MySQL via SQLAlchemy.
- `helpdesk-ui/src/` — Next.js UI (streaming clients, query/chat surfaces).
- `tests/`
  - `unit/` — isolated unit tests.
  - `integration/` — API and boundary tests.
  - `e2e/test_e2e.py` — mocked end-to-end suite (default).
  - `e2e/test_live_e2e.py` — live providers + Qdrant suite (gated by `RUN_LIVE_E2E=1`).

---

## 10) Quick Start

1. Configure `.env` with valid keys and DB URLs.
2. `make up` to start Qdrant/Milvus + Postgres/MySQL via docker-compose.
3. `make install` (Python deps + frontend deps).
4. `make init` (relational schema + vector collection).
5. `make dev-backend` and `make dev-frontend`.
6. Open `http://localhost:3000`, upload documents (any supported format), and exercise both Query and Chat (streaming included).

---

## 11) Operational Notes

- `frontend network error`: verify `GET /health`, `NEXT_PUBLIC_API_URL`, and that no stale processes are blocking ports.
- Provider 429 / rate-limit events are absorbed by failover + fallback, but answer quality still depends on healthy quotas.
- `Open PDF` 404s indicate the PDF storage backend was switched between ingest and query — re-ingest to repopulate.
- Best-quality production setup: paid provider tiers, healthy Cohere rerank quota, clean source documents (OCR noise on scanned PDFs and images hurts retrieval).
- Re-run `python scripts/migrate_qdrant_hybrid.py --confirm` after collection schema changes; this is destructive and intentionally manual.
- `ruff check`, `mypy app/`, and `pytest -q` should all exit 0 — CI mirrors this contract.

---

End of manual.
