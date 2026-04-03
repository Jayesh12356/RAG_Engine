# IT-HELPDESK-RAG — CONTEXT.md

## Project
Configurable IT Helpdesk RAG System
Final Section — End-to-End Integration QA + Polish + Production Readiness
Builds on top of all previous sections — do NOT modify any existing code unless fixing a bug

## What This Section Adds
- Full end-to-end integration test suite — backend + frontend wired together
- Docker Compose — all services (Qdrant, Milvus, Postgres, MySQL) in one command
- scripts/init_db.py — creates relational DB tables on first run
- scripts/init_vector_db.py — creates vector collections for both Qdrant and Milvus
- scripts/seed_demo.py — ingests VPN_Setup_Guide.pdf into running stack end-to-end
- Makefile — single commands for common dev tasks
- README.md — setup, run, switch provider instructions
- Final bug sweep — all acceptance criteria from all 5 sections verified together
- Performance check — query pipeline end-to-end under 2 seconds in demo mode

## Existing Code (do NOT rebuild — only fix bugs found during QA)
- app/config.py
- app/main.py
- app/llm/client.py
- app/db/vector_store.py
- app/db/relational.py
- app/models/document.py
- app/models/query.py
- app/ingestion/ — pdf_parser, chunker, sparse, pipeline
- app/query/ — router, hybrid_search, reranker, rag_generator, pipeline
- app/api/ — models, routes
- helpdesk-ui/ — full Next.js frontend
- data/sample_pdfs/VPN_Setup_Guide.pdf (generated in section 2)
- tests/unit/test_config.py
- tests/unit/test_ingestion.py
- tests/unit/test_query.py
- tests/integration/test_api.py

## Docker Compose Spec (docker-compose.yml — full replacement)
  Services:

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]

  milvus:
    image: milvusdb/milvus:v2.3.0
    ports: ["19530:19530"]
    environment: ETCD_ENDPOINTS=etcd:2379
    depends_on: [etcd, minio]

  etcd:
    image: quay.io/coreos/etcd:v3.5.0
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: "1000"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    command: minio server /minio_data

  postgres:
    image: postgres:15
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: helpdesk
      POSTGRES_PASSWORD: helpdesk
      POSTGRES_DB: helpdesk
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  mysql:
    image: mysql:8.0
    ports: ["3306:3306"]
    environment:
      MYSQL_ROOT_PASSWORD: helpdesk
      MYSQL_DATABASE: helpdesk
      MYSQL_USER: helpdesk
      MYSQL_PASSWORD: helpdesk
    volumes: ["mysql_data:/var/lib/mysql"]

  volumes: qdrant_data, postgres_data, mysql_data

  Note: Milvus + etcd + minio are optional — only needed when VECTOR_DB=milvus
  Default compose starts all services — user can comment out milvus block if not needed

## Scripts Spec

### scripts/init_db.py
  - Reads RELATIONAL_DB from env (postgres or mysql)
  - Creates all tables: documents, chunks, conversation_history
  - Uses SQLAlchemy create_all() via app/db/relational.py
  - Idempotent: safe to run multiple times
  - Logs: "db.init.complete  provider=postgres  tables=[documents, chunks, conversation_history]"
  - Run: python scripts/init_db.py

### scripts/init_vector_db.py
  - Reads VECTOR_DB from env (qdrant or milvus)
  - Reads EMBEDDING_DIM from env
  - Calls vector_store.ensure_collection(settings.vector_collection, settings.embedding_dim)
  - Idempotent: safe to run multiple times
  - Logs: "vectordb.init.complete  provider=qdrant  collection=helpdesk_chunks  dim=1536"
  - Run: python scripts/init_vector_db.py

### scripts/seed_demo.py
  - Runs full ingestion pipeline on data/sample_pdfs/VPN_Setup_Guide.pdf
  - Uses demo_mode=False (real embed calls) — requires OPENAI_API_KEY or other embed provider
  - Falls back to demo_mode=True if embed fails (prints warning)
  - Logs full IngestionResult on completion
  - Run: python scripts/seed_demo.py

## Makefile Spec
  install:
    pip install -e ".[dev]"
    cd helpdesk-ui && npm install

  up:
    docker-compose up -d

  down:
    docker-compose down

  init:
    python scripts/init_db.py
    python scripts/init_vector_db.py

  seed:
    python data/sample_pdfs/sample_it_guide.py
    python scripts/seed_demo.py

  dev-backend:
    python -m app.main

  dev-frontend:
    cd helpdesk-ui && npm run dev

  test:
    pytest tests/ -v

  test-unit:
    pytest tests/unit/ -v

  test-integration:
    pytest tests/integration/ -v

  build-frontend:
    cd helpdesk-ui && npm run build

  demo:
    python -m app.main --demo-mode

  lint:
    ruff check app/ tests/
    cd helpdesk-ui && npm run build (tsc --noEmit)

