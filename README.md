# ⚡ RAG Engine (IT Helpdesk)

Grounded, confidence-gated IT helpdesk chatbot built with a production-style Retrieval-Augmented Generation (RAG) pipeline.
Upload IT PDFs (network, VPN, SSL, Linux/cloud guides, device manuals, etc.) and ask questions with **sources** and **safe refusals** when evidence is insufficient.

## Live Demo
- Not deployed yet. Run locally using the steps below.

---

## Features

- 📄 **PDF Ingestion** (digital text PDFs)
- 🖼️ **Scanned / Image PDF Support**
  - Auto-detects `text_pdf`, `image_pdf`, and `mixed_pdf`
  - Uses OCR for image pages (local Tesseract; optional Vision fallback)
- 🔎 **Hybrid Retrieval**
  - Dense embeddings + sparse BM25 vectors for stronger candidate recall
- ⚖️ **Evidence & Confidence Gates**
  - Retrieval quality checks and confidence-based refusal to reduce hallucinations
- 🧠 **Reranking + Fallbacks**
  - Cohere reranking when available, with local fallback on failures
- 🔄 **Provider Failover**
  - Automatic LLM provider rotation across configured keys
- 📡 **Streaming APIs (SSE)**
  - `/query/stream` and `/chat/stream` emit `delta` then `final`

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11+, FastAPI |
| Ingestion / Parsing | PyMuPDF + OCR (Tesseract; optional Vision) |
| Text Chunking | `langchain-text-splitters` |
| Embeddings | OpenAI / OpenRouter / Cohere (configurable) |
| Vector DB | Qdrant or Milvus |
| Relational DB | Postgres or MySQL |
| Retrieval | Dense + BM25 sparse hybrid search |

---

## Documentation

This repo includes a full reference manual under `docs/`:

- `docs/reference/MANUAL.md` (implementation-level behavior, accuracy/grounding strategy, API contracts)
- `docs/reference/sampleqna.md` (sample Q&A content used for testing)
- `docs/reference/helpdesk_flow.png` (flow image)
- `docs/diagram-v4.gif` (end-to-end architecture animation)
- `docs/diagram-v4.html` (source for the architecture diagram)

---

## Quick Start

### 1) Clone & Configure

```bash
git clone https://github.com/Jayesh12356/RAG_Engine.git
cd RAG_Engine
```

Copy env:

```bash
cp .env.example .env
```

### 2) OCR (Optional but recommended for scanned PDFs)

If you want OCR for scanned/image PDFs:

- Ensure **Tesseract** is installed on your machine
- Configure these env vars (see `.env.example`):
  - `OCR_ENABLED`
  - `OCR_LANGUAGES`
  - `OCR_RENDER_DPI`
  - `OCR_TEXT_CONFIDENCE_THRESHOLD`
  - `OCR_VISION_FALLBACK_ENABLED` (default `false`; set `true` to enable Vision fallback)
  - `TESSERACT_CMD` (Windows full path if needed)

### 3) Start local services

```bash
make up
```

### 4) Install dependencies & initialize DBs

```bash
make install
make init
```

### 5) Run backend + frontend

Backend:

```bash
make dev-backend
```

Frontend:

```bash
make dev-frontend
```

Open: `http://localhost:3000`

### 6) Ingest PDFs

Use the UI to upload PDFs. For OCR testing, your scanned assets live in:

- `image_pdfs/` (image/scanned PDFs)

---

## Deployment (Vercel + Render + Qdrant Cloud)

### Frontend on Vercel (helpdesk-ui repo)

- Keep frontend deployment connected to the `helpdesk-ui` source repository.
- Set frontend env:
  - `NEXT_PUBLIC_API_URL=https://<your-render-backend>.onrender.com`
- Do not leave this env empty, otherwise frontend falls back to localhost.

### Backend on Render (single-command startup)

Use this as Render start command:

```bash
python scripts/bootstrap_start.py
```

What this one command does on each deploy:

1. Initializes relational schema idempotently (`create_all`).
2. Ensures vector collection exists in Qdrant.
3. Starts FastAPI/Uvicorn.

### Required Render backend env vars

```env
RELATIONAL_DB=postgres
DATABASE_URL=postgres://<user>:<password>@<host>:5432/<db>
DB_SCHEMA=helpdesk_chatbot

VECTOR_DB=qdrant
QDRANT_URL=https://<cluster-id>.<region>.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=<qdrant-cloud-api-key>
QDRANT_COLLECTION=helpdesk_chunks

CORS_ALLOW_ORIGINS=https://<your-vercel-app>.vercel.app,http://localhost:3000
```

Notes:

