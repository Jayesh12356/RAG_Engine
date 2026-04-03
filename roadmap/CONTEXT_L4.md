# IT-HELPDESK-RAG — CONTEXT.md

## Project
Configurable IT Helpdesk RAG System
API Layer — FastAPI endpoints wiring ingestion + query pipelines to HTTP
Builds directly on top of Query Pipeline — all Foundation + Ingestion + Query code remains intact

## What This Section Adds
- POST /ingest — upload PDF → run IngestPipeline → return IngestionResult
- POST /query — send question → run QueryPipeline → return QueryResponse
- GET  /pdfs/{pdf_name} — serve raw PDF file for viewer
- GET  /documents — list all ingested documents from relational DB
- GET  /documents/{document_id}/chunks — list all chunks for a document
- DELETE /documents/{document_id} — remove document + chunks from relational + vector DB
- GET  /health — liveness check with provider info
- Full request/response validation via Pydantic
- Background task support — ingest runs as FastAPI BackgroundTask
- API-level demo mode toggle via header X-Demo-Mode: true
- Complete integration tests hitting real endpoints via httpx AsyncClient

## Demo Mode
- X-Demo-Mode: true header on any request → forces demo_mode=True for that request
- DEMO_MODE=true in env → all requests use demo_mode=True globally
- demo_mode flows through to IngestPipeline and QueryPipeline unchanged

## Stack (unchanged — do not modify any existing files)
- LLM:          Configurable via LLM_PROVIDER (groq/openrouter/openai)
- Embeddings:   Configurable via EMBEDDING_PROVIDER (openai/openrouter/cohere)
- Vector DB:    Configurable via VECTOR_DB (qdrant/milvus)
- Relational DB: Configurable via RELATIONAL_DB (postgres/mysql)
- Re-ranking:   Cohere Rerank v3
- API:          FastAPI + python-multipart (file upload)
- Config:       pydantic-settings
- Logging:      structlog
- Python:       3.11+, async throughout

## Existing Code (already built — do NOT rebuild or modify)
- app/config.py
- app/main.py — FastAPI app with CORS, Windows policy (update only to include router)
- app/llm/client.py
- app/db/vector_store.py
- app/db/relational.py
- app/models/document.py — Document, Chunk
- app/models/query.py — QueryRequest, QueryResponse, SourceChunk, SearchResult
- app/ingestion/ — full ingestion pipeline
- app/query/ — full query pipeline

## API Spec

### app/api/models.py — Request/Response Pydantic models for API layer
  IngestResponse:
    document_id:  str
    pdf_name:     str
    total_pages:  int
    total_chunks: int
    service_name: str
    status:       str          # "success" | "failed" | "processing"
    error:        str | None = None
    task_id:      str | None = None   # if background task

  QueryAPIRequest:
    question:         str
    service_category: str | None = None
    top_k:            int = 20
    rerank_top_n:     int | None = None

  DocumentListItem:
    document_id:  str
    pdf_name:     str
    service_name: str
    total_pages:  int
    total_chunks: int
    created_at:   str    # ISO format

  DocumentListResponse:
    documents: list[DocumentListItem]
    total:     int

  ChunkListResponse:
    document_id: str
    chunks:      list[dict]   # chunk_id, text preview (first 100 chars), page_number, section_title
    total:       int

  DeleteResponse:
    document_id: str
    status:      str   # "deleted"
    chunks_removed: int

  HealthResponse:
    status:           str   # "ok"
    llm_provider:     str
    embedding_provider: str
    vector_db:        str
    relational_db:    str
    demo_mode:        bool

