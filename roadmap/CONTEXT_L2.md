# IT-HELPDESK-RAG — CONTEXT.md

## Project
Configurable IT Helpdesk RAG System
Ingestion Pipeline — PDF parse → chunk → dual embed → vector upsert → relational metadata save
Builds directly on top of Foundation — all Foundation code remains intact

## What This Section Adds
- PDF parser with metadata extraction (service name, section title, page number)
- Smart chunker — page-boundary aware, table-aware, 512/64 overlap
- BM25 sparse encoder for hybrid search preparation
- Full async ingestion pipeline wiring all steps together
- Demo PDF generator (VPN_Setup_Guide.pdf via reportlab)
- Ingestion unit tests with mocked dependencies

## Demo Mode
- ALL external calls have a --demo-mode fallback
- --demo-mode loads from data/sample_pdfs/ instead of live uploads
- LLM still runs in demo mode (only file I/O is mocked)
- Every pipeline stage MUST implement both live and demo paths

## Stack
- LLM:          Configurable via LLM_PROVIDER env var
                  "groq"       → llama-3.3-70b via Groq API
                  "openrouter" → any model via OpenRouter
                  "openai"     → any OpenAI-compatible model
- Embeddings:   Configurable via EMBEDDING_PROVIDER env var
                  "openai"     → text-embedding-3-small (default)
                  "openrouter" → google/gemini-embedding-001
                  "cohere"     → embed-english-v3.0
- Relational DB: Configurable via RELATIONAL_DB env var
                  "postgres"   → asyncpg + SQLAlchemy async
                  "mysql"      → aiomysql + SQLAlchemy async
- Vector DB:    Configurable via VECTOR_DB env var
                  "qdrant"     → Qdrant via qdrant-client
                  "milvus"     → Milvus via pymilvus
- PDF Parsing:  PyMuPDF (fitz)
- Chunking:     RecursiveCharacterTextSplitter (langchain-text-splitters)
- Sparse:       rank_bm25 (BM25Okapi)
- Demo PDF gen: reportlab
- API:          FastAPI
- Config:       pydantic-settings
- Logging:      structlog
- Python:       3.11+, async throughout
- OS:           Windows 11 (native)

## Eliminated
- NO LangGraph   (not needed — linear pipelines only)
- NO AutoGen     (overkill)
- NO CrewAI      (overkill)
- NO LlamaIndex  (direct vector DB calls)
- NO hardcoded model strings anywhere

## LLM Client Pattern (unchanged from Foundation — do not touch)
- File: app/llm/client.py — ALL LLM + embed calls go here ONLY
- complete() + embed(), provider-switched (groq/openrouter/openai)
- tenacity retry: 3 attempts, exponential 2–60s

## Vector DB Client Pattern (unchanged from Foundation — do not touch)
- File: app/db/vector_store.py — ALL vector DB calls go here ONLY
- VectorStore ABC, QdrantVectorStore, MilvusVectorStore, get_vector_store()

## Relational DB Client Pattern (unchanged from Foundation — do not touch)
- File: app/db/relational.py — ALL relational DB calls go here ONLY
- SQLAlchemy async engine factory, postgres + mysql, tables: documents, chunks

## Conventions
- ALL pipeline methods are async
- ALL inter-stage data uses Pydantic models (no raw dicts)
- ALL LLM + embed calls go through app/llm/client.py only
- ALL vector DB calls go through app/db/vector_store.py only
- ALL relational DB calls go through app/db/relational.py only
- ALL errors logged via structlog before raising
- Type hints on every function signature
- No print() anywhere — structlog only
- No hardcoded strings — always use settings or constants
- Windows 11: asyncio.WindowsSelectorEventLoopPolicy() already set in main.py

## Existing Foundation (already built — do NOT rebuild or modify)
- app/config.py — pydantic-settings, get_settings(), all env vars loaded
- app/main.py — FastAPI, CORS, Windows event loop policy
- app/llm/client.py — complete() + embed(), provider-switched
- app/db/vector_store.py — VectorStore ABC, QdrantVectorStore, MilvusVectorStore
- app/db/relational.py — async SQLAlchemy engine, postgres/mysql, documents+chunks tables
- app/models/document.py — Document, Chunk pydantic models
- app/models/query.py — QueryRequest, QueryResponse, SearchResult pydantic models