## README.md Spec
  Sections (write fully, no placeholders):

  ### Overview
  One paragraph describing the system — configurable RAG, hybrid search, re-ranking, strict grounding

  ### Architecture
  ASCII diagram showing:
  PDF → Ingestion Pipeline → Vector DB (Qdrant/Milvus) + Relational DB (Postgres/MySQL)
  User Question → Query Pipeline → Router → Hybrid Search → Reranker → RAG Generator → Response

  ### Prerequisites
  - Python 3.11+
  - Node.js 18+
  - Docker + Docker Compose
  - At least one LLM API key (Groq recommended — free tier)
  - Cohere API key (free tier — for reranking)

  ### Quick Start (5 steps)
  1. cp .env.example .env — fill in at minimum GROQ_API_KEY + COHERE_API_KEY
  2. make up — start Docker services
  3. make install — install Python + Node deps
  4. make init — create DB tables + vector collections
  5. make dev-backend (terminal 1) + make dev-frontend (terminal 2)
  Open http://localhost:3000

  ### Switching Providers
  Table with 3 columns: What to change | Env var | Options
  LLM | LLM_PROVIDER | groq, openrouter, openai
  Embeddings | EMBEDDING_PROVIDER | openai, openrouter, cohere
  Vector DB | VECTOR_DB | qdrant, milvus
  Relational DB | RELATIONAL_DB | postgres, mysql
  Note: after switching DB, re-run make init

  ### Demo Mode
  python -m app.main --demo-mode
  No API keys needed except LLM (LLM still runs live)
  Sample PDF auto-loaded from data/sample_pdfs/

  ### API Reference
  Table of all 7 endpoints with method, path, description

  ### Project Structure
  Full directory tree (same as established across all sections)

## End-to-End QA Test Suite (tests/e2e/test_e2e.py)
  Scope: full stack with real app instance, mocked external APIs only
  Use: httpx.AsyncClient + ASGITransport
  Mock: llm_client.embed (return fixed 1536-dim vectors)
        llm_client.complete (return realistic answer strings)
        cohere reranker (return mock scored results)
        vector_store calls (in-memory stub)
        relational DB calls (SQLite in-memory via override)

  test_e2e_ingest_then_query:
    1. POST /ingest with VPN_Setup_Guide.pdf bytes (demo PDF from sample_it_guide.py)
    2. Assert IngestResponse.status == "success"
    3. Assert IngestResponse.total_chunks > 0
    4. POST /query {"question": "How do I reset my VPN password?"}
    5. Assert QueryResponse.refused == False
    6. Assert QueryResponse.confidence >= 0.6
    7. Assert len(QueryResponse.sources) > 0
    8. Assert QueryResponse.sources[0].pdf_name == "VPN_Setup_Guide.pdf"

  test_e2e_health_reflects_config:
    1. GET /health
    2. Assert response matches current env settings
    3. Assert llm_provider == settings.llm_provider
    4. Assert vector_db == settings.vector_db

  test_e2e_document_lifecycle:
    1. POST /ingest → get document_id
    2. GET /documents → assert document appears in list
    3. GET /documents/{document_id}/chunks → assert chunks > 0
    4. DELETE /documents/{document_id} → assert status="deleted"
    5. GET /documents → assert document no longer in list

  test_e2e_confidence_gate_fires:
    1. mock llm_client.complete to return refusal phrase
    2. POST /query {"question": "what is the weather in Paris?"}
    3. Assert QueryResponse.refused == True
    4. Assert QueryResponse.confidence_label == "refused"
    5. Assert QueryResponse.sources == []

  test_e2e_demo_mode_header:
    1. POST /ingest with header X-Demo-Mode: true + any file
    2. Assert pipeline runs in demo_mode (no real embed called)
    3. POST /query with header X-Demo-Mode: true
    4. Assert response returned without real vector DB call

  test_e2e_provider_switching_config:
    1. Override settings: VECTOR_DB=qdrant → assert get_vector_store() is QdrantVectorStore
    2. Override settings: VECTOR_DB=milvus → assert get_vector_store() is MilvusVectorStore
    3. Override settings: RELATIONAL_DB=mysql → assert engine URL contains aiomysql
    4. Override settings: LLM_PROVIDER=groq → assert client base_url contains groq.com
    These are unit-style assertions, no live DB needed

