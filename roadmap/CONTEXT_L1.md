# IT-HELPDESK-RAG — Build Context

## Project
Configurable IT Helpdesk RAG System
2 pipelines (Ingest + Query) · Hybrid search · Re-ranking · Strict grounding
Solo build — demo-first priority

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
- Re-ranking:   Cohere Rerank v3 (cohere SDK)
- PDF Parsing:  PyMuPDF (fitz)
- Chunking:     RecursiveCharacterTextSplitter (langchain-text-splitters)
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

## LLM Client Pattern (CRITICAL)
- File: app/llm/client.py — ALL LLM + embed calls go here ONLY
- Use openai SDK with custom base_url for all providers
- Provider switching via LLM_PROVIDER env var:
    if LLM_PROVIDER == "groq":
        base_url = "https://api.groq.com/openai/v1"
        api_key  = GROQ_API_KEY
    elif LLM_PROVIDER == "openrouter":
        base_url = "https://openrouter.ai/api/v1"
        api_key  = OPENROUTER_API_KEY
    else (openai):
        base_url = "https://api.openai.com/v1"
        api_key  = OPENAI_API_KEY
- Embedding switching via EMBEDDING_PROVIDER env var:
    if EMBEDDING_PROVIDER == "openrouter":  use openai SDK → OpenRouter base_url
    elif EMBEDDING_PROVIDER == "cohere":    use cohere SDK → co.embed()
    else (openai):                          use openai SDK → OpenAI base_url
- client.py exposes:
    async complete(prompt, system, model_override) → str
    async embed(texts: list[str]) → list[list[float]]
- Startup log: "llm.provider.active  provider=<> model=<>  embed_provider=<>"
- tenacity retry on all calls: 3 attempts, exponential 2–60s

## Vector DB Client Pattern (CRITICAL)
- File: app/db/vector_store.py — ALL vector DB calls go here ONLY
- Abstract base class VectorStore with:
    async ensure_collection(name, dim) → None
    async upsert(collection, id, vector, payload) → None
    async hybrid_search(collection, dense_vec, sparse_vec, top_k, filter) → list[SearchResult]
    async search_by_vector(collection, vector, top_k, filter) → list[SearchResult]
- QdrantVectorStore implements VectorStore
- MilvusVectorStore implements VectorStore
- Factory: get_vector_store() → VectorStore  (reads VECTOR_DB env var)
- No agent or pipeline imports qdrant-client or pymilvus directly

## Relational DB Client Pattern (CRITICAL)
- File: app/db/relational.py — ALL relational DB calls go here ONLY
- SQLAlchemy async engine, provider-switched:
    if RELATIONAL_DB == "mysql":   "mysql+aiomysql://..."
    else (postgres):               "postgresql+asyncpg://..."
- Tables: documents, chunks, conversation_history
- get_engine() factory reads RELATIONAL_DB env var
- No raw SQL outside relational.py

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
- Windows 11: app/main.py must set asyncio.WindowsSelectorEventLoopPolicy()

## Required .env Variables
  # LLM
  LLM_PROVIDER=groq                       # groq | openrouter | openai
  GROQ_API_KEY=
  GROQ_MODEL=llama-3.3-70b-versatile
  OPENROUTER_API_KEY=
  OPENROUTER_MODEL=google/gemini-2.0-flash-001
  OPENAI_API_KEY=
  OPENAI_MODEL=gpt-4o-mini

  # Embeddings
  EMBEDDING_PROVIDER=openai               # openai | openrouter | cohere
  OPENAI_EMBEDDING_MODEL=text-embedding-3-small
  OPENROUTER_EMBEDDING_MODEL=google/gemini-embedding-001
  COHERE_API_KEY=
  COHERE_EMBEDDING_MODEL=embed-english-v3.0
  EMBEDDING_DIM=1536                      # must match chosen model

  # Vector DB
  VECTOR_DB=qdrant                        # qdrant | milvus
  QDRANT_URL=http://localhost:6333
  QDRANT_COLLECTION=helpdesk_chunks
  MILVUS_URI=http://localhost:19530
  MILVUS_COLLECTION=helpdesk_chunks

  # Relational DB
  RELATIONAL_DB=postgres                  # postgres | mysql
  POSTGRES_URL=postgresql+asyncpg://user:pass@localhost/helpdesk
  MYSQL_URL=mysql+aiomysql://user:pass@localhost/helpdesk

  # Re-ranking
  COHERE_RERANK_MODEL=rerank-english-v3.0

  # App
  DEMO_MODE=false
  LOG_LEVEL=INFO
  MAX_CHUNKS_RETURN=20
  RERANK_TOP_N=5
  CONFIDENCE_THRESHOLD=0.6