### app/api/routes.py — All endpoints

  GET /health
    - Return HealthResponse with all provider names from settings
    - No DB calls — pure config introspection
    - Always returns 200

  POST /ingest
    - Accept: multipart/form-data
    - Field: file (UploadFile, PDF only — reject non-PDF with 400)
    - Field: service_name_override (str, optional form field)
    - Field: background (bool, default False)
    - Read demo_mode from header X-Demo-Mode or global settings.demo_mode
    - Save uploaded file to temp path: /tmp/{uuid}_{filename}
    - If background=False (default):
        await IngestPipeline(demo_mode).run(tmp_path, service_name_override)
        delete tmp file
        return IngestResponse (status 200)
    - If background=True:
        add_background_task(run_ingest_and_cleanup, tmp_path, ...)
        return IngestResponse(status="processing", task_id=uuid) immediately
    - On file read error → 400 with detail

  POST /query
    - Accept: application/json — QueryAPIRequest body
    - Read demo_mode from header X-Demo-Mode or global settings.demo_mode
    - Build QueryRequest from QueryAPIRequest
    - await QueryPipeline(demo_mode).run(request)
    - Return QueryResponse directly (already correct shape)
    - Status 200 always (refused=True is a valid response, not an error)

  GET /pdfs/{pdf_name}
    - Serve file from data/sample_pdfs/{pdf_name}
    - If not found → 404
    - Return FileResponse with media_type="application/pdf"
    - This allows frontend to open PDFs at exact page

  GET /documents
    - Query relational DB: SELECT all from documents table ORDER BY created_at DESC
    - Return DocumentListResponse
    - On DB error → 500 with logged detail

  GET /documents/{document_id}/chunks
    - Query relational DB: SELECT chunks WHERE document_id = ?
    - Return ChunkListResponse with text preview (chunk.text[:100] + "...")
    - 404 if document_id not found

  DELETE /documents/{document_id}
    - Step 1: query relational DB for all chunk_ids of this document
    - Step 2: delete each chunk from vector DB by chunk_id
    - Step 3: DELETE FROM chunks WHERE document_id = ?
    - Step 4: DELETE FROM documents WHERE id = ?
    - Return DeleteResponse(chunks_removed=N)
    - 404 if document not found
    - On partial failure: log error, still return what was deleted

### app/main.py update
  - Import and include app/api/routes.py router
  - Mount router with prefix="" (no prefix — routes are top-level)
  - CORS already set — verify http://localhost:3000 in origins
  - Add /pdfs static-like route via routes.py (FileResponse, not StaticFiles)

## Files to Create
  - app/api/__init__.py
  - app/api/models.py
  - app/api/routes.py
  - tests/integration/test_api.py

## tests/integration/test_api.py — Required Tests
  Use: httpx.AsyncClient with ASGITransport(app=create_app())
  Use: pytest-asyncio for all async tests
  Mock: IngestPipeline.run, QueryPipeline.run, relational DB calls, vector DB calls

  test_health_returns_ok:
    GET /health
    assert status 200
    assert response.json()["status"] == "ok"
    assert "llm_provider" in response.json()

  test_ingest_rejects_non_pdf:
    POST /ingest with a .txt file
    assert status 400

  test_ingest_success_demo:
    mock IngestPipeline.run → return IngestionResult(status="success", total_chunks=10, ...)
    POST /ingest with a dummy PDF bytes, header X-Demo-Mode: true
    assert status 200
    assert response.json()["status"] == "success"
    assert response.json()["total_chunks"] == 10

  test_query_success_demo:
    mock QueryPipeline.run → return QueryResponse(answer="Open Pulse...", confidence=0.91, refused=False, ...)
    POST /query with {"question": "how do I reset VPN password?"}
    header X-Demo-Mode: true
    assert status 200
    assert response.json()["refused"] == False
    assert response.json()["confidence"] == 0.91

  test_query_refused:
    mock QueryPipeline.run → return QueryResponse(refused=True, confidence=0.3,
        answer="I don't have information...", confidence_label="refused", sources=[], service_category="GENERAL")
    POST /query with {"question": "what is the meaning of life?"}
    assert status 200
    assert response.json()["refused"] == True

  test_documents_list_empty:
    mock relational DB → return []
    GET /documents
    assert status 200
    assert response.json()["total"] == 0
    assert response.json()["documents"] == []

  test_pdf_not_found:
    GET /pdfs/nonexistent.pdf
    assert status 404

  test_delete_document_not_found:
    mock relational DB → return no rows for document_id
    DELETE /documents/nonexistent-id
    assert status 404