- `DATABASE_URL` is preferred in production; `postgres://` is auto-normalized to async SQLAlchemy format.
- `DB_SCHEMA` isolates tables per app when sharing one Postgres instance; use a unique schema per project.
- Qdrant API key is optional locally, but required for most Qdrant Cloud projects.
- Seed data ingestion is intentionally skipped in production startup (only schema + collection bootstrap).

---

## API (High Level)

- `GET /health`
- `POST /ingest` (PDF upload and ingestion)
- `GET /pdfs/{pdf_name}` (serve original PDFs for source links)
- `GET /documents` + `GET /documents/{document_id}/chunks` + `DELETE /documents/{document_id}`
- `POST /query` and `POST /query/stream`
- `POST /chat` and `POST /chat/stream`

For the full operational contract and behavior details, see `docs/reference/MANUAL.md`.

---

## Project Structure

```text
helpdesk-ui/          # Frontend (Next.js)
app/                  # FastAPI backend
  api/                # Web boundaries + routes (incl. SSE streaming)
  db/                 # Vector + relational adapters
  ingestion/          # PDF parsing, OCR, chunking, ingestion pipeline
  llm/                # Provider routing for completion + embeddings
  query/              # Hybrid retrieval + reranking + RAG generation
  chat/               # Session + chat orchestration
data/
  sample_pdfs/        # Demo PDFs
image_pdfs/           # OCR testing PDFs
docs/                  # Architecture diagrams + reference manual
tests/                 # Unit + integration + e2e tests
scripts/               # Init / seed helpers
```

---

## License

MIT (add/adjust if you publish under a different license).

## RAG Engine – IT Helpdesk Assistant

### Overview

**RAG Engine** is an IT helpdesk assistant built on a production-grade Retrieval-Augmented Generation (RAG) stack.  
It ingests your IT PDFs (VPN, network, SSL, Linux, cloud, device guides, etc.), stores them in a hybrid vector + relational backend, and answers user questions with:

- **Grounded responses** strictly based on your documentation.
- **Confidence scores and cited sources** (page-level PDF links).
- **Safe refusals** when evidence is weak instead of hallucinating.

The system is designed for **enterprise environments** with configurable providers, databases, and routing behavior.

---

### Architecture

```text
PDF → Ingestion Pipeline → Vector DB (Qdrant/Milvus) + Relational DB (Postgres/MySQL)
User Question → Query/Chat Pipeline → Router → Hybrid Search → Reranker → RAG Generator → Response
```

- **Ingestion**: parses PDFs, chunks text, builds dense + sparse vectors, and persists metadata.
- **Query**: routes requests, retrieves relevant chunks, reranks, and generates answers with grounding + confidence gating.
- **Chat**: maintains short-term session history on top of the same retrieval pipeline.

For a deeper, implementation-level explanation, see `docs/reference/MANUAL.md`.

---

### Key Features

- **Hybrid retrieval**: dense embeddings + BM25-style sparse vectors for robust matching.
- **Provider failover**: Groq, OpenAI, and OpenRouter with automatic fallback for both generation and embeddings.
- **Cohere reranking**: high-quality reranking when available, with local relevance fallback.
- **Strict grounding**: prompts and pipelines tuned to prefer “I don’t know” over hallucinations.
- **Streaming APIs**: Server-Sent Events (SSE) endpoints for both Query and Chat.
- **Scanned/Image PDF support**:
  - Auto-detects `text_pdf`, `image_pdf`, and `mixed_pdf`.
  - Uses PyMuPDF for digital text.
  - Uses OCR (Tesseract + optional Vision fallback) for image-only pages.

---

### Prerequisites

- **Backend**
  - Python 3.11+
  - Docker + Docker Compose (for local DBs and vector stores)
- **Frontend**
  - Node.js 18+
- **API keys**
  - At least one LLM provider key (Groq recommended – generous free tier)
  - Cohere API key (for reranking)

---

### Quick Start

1. **Configure environment**
   - Copy the example file:
     - `cp .env.example .env`
   - Fill in at least:
     - `GROQ_API_KEY`
     - `COHERE_API_KEY`
     - DB URLs (or keep defaults for local Docker)
2. **Start infrastructure**
   - `make up`  
     Starts Qdrant/Milvus + Postgres/MySQL (depending on config).
3. **Install dependencies**
   - `make install`  
     Installs Python and frontend dependencies.
4. **Initialize databases**
   - `make init`  
     Creates relational tables + vector collections.
5. **Run dev environment**
   - Terminal 1: `make dev-backend`
   - Terminal 2: `make dev-frontend`
   - Open `http://localhost:3000`
6. **Ingest PDFs**
   - Go to the Documents/ingestion screen and upload PDFs from `data/sample_pdfs/` or your own docs.