## Final Bug Sweep Checklist
  Run these in order — fix any failure before moving to next:

  Backend:
  [ ] python -m app.main starts with zero import errors
  [ ] All unit tests pass: pytest tests/unit/ -v
  [ ] All integration tests pass: pytest tests/integration/ -v
  [ ] All e2e tests pass: pytest tests/e2e/ -v
  [ ] LLM_PROVIDER=groq → startup log shows "provider=groq"
  [ ] LLM_PROVIDER=openrouter → startup log shows "provider=openrouter"
  [ ] VECTOR_DB=qdrant → get_vector_store() returns QdrantVectorStore
  [ ] VECTOR_DB=milvus → get_vector_store() returns MilvusVectorStore
  [ ] RELATIONAL_DB=postgres → engine URL contains asyncpg
  [ ] RELATIONAL_DB=mysql → engine URL contains aiomysql
  [ ] EMBEDDING_PROVIDER=cohere → embed() uses cohere SDK
  [ ] No print() anywhere in app/ — structlog only
  [ ] No hardcoded model/DB strings outside config.py
  [ ] All pydantic models have no raw dicts passed between pipeline stages
  [ ] Confidence gate fires correctly at CONFIDENCE_THRESHOLD
  [ ] demo_mode=True never raises — always returns graceful response
  [ ] DELETE /documents cleans both vector DB and relational DB
  [ ] POST /ingest background=True returns immediately with task_id

  Frontend:
  [ ] cd helpdesk-ui && npm run build — zero TypeScript errors
  [ ] /query page submits and shows ResponseCard
  [ ] /documents page uploads PDF, shows in list, deletes correctly
  [ ] /status page shows all 4 provider pills
  [ ] DemoBanner visible when demo mode active
  [ ] ConfidenceGauge correct color per label
  [ ] SourceAccordion opens/closes, Open PDF works
  [ ] No unhandled promise rejections in console
  [ ] No emojis in rendered UI
  [ ] NEXT_PUBLIC_API_URL respected — no hardcoded localhost

  Scripts:
  [ ] python scripts/init_db.py — completes without error
  [ ] python scripts/init_vector_db.py — completes without error
  [ ] python data/sample_pdfs/sample_it_guide.py — generates PDF
  [ ] make test — all tests pass

## Files to Create
  - docker-compose.yml (full replacement of existing)
  - Makefile
  - README.md
  - scripts/__init__.py
  - scripts/init_db.py
  - scripts/init_vector_db.py
  - scripts/seed_demo.py
  - tests/e2e/__init__.py
  - tests/e2e/test_e2e.py

## Acceptance Criteria
  [ ] All unit tests pass (pytest tests/unit/ -v)
  [ ] All integration tests pass (pytest tests/integration/ -v)
  [ ] All e2e tests pass (pytest tests/e2e/ -v)
  [ ] npm run build zero errors
  [ ] make init runs without error against Docker services
  [ ] make seed ingests VPN_Setup_Guide.pdf successfully
  [ ] Full query round-trip (ingest → query) returns answer with sources
  [ ] Provider switching verified for all 4 axes (LLM, embed, vectorDB, relDB)
  [ ] README.md complete — no TODOs, no placeholders
  [ ] Zero print() calls in entire app/ directory
  [ ] Zero hardcoded strings outside config.py

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
5. When Next == QA:
   - Run pytest tests/unit/ -v
   - Run pytest tests/integration/ -v
   - Run pytest tests/e2e/ -v
   - Run cd helpdesk-ui && npm run build
   - Verify all checklist items in Final Bug Sweep
STEP 4 — SELF-HEAL LOOP
6. Fix every failure → re-run full test suite → repeat until ZERO failures
STEP 5 — COMPLETION
7. Only when ALL of the following are true:
   - All pytest suites pass
   - npm run build zero errors
   - All 35 bug sweep checklist items verified
THEN: update Next → QA COMPLETE
FAIL-SAFE: never halt, always infer, always fix and retry.
OUTPUT: only the final fully updated CONTEXT.md.

## Built
- Foundation complete (see roadmap/CONTEXT_L1.md)
- Ingestion complete (see roadmap/CONTEXT_L2.md)
- Query Pipeline complete (see roadmap/CONTEXT_L3.md)
- API Layer complete (see roadmap/CONTEXT_L4.md)
- Frontend complete (see roadmap/CONTEXT_L5.md)

## Files Created
- (all previous files — see roadmap/)

## Progress Tracker
  [x] docker-compose.yml — all 6 services
  [x] Makefile — all 12 commands
  [x] README.md — complete, no placeholders
  [x] scripts/init_db.py — idempotent table creation
  [x] scripts/init_vector_db.py — idempotent collection creation
  [x] scripts/seed_demo.py — full ingest of demo PDF
  [x] tests/e2e/test_e2e.py — 5 e2e tests
  [x] pytest tests/unit/ — all pass
  [x] pytest tests/integration/ — all pass
  [x] pytest tests/e2e/ — all pass
  [x] npm run build — zero TypeScript errors
  [x] all 35 bug sweep items verified
  [x] make init runs clean
  [x] make seed runs clean

## Next
QA COMPLETE