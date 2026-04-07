  # IT Helpdesk RAG System — User & Technical Manual (Latest)

  This manual reflects the current implementation in this repository, including:
  - relevance-first retrieval and answer generation,
  - streaming responses for Query and Chat,
  - provider failover and fallback behavior,
  - current API contracts and operations.

  ---

  ## 1) System Overview

  The platform is a document-grounded IT assistant:
  - Upload PDFs (network, VPN, SSL, Linux, cloud, etc.).
  - Ask questions in Query mode or Chat mode.
  - Receive structured answers with confidence and source chunks.
  - Refuse when evidence is insufficient.

  Core design goal: **accuracy over speed**.  
  Latency is acceptable if it improves answer quality and grounding.

  ---

  ## 2) End-to-End Data Flow

  ### Ingestion Flow
  1. Frontend uploads PDF to `POST /ingest`.
  2. Parser extracts page text and metadata.
  3. Chunker splits content into overlapping chunks.
  4. Dense embeddings are generated.
  5. Chunks + vectors + metadata are upserted into vector DB.
  6. Document/chunk metadata is stored in relational DB.
  7. Raw PDF bytes are stored through configurable PDF storage backend:
     - relational DB (`document_files` table), or
     - vector DB payload storage (chunked records).

  ### Query Flow (non-streaming)
  1. `POST /query` receives question.
  2. Router classifies likely domain/intent (keyword-based fast routing).
  3. Hybrid search retrieves candidate chunks.
  4. Reranker scores candidates (Cohere when available).
  5. Evidence gate validates signal quality.
  6. Generator produces answer with strict grounding rules.
  7. Confidence gate decides answer vs refusal.
  8. Response includes confidence + sources.

  ### Query Flow (streaming)
  1. `POST /query/stream` starts SSE stream.
  2. Emits `delta` events for incremental text (when LLM stream succeeds).
  3. Emits a `final` event with full `QueryResponse` payload.
  4. If stream provider fails, server falls back and still emits `final`.

  ### Chat Flow (non-streaming and streaming)
  1. Session is created or resumed.
  2. Recent history is loaded (`CHAT_HISTORY_TURNS`).
  3. Retrieval + rerank run similarly to Query.
  4. Prompt includes conversation history.
  5. Answer is generated or fallback is used.
  6. User/assistant turns are persisted.
  7. Chat response includes updated history.

  Streaming endpoint: `POST /chat/stream` (SSE with `delta` + `final`).

  ---

  ## 3) Accuracy and Grounding Strategy

  Current accuracy controls:
  - **Grounding prompt rules** in `app/query/rag_generator.py` enforce context-only answers.
  - **Context sanitization and filtering** remove low-signal chunks/fragments before generation.
  - **Evidence gating** in query/chat pipelines rejects weak retrieval sets.
  - **Confidence gating** refuses low-confidence answers.
  - **Reranker fallback scoring** (lexical overlap + base score) when Cohere is rate-limited.
  - **LLM provider failover** (preferred provider, then alternates if configured) in `app/llm/client.py`.
  - **Extractive fallback answer synthesis** when generation fails (rate limits, provider errors).

  Important: no LLM system can guarantee literal 100% correctness.  
  This stack is engineered to maximize grounded correctness and fail safely when uncertain.

  ---

  ## 4) Streaming Contract (SSE)

  Both `/query/stream` and `/chat/stream` emit lines in SSE format:

  `data: {"type":"delta","text":"..."}`

  `data: {"type":"final","payload":{...}}`

  Frontend behavior:
  - Render deltas immediately for fast perceived response.
  - Replace with final authoritative payload at stream end.

  ---

  ## 5) Provider and Fallback Behavior

  ### LLM generation
  - Preferred provider from `LLM_PROVIDER`.
  - Automatic failover across configured providers with keys:
    - `groq`
    - `openai`
    - `openrouter`
  - Applies to both normal completion and streaming completion.

  ### Reranking
  - Primary: Cohere rerank.
  - On rerank failure/rate-limit: local relevance fallback (lexical overlap + retrieval score).

  ### Final fallback
  - If generation fails after provider attempts, system uses extractive fallback from top chunks.
  - If evidence is weak, system refuses:
    - `"I don't have information on this topic in our documentation."`

  ---

  ## 6) API Endpoints (Current)

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
  - `POST /query`
  - `POST /query/stream` (SSE)

  ### Chat
  - `POST /chat`
  - `POST /chat/stream` (SSE)
  - `GET /chat/sessions`
  - `GET /chat/{session_id}/history`
  - `DELETE /chat/{session_id}`

  ---

  ## 7) Key Configuration (from `.env` + `app/config.py`)

  ### LLM
  - `LLM_PROVIDER` = `groq | openrouter | openai`
  - `GROQ_MODEL`, `OPENROUTER_MODEL`, `OPENAI_MODEL`
  - `LLM_REQUEST_TIMEOUT_SEC`
  - `LLM_RETRY_ATTEMPTS`

  ### Embeddings
  - `EMBEDDING_PROVIDER`
  - `OPENAI_EMBEDDING_MODEL`, `OPENROUTER_EMBEDDING_MODEL`, `COHERE_EMBEDDING_MODEL`
  - `EMBEDDING_DIM`

  ### Retrieval and confidence
  - `MAX_CHUNKS_RETURN`
  - `RERANK_TOP_N`
  - `CONFIDENCE_THRESHOLD`
  - `RELEVANCE_MIN_TOP_SCORE`
  - `RELEVANCE_MIN_SECOND_SCORE`
  - `RELEVANCE_MIN_SCORE_GAP`

  ### Chat/session
  - `CHAT_HISTORY_TURNS`
  - `MAX_SESSIONS`

  ### Databases
  - `VECTOR_DB` (`qdrant | milvus`)
  - `RELATIONAL_DB` (`postgres | mysql`)
  - `PDF_STORAGE_BACKEND` (`relational | vector`) — controls where raw PDFs are stored
  - `PDF_VECTOR_COLLECTION` — dedicated vector collection for PDF payload chunks
  - `PDF_VECTOR_CHUNK_BYTES` — chunk size for vector payload storage

  ### Open PDF source behavior
  - Source links are generated as `/pdfs/by-id/{document_id}`.
  - Backend loads PDF bytes from configured storage backend and returns inline PDF.
  - Page navigation uses browser fragment: `#page={n}` appended by frontend.

  ### PDF storage backend details
  - `relational` (default):
    - stores bytes in relational table `document_files`
    - durable and simple for personal/small deployments
  - `vector`:
    - stores PDF as chunked base64 payload records
    - supports both Qdrant and Milvus
    - useful if you want to avoid additional relational binary growth

  ---

  ## 8) Project Structure (Current)

  - `app/main.py`: FastAPI entrypoint.
  - `app/api/routes.py`: HTTP routes + streaming routes.
  - `app/config.py`: settings.
  - `app/llm/client.py`: completion/streaming/embedding + provider failover.
  - `app/query/`
    - `router.py`: fast category/intent routing.
    - `hybrid_search.py`: retrieval.
    - `reranker.py`: rerank + local fallback.
    - `rag_generator.py`: prompting, cleaning, confidence, extractive fallback.
    - `pipeline.py`: query orchestration + query streaming.
  - `app/chat/`
    - `session.py`: session/history persistence.
    - `pipeline.py`: chat orchestration + chat streaming.
  - `app/ingestion/`: parsing/chunking/ingestion pipeline.
  - `app/db/`: vector + relational adapters.
  - `helpdesk-ui/src/`: Next.js UI, including streaming clients.
  - `tests/`: unit + integration + e2e coverage.

  ---

  ## 9) Quick Start

  1. Configure `.env` with valid API keys and DB URLs.
  2. Start infrastructure (`docker-compose up -d`) if needed.
  3. Install dependencies:
    - backend: `pip install -e ".[dev]"`
    - frontend: `cd helpdesk-ui && npm install`
  4. Start backend: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
  5. Start frontend: `cd helpdesk-ui && npm run dev -- -p 3000`
  6. Open `http://localhost:3000`.
  7. Upload PDFs in Documents page.
  8. Test Query and Chat (including streaming behavior).

  ---

  ## 10) Operational Notes

  - If frontend shows `network error`, verify:
    - backend health (`GET /health`),
    - frontend API base URL (`NEXT_PUBLIC_API_URL`),
    - no stale processes/port conflicts.
  - Provider 429/rate-limit events are handled with failover/fallback, but best quality still depends on active provider quota.
  - If **Open PDF** returns 404:
    - verify the document still exists (`GET /documents`),
    - verify `PDF_STORAGE_BACKEND` matches how files were ingested,
    - if you switched backend mode, re-ingest documents so PDF bytes are stored in the selected backend.
  - For highest quality in production:
    - use paid provider tiers,
    - keep reranker quota healthy,
    - ingest clean PDFs (OCR/noise impacts retrieval quality).

  ---

  End of manual.