7. **Query and Chat**
   - Use the Query and Chat UIs to ask IT questions and inspect sourced answers.

---

### Scanned / Image PDF Support

Some IT manuals are scanned images rather than digital text. The ingestion pipeline handles these transparently:

- **Detection**
  - Inspects page text density with PyMuPDF.
  - Classifies documents as:
    - `text_pdf` – normal digital text.
    - `image_pdf` – predominantly scanned/image-based.
    - `mixed_pdf` – combination, routed page-by-page.
- **OCR pipeline**
  - Primary: local Tesseract OCR (multilingual).
  - Optional: Vision-based OCR fallback for low-confidence pages.
  - Returns the same `ParsedPage` model used by the normal parser so chunking and embeddings remain unchanged.

**OCR-related env vars** (see `.env.example` for defaults):

- `OCR_ENABLED` – master switch for OCR.
- `OCR_LANGUAGES` – e.g. `eng+hin`.
- `OCR_RENDER_DPI` – page render DPI for OCR (e.g. `300`).
- `OCR_TEXT_CONFIDENCE_THRESHOLD` – triggers Vision fallback below this score.
- `OCR_VISION_FALLBACK_ENABLED` – `false` by default; set `true` to enable Vision fallback.
- `OCR_VISION_MODEL` – e.g. `gpt-4o-mini`.
- `TESSERACT_CMD` – full path to `tesseract` on Windows if not on `PATH`.

Behavior:

- With `OCR_VISION_FALLBACK_ENABLED=false` (default), only Tesseract is used.
- With `true`, Vision OCR is used **only** for low-confidence OCR pages.
- If enabled but no valid Vision API key exists, ingestion automatically falls back to Tesseract-only without failing.

Place sample scanned PDFs under `image_pdfs/` and ingest them through `/ingest` or the UI like any other document.

---

### API Surface (High-Level)

- **Health**
  - `GET /health`
- **Ingestion & documents**
  - `POST /ingest`
  - `GET /documents`
  - `GET /documents/{document_id}/chunks`
  - `DELETE /documents/{document_id}`
  - `GET /pdfs/{pdf_name}` – serves original PDFs for source links.
- **Query**
  - `POST /query` – standard request/response.
  - `POST /query/stream` – SSE streaming (`delta` + `final` events).
- **Chat**
  - `POST /chat`
  - `POST /chat/stream` – SSE streaming.
  - `GET /chat/sessions`
  - `GET /chat/{session_id}/history`
  - `DELETE /chat/{session_id}`

Details for each endpoint, payload shape, and behavior are documented in `docs/reference/MANUAL.md`.

---

### Configuration Highlights

Most behavior is driven by `.env` and `app/config.py`:

- **LLM**
  - `LLM_PROVIDER` ∈ `{groq, openrouter, openai}`
  - Provider-specific models and timeouts.
- **Embeddings**
  - `EMBEDDING_PROVIDER` ∈ `{openai, openrouter, cohere}`
- **Vector / relational DB**
  - `VECTOR_DB` ∈ `{qdrant, milvus}`
  - `RELATIONAL_DB` ∈ `{postgres, mysql}`
- **Retrieval & confidence**
  - `MAX_CHUNKS_RETURN`, `RERANK_TOP_N`, `CONFIDENCE_THRESHOLD`, and related relevance thresholds.
- **Chat/session**
  - `CHAT_HISTORY_TURNS`, `MAX_SESSIONS`.

---

### Project Structure

```text
helpdesk-ui/          # Next.js frontend (query + chat UI, streaming clients)
app/
  api/                # FastAPI routes and SSE endpoints
  chat/               # Chat pipeline and session handling
  config.py           # Centralized settings (Pydantic-based)
  db/                 # Relational + vector store integrations
  ingestion/          # PDF parsing, OCR, chunking, and ingestion pipeline
  llm/                # LLM + embeddings client with provider failover
  models/             # Pydantic models / schemas
  query/              # Hybrid search, reranking, RAG generation, pipelines
  main.py             # FastAPI application entrypoint
docs/
  reference/MANUAL.md # Detailed system manual and API behavior
tests/
  unit/               # Isolated unit tests
  integration/        # API and boundary tests
  e2e/                # End-to-end workflow tests
scripts/
  init_db.py          # Relational DB initialization
  init_vector_db.py   # Vector DB initialization
  seed_demo.py        # Demo PDF ingestion helper
data/
  sample_pdfs/        # Example IT PDFs for demo and testing
image_pdfs/           # Scanned/Image PDFs for OCR testing
```

---

### License

This project is intended as an internal/reference implementation for IT helpdesk RAG systems.  
Add your chosen license here before public or commercial deployment.