## Directory Structure
  it-helpdesk-rag/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.py
  │   ├── llm/
  │   │   ├── __init__.py
  │   │   └── client.py          ← LLM + embed, provider-switched
  │   ├── db/
  │   │   ├── __init__.py
  │   │   ├── vector_store.py    ← abstract + Qdrant + Milvus
  │   │   └── relational.py      ← SQLAlchemy async, pg + mysql
  │   ├── ingestion/
  │   │   ├── __init__.py
  │   │   ├── pdf_parser.py
  │   │   ├── chunker.py
  │   │   └── pipeline.py
  │   ├── query/
  │   │   ├── __init__.py
  │   │   ├── router.py
  │   │   ├── hybrid_search.py
  │   │   ├── reranker.py
  │   │   ├── rag_generator.py
  │   │   └── pipeline.py
  │   ├── models/
  │   │   ├── __init__.py
  │   │   ├── document.py
  │   │   └── query.py
  │   └── api/
  │       ├── __init__.py
  │       └── routes.py
  ├── data/
  │   └── sample_pdfs/
  ├── tests/
  │   ├── __init__.py
  │   └── unit/
  │       ├── __init__.py
  │       └── test_config.py
  ├── docker-compose.yml
  ├── Dockerfile
  ├── pyproject.toml
  └── .env.example

## Files to Create in This Section (Foundation)
  - pyproject.toml                 pinned deps, no hardcoded providers
  - .env.example                   all vars above
  - docker-compose.yml             Qdrant + Milvus + Postgres + MySQL services
  - Dockerfile
  - app/__init__.py
  - app/config.py                  pydantic-settings, get_settings() lru_cache
  - app/main.py                    FastAPI create_app(), CORS, Windows policy
  - app/llm/__init__.py
  - app/llm/client.py              complete() + embed(), provider-switched
  - app/db/__init__.py
  - app/db/vector_store.py         VectorStore ABC + QdrantVectorStore + MilvusVectorStore + factory
  - app/db/relational.py           async engine factory + table definitions
  - app/models/__init__.py
  - app/models/document.py         Document, Chunk pydantic models
  - app/models/query.py            QueryRequest, QueryResponse, SearchResult pydantic models
  - tests/unit/test_config.py      settings load + provider switching tests
  - data/sample_pdfs/.gitkeep


## Built
- Config module (`pydantic-settings`)
- Main FastAPI app (`app/main.py`)
- LLM Client (`app/llm/client.py`)
- DB Models (`app/models/document.py`, `app/models/query.py`)
- Vector Store Client (`app/db/vector_store.py`)
- Relational DB Client (`app/db/relational.py`)
- Docker/System configs

## Files Created
- pyproject.toml
- .env.example
- docker-compose.yml
- Dockerfile
- app/__init__.py
- app/config.py
- app/main.py
- app/llm/__init__.py
- app/llm/client.py
- app/db/__init__.py
- app/db/vector_store.py
- app/db/relational.py
- app/models/__init__.py
- app/models/document.py
- app/models/query.py
- tests/unit/__init__.py
- tests/unit/test_config.py

## Progress Tracker
- [x] python -m app.main starts with no import errors
- [x] LLM_PROVIDER=groq → startup log shows groq + correct model
- [x] LLM_PROVIDER=openrouter → startup log shows openrouter + correct model
- [x] VECTOR_DB=qdrant → get_vector_store() returns QdrantVectorStore
- [x] VECTOR_DB=milvus → get_vector_store() returns MilvusVectorStore
- [x] RELATIONAL_DB=postgres → engine URL contains asyncpg
- [x] RELATIONAL_DB=mysql → engine URL contains aiomysql
- [x] test_config.py passes
- [x] No hardcoded model or DB strings outside config.py

## Next
QA COMPLETE