## Ingestion Pipeline Spec

### app/ingestion/pdf_parser.py
- Uses PyMuPDF (fitz)
- Function: parse_pdf(path: str, demo_mode: bool = False) -> list[ParsedPage]
- ParsedPage Pydantic model:
    page_number:   int
    text:          str
    pdf_name:      str
    service_name:  str   # from filename: "VPN_Setup_Guide.pdf" → "VPN"
    section_title: str   # largest font text block on page
    total_pages:   int
- Strip headers/footers: ignore blocks in top 5% and bottom 5% of page height
- Detect section_title: largest font size block per page (fitz block font size)
- demo fallback: if demo_mode=True and path not found →
    load data/sample_pdfs/VPN_Setup_Guide.pdf if it exists,
    else return 1 synthetic ParsedPage with placeholder text (never raise)

### app/ingestion/chunker.py
- Uses RecursiveCharacterTextSplitter (langchain-text-splitters)
- Function: chunk_pages(pages: list[ParsedPage]) -> list[ChunkData]
- ChunkData Pydantic model:
    chunk_id:      str   # uuid4
    text:          str
    pdf_name:      str
    service_name:  str
    section_title: str
    page_number:   int
    chunk_index:   int
    total_pages:   int
- chunk_size and chunk_overlap read from settings (CHUNK_SIZE=512, CHUNK_OVERLAP=64)
- Page-boundary aware: chunk within each page independently, never split across pages
- Table detection: if a text block has ≥2 lines containing ≥2 pipe chars (|) or ≥2 tab chars
    → keep entire block as a single chunk regardless of size

### app/ingestion/sparse.py
- BM25SparseEncoder class using rank_bm25 (BM25Okapi)
- fit(corpus: list[str]) -> None
    tokenise each text (lowercase split), build BM25Okapi index
- encode(text: str) -> dict[int, float]
    tokenise text, get BM25 scores against corpus,
    token_id = hash(token) % 30000,
    return {token_id: float(score)} for non-zero scores only
- encode_batch(texts: list[str]) -> list[dict[int, float]]
    calls encode() for each text, returns list

### app/ingestion/pipeline.py
- IngestPipeline class
- __init__(self, demo_mode: bool = False)
- async run(pdf_path: str, service_name_override: str | None = None) -> IngestionResult
- IngestionResult Pydantic model (define in this file):
    document_id:  str
    pdf_name:     str
    total_pages:  int
    total_chunks: int
    service_name: str
    status:       str   # "success" | "failed"
    error:        str | None = None
- Pipeline steps in order (all async, all logged):
    STEP 1: parse_pdf(pdf_path, demo_mode) → list[ParsedPage]
    STEP 2: chunk_pages(pages) → list[ChunkData]
    STEP 3: BM25SparseEncoder().fit([c.text for c in chunks])
    STEP 4: embed all chunk texts in batches of EMBED_BATCH_SIZE (default 32)
             call llm_client.embed(batch) → list of dense vectors
    STEP 5: encode_batch(all chunk texts) → list of sparse dicts
    STEP 6: for each chunk → vector_store.upsert(
               collection=settings.vector_collection,
               id=chunk.chunk_id,
               vector=dense_vector,
               payload={**chunk.dict(), "sparse_vector": sparse_dict}
            )
    STEP 7: relational DB inserts via relational.py:
               INSERT INTO documents (id, pdf_name, service_name, total_pages, total_chunks, created_at)
               INSERT INTO chunks per chunk (id, document_id, text, page_number, chunk_index, section_title, created_at)
    STEP 8: return IngestionResult(status="success", ...)
- On ANY error: log via structlog, return IngestionResult(status="failed", error=str(e))
- If service_name_override provided: use it instead of parsed service_name

### data/sample_pdfs/sample_it_guide.py
- Script using reportlab to generate data/sample_pdfs/VPN_Setup_Guide.pdf
- 5 pages:
    Page 1: title "VPN Setup Guide", section "Overview" — 2 paragraphs
    Page 2: section "Installation" — numbered steps
    Page 3: section "Configuration" — includes Error Codes table (pipe-formatted)
    Page 4: section "Troubleshooting" — bullet list of common issues
    Page 5: section "FAQ" — Q&A format