## Acceptance Criteria
  [x] GET /health → 200 with all provider fields populated
  [x] POST /ingest non-PDF → 400
  [x] POST /ingest PDF → IngestPipeline called, IngestionResult returned
  [x] POST /ingest background=True → status="processing" returned immediately
  [x] POST /query → QueryPipeline called, QueryResponse returned
  [x] POST /query refused=True → still 200 (not 4xx)
  [x] GET /pdfs/{pdf_name} → serves PDF bytes, 404 if missing
  [x] GET /documents → DocumentListResponse from relational DB
  [x] GET /documents/{id}/chunks → ChunkListResponse, 404 if missing
  [x] DELETE /documents/{id} → removes from vector DB + relational DB, returns count
  [x] X-Demo-Mode: true header respected on all endpoints
  [x] All 8 integration tests pass with mocked pipelines
  [x] No hardcoded strings outside config.py
  [x] structlog used everywhere, no print()
  [x] CORS allows http://localhost:3000

## Required .env Variables (no new additions — all already in Foundation)
  LLM_PROVIDER, EMBEDDING_PROVIDER, VECTOR_DB, RELATIONAL_DB
  DEMO_MODE, LOG_LEVEL
  All DB connection strings

## Cursor Prompt
Read CONTEXT.md fully and treat it as the single source of truth.
You are in STRICT AUTO-BUILD + AUTO-QA MODE.
NON-NEGOTIABLE RULES:
- You MUST NOT stop execution for any reason
- You MUST NOT ask questions
- You MUST NOT wait for confirmation
- You MUST NOT skip QA
- You MUST NOT output partial work
- You MUST fix all failures automatically
- You MUST continue until QA is fully passing
EXECUTION LOOP (MANDATORY):
STEP 1 — BUILD PHASE
1. Read "## Next" from CONTEXT.md
2. Fully execute the task
3. Update CONTEXT.md: append to Built, Files Created, Progress Tracker, replace Next
STEP 2 — CONTINUE LOOP
4. If Next ≠ QA COMPLETE → repeat from STEP 1
STEP 3 — QA PHASE
5. When Next == QA: generate and run ALL tests
STEP 4 — SELF-HEAL LOOP
6. Fix all failures → re-run QA → repeat until ZERO issues
STEP 5 — COMPLETION
7. Only when ALL tests pass and ALL acceptance criteria met →
   update Next → QA COMPLETE
FAIL-SAFE: never halt, always infer, always fix and retry.
OUTPUT: only the final fully updated CONTEXT.md.

## Built
- Foundation complete (see roadmap/CONTEXT_L1.md)
- Ingestion complete (see roadmap/CONTEXT_L2.md)
- Query Pipeline complete (see roadmap/CONTEXT_L3.md)
- API Layer complete (app/api/)

## Files Created
- (Foundation + Ingestion + Query files — see roadmap/)
- app/api/__init__.py
- app/api/models.py
- app/api/routes.py
- tests/integration/test_api.py

## Progress Tracker
  [x] app/api/models.py — all request/response models
  [x] app/api/routes.py — all 7 endpoints implemented
  [x] app/main.py — router included
  [x] GET /health works
  [x] POST /ingest validates PDF, calls pipeline
  [x] POST /ingest background=True returns immediately
  [x] POST /query returns QueryResponse, refused=True is 200
  [x] GET /pdfs/{pdf_name} serves file or 404
  [x] GET /documents queries relational DB
  [x] GET /documents/{id}/chunks returns previews
  [x] DELETE /documents/{id} cleans vector + relational
  [x] X-Demo-Mode header respected
  [x] all 8 integration tests pass
  [x] No hardcoded strings
  [x] structlog only, no print()

## Next
QA COMPLETE