- Run standalone: python data/sample_pdfs/sample_it_guide.py
- Idempotent: overwrites if already exists

## Required .env Variables (additions to Foundation)
  CHUNK_SIZE=512
  CHUNK_OVERLAP=64
  EMBED_BATCH_SIZE=32

  # Already in Foundation .env.example — ensure present:
  VECTOR_DB=qdrant
  QDRANT_COLLECTION=helpdesk_chunks
  MILVUS_COLLECTION=helpdesk_chunks
  RELATIONAL_DB=postgres

## config.py additions (add these fields if not present)
  chunk_size:        int = 512
  chunk_overlap:     int = 64
  embed_batch_size:  int = 32
  vector_collection: str  # property: returns QDRANT_COLLECTION or MILVUS_COLLECTION based on VECTOR_DB

## Files to Create
  - app/ingestion/__init__.py
  - app/ingestion/pdf_parser.py
  - app/ingestion/chunker.py
  - app/ingestion/sparse.py
  - app/ingestion/pipeline.py
  - data/sample_pdfs/sample_it_guide.py
  - tests/unit/test_ingestion.py

## tests/unit/test_ingestion.py — Required Tests
  test_parse_pdf_demo:
    set demo_mode=True, call parse_pdf with non-existent path
    assert returns list, len ≥ 1, first item is ParsedPage, pdf_name populated

  test_chunk_pages:
    create 2 synthetic ParsedPage objects with ~600 chars each
    call chunk_pages(pages)
    assert all items are ChunkData
    assert chunk_id is valid UUID
    assert pdf_name, service_name populated on each chunk

  test_table_kept_whole:
    create ParsedPage with text containing pipe-heavy table block
    call chunk_pages([page])
    assert the table text appears unsplit in exactly one chunk

  test_sparse_encoder:
    fit on ["reset vpn password", "ssl certificate error"]
    encode("vpn password reset")
    assert result is dict, all values are float, len > 0

  test_pipeline_demo:
    mock embed() to return list of 1536-length zero vectors
    mock vector_store.upsert to no-op
    mock relational inserts to no-op
    call IngestPipeline(demo_mode=True).run("nonexistent.pdf")
    assert result.status == "success"
    assert result.total_chunks > 0

  test_pipeline_returns_model:
    same mocks as above
    assert result is IngestionResult
    assert result.document_id is non-empty string
    assert result.error is None

## Acceptance Criteria
  [ ] python data/sample_pdfs/sample_it_guide.py → creates VPN_Setup_Guide.pdf with no errors
  [ ] parse_pdf("data/sample_pdfs/VPN_Setup_Guide.pdf") → 5 ParsedPage objects, section_title populated
  [ ] chunk_pages(pages) → all ChunkData fields populated, chunk_id is UUID
  [ ] Table block on page 3 is kept as single chunk (not split)
  [ ] embed() called with batches of max EMBED_BATCH_SIZE chunks
  [ ] Sparse encode returns non-empty dict with float values
  [ ] vector_store.upsert called once per chunk with payload containing sparse_vector
  [ ] Relational INSERT called for document + all chunks
  [ ] demo_mode=True with missing PDF returns status="success" without raising
  [ ] All 6 unit tests pass with mocked dependencies
  [ ] No hardcoded model/DB strings outside config.py
  [ ] structlog used everywhere, no print()

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

## Files Created
- (Foundation files — see roadmap/CONTEXT_L1.md)

## Progress Tracker
  [x] sample_it_guide.py generates VPN_Setup_Guide.pdf
  [x] pdf_parser.py parses pages with metadata
  [x] chunker.py produces ChunkData with UUID chunk_id
  [x] table detection keeps table blocks whole
  [x] sparse.py BM25 encode returns non-empty dict
  [x] pipeline.py runs end-to-end with mocks
  [x] all 6 unit tests pass
  [x] No hardcoded strings
  [x] structlog only, no print()

## Next
QA COMPLETE