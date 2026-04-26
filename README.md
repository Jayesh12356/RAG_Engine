# RAG Engine

A premium, grounded, confidence-gated **document Q&A engine**. Drop in PDFs, Word, Excel/CSV, PowerPoint, text, Markdown, HTML, JSON or images and ask questions with **inline citations**, **calibrated confidence**, **safe refusals** when the evidence is thin, and **rich visual answers** (Mermaid, Recharts, KaTeX, generated images) whenever the active model can produce them.

> Live demo: not deployed yet. Run locally — see [`START_HERE.md`](START_HERE.md) for a single AI-agent prompt that boots everything end-to-end, or follow the manual steps below.

---

## Bootstrapping with an AI agent

If you have Cursor, Claude Code, Antigravity, GitHub Copilot Chat, Codex CLI or any similar AI IDE, you do not have to read the rest of this README. Open [`START_HERE.md`](START_HERE.md), copy the entire prompt block, and paste it into the agent. It will:

1. Detect your OS / shell (PowerShell, bash or zsh).
2. Check Python 3.11+, Node 20+, Docker Desktop, optional Tesseract OCR.
3. Copy `.env.example` to `.env` and ask once for your API keys.
4. Bring up Postgres + Qdrant via `docker-compose`.
5. Install Python (`pip install -e ".[dev]"`) and Node deps.
6. Initialise the relational schema and the Qdrant collection.
7. Start FastAPI on `:8000` and Next.js on `:3000`.
8. Health-check every UI route and the `/health` endpoint.
9. Optionally seed the demo corpus.

That is the fastest path from `git clone` to a working browser tab.

---

## Features

- **Universal document ingestion** through a single format router ([`app/ingestion/router.py`](app/ingestion/router.py)) — PDF, DOCX, XLSX/XLS/CSV, PPTX, TXT/Markdown/HTML/JSON, and images (PNG/JPG/WEBP/TIFF/BMP). New formats are a one-line change in the extension map.
- **PDF nuance preserved** — auto-detects `text_pdf`, `image_pdf`, and `mixed_pdf`, runs Tesseract OCR for image pages, with an optional Vision-LLM fallback for low-confidence pages.
- **Heading-aware chunking** that keeps headings glued to their first paragraph and preserves table/list blocks.
- **True hybrid retrieval** on Qdrant: dense embeddings + sparse BM25 with **server-side RRF fusion**, and a persisted BM25 corpus for consistent ingest/query encoding.
- **Optional query rewriting** (LLM-driven, feature-flagged) triggered only when initial retrieval scores are weak.
- **Cohere reranking** with a local lexical fallback when the API is unavailable.
- **MMR diversification** + per-document cap applied after rerank.
- **Calibrated confidence** combining reranker score, score margin, answer↔context overlap, and refusal detection.
- **Unified evidence and confidence gates** ([`app/query/gates.py`](app/query/gates.py)) shared by `/query` and `/chat` — prefer "I don't know" over hallucinations.
- **Optional grounded citations** in API responses (`include_citations: true`).
- **Provider failover** for completion *and* embeddings (Groq / OpenAI / OpenRouter, plus Cohere for embeddings) with bounded retries on streaming connections.
- **Multi-turn chat** with session storage and short-term history on top of the same retrieval pipeline.
- **Streaming APIs** via Server-Sent Events: `/query/stream` and `/chat/stream` emit `delta` events followed by a `final` event (with optional citations).
- **Rich visual answers** — Markdown answers render Mermaid diagrams, KaTeX math, syntax-highlighted code (Shiki), Recharts charts and (when the active visual model supports it) generated images. Visual richness is detected automatically from the model name pattern; the user just asks a question.
- **Premium Next.js UI** — auth shell, sidebar/topbar app shell, query + chat surfaces, document library and a live status page. Single-token typography (15/14/13/12/11px tiers), accessible Radix primitives, light + dark themes, mobile-first.
- **Generic refusal on errors** — pipelines never leak raw exceptions to clients.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Pydantic v2, structlog |
| Document ingestion | PyMuPDF, python-docx, python-pptx, openpyxl/xlrd, pandas, beautifulsoup4, markdown, chardet, Pillow, pdf2image, pytesseract |
| Text Chunking | `langchain-text-splitters` with heading-aware splits |
| Embeddings | OpenAI / OpenRouter / Cohere (configurable, with cross-provider failover) |
| Vector DB | Qdrant (named dense + sparse vectors, RRF fusion) or Milvus (dense-only) |
| Relational DB | PostgreSQL or MySQL |
| Reranking | Cohere Rerank with local lexical fallback |
| Frontend | Next.js 14 (App Router), Tailwind CSS, Radix UI, Framer Motion |
| Answer rendering | react-markdown + remark-gfm + remark-math, rehype-katex, Shiki, Mermaid, Recharts |
| Tooling | ruff, black, mypy, pytest, eslint, next lint |

---

## Documentation

The full reference manual lives under `docs/`:

- [`docs/reference/MANUAL.md`](docs/reference/MANUAL.md) — implementation-level behaviour, accuracy/grounding strategy, and API contracts.
- [`docs/reference/sampleqna.md`](docs/reference/sampleqna.md) — sample Q&A content used for testing.
- [`docs/diagram-v4.html`](docs/diagram-v4.html) — interactive end-to-end architecture diagram.

---

## Architecture

```text
Ingestion: Document → Format router → Parse (+ OCR for image pages) →
           Heading-aware chunks → Dense + Sparse vectors →
           Persist BM25 corpus → Upsert Qdrant (named dense + sparse) +
           Relational DB (Postgres/MySQL)

Query / Chat: Question → Router (category + intent) → Optional rewrite →
              Hybrid search (dense + sparse, server-side RRF) → Cohere rerank
              with lexical fallback → MMR + per-doc cap → Evidence gate →
              Generator (category-aware system prompt) → Calibrated confidence
              gate → Response (+ optional citations / visuals / SSE deltas)
```

- **Ingestion** dispatches each file through the format router, parses it (with OCR when needed for PDFs and images), chunks text with heading-aware boundaries, builds dense + sparse vectors, persists BM25 corpus statistics for consistent query-time encoding, upserts named-vector points into Qdrant, and stores document metadata in the relational store.
- **Query** routes the request, optionally rewrites the question when retrieval scores are weak, fetches candidates with hybrid search (server-side RRF), reranks them, diversifies with MMR + per-doc cap, then generates a grounded answer that is gated by both an evidence check and a calibrated confidence threshold.
- **Chat** layers session history on top of the same retrieval pipeline and shares the same evidence/confidence gates.

For a deeper, implementation-level explanation see [`docs/reference/MANUAL.md`](docs/reference/MANUAL.md).

---

## Quick Start (manual)

> Prefer the AI-agent path? Use [`START_HERE.md`](START_HERE.md) and skip the rest of this section.

### 1. Clone and configure

```bash
git clone https://github.com/Jayesh12356/RAG_Engine.git
cd RAG_Engine
cp .env.example .env
```

Fill in at least:

- `OPENROUTER_API_KEY` (or `GROQ_API_KEY` / `OPENAI_API_KEY`)
- `OPENAI_API_KEY` (used for embeddings by default)
- `COHERE_API_KEY` (for reranking — optional, lexical fallback works without it)
- DB URLs, or keep defaults for local Docker

### 2. Optional: OCR for scanned PDFs and images

If you want OCR for scanned/image documents, install **Tesseract** locally and configure these env vars (see `.env.example`):

- `OCR_ENABLED`, `OCR_MODE` (`tesseract` | `vision` | `hybrid`), `OCR_LANGUAGES`, `OCR_RENDER_DPI`
- `OCR_TEXT_CONFIDENCE_THRESHOLD`, `OCR_VISION_FALLBACK_ENABLED`
- `TESSERACT_CMD` (Windows full path if needed)

### 3. Start local services

```bash
make up       # Qdrant/Milvus + Postgres/MySQL via docker-compose
```

### 4. Install dependencies and initialise

```bash
make install  # backend (Python) + frontend (Node) deps
make init     # creates relational tables and the vector collection
```

### 5. Run backend and frontend

```bash
make dev-backend    # FastAPI with autoreload
make dev-frontend   # Next.js dev server
```

Open `http://localhost:3000`.

### 6. Ingest documents

Use the UI to upload files, or call `POST /ingest` directly. Sample assets live under `data/sample_pdfs/`.

> **Migrating to Qdrant hybrid:** if you previously ran the dense-only collection, run `python scripts/migrate_qdrant_hybrid.py --confirm` and re-ingest your documents. The script recreates the Qdrant collection with named dense + sparse vectors required for server-side RRF.

---

## Deployment

### Frontend on Vercel (helpdesk-ui repo)

- Keep frontend deployment connected to the `helpdesk-ui` source repository.
- Set `NEXT_PUBLIC_API_URL=https://<your-render-backend>.onrender.com`.
- Do not leave this env empty, otherwise the frontend falls back to `localhost`.

### Backend on Render (single-command startup)

Use this as the Render start command:

```bash
python scripts/bootstrap_start.py
```

What this command does on each deploy:

1. Initialises the relational schema idempotently (`create_all`).
2. Ensures the vector collection exists in Qdrant (with named dense + sparse vectors).
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

- `DATABASE_URL` is preferred in production; `postgres://` is auto-normalised to async SQLAlchemy format.
- `DB_SCHEMA` isolates tables when sharing one Postgres instance; use a unique schema per project.
- A Qdrant API key is optional locally but required for most Qdrant Cloud projects.
- Seed data ingestion is intentionally skipped in production startup (only schema + collection bootstrap).

---

## API Surface

- **Health**
  - `GET /health` — returns provider, vector_db, relational_db, demo_mode, `visual_capable`, `image_gen_active`.
- **Ingestion & documents**
  - `POST /ingest` — accepts every supported document type (see `app/ingestion/router.py`).
  - `GET /documents`
  - `GET /documents/{document_id}/chunks`
  - `DELETE /documents/{document_id}`
  - `GET /pdfs/{pdf_name}` (serves original PDFs for source links)
- **Query**
  - `POST /query` — standard request/response.
  - `POST /query/stream` — SSE streaming (`delta` + `final`).
- **Chat**
  - `POST /chat`
  - `POST /chat/stream` — SSE streaming.
  - `GET /chat/sessions`
  - `GET /chat/{session_id}/history`
  - `DELETE /chat/{session_id}`

Both `/query` and `/chat` accept an optional `include_citations: true` to receive a structured `citations` list pointing back to the retrieved chunks (chunk id, document id, source name, page number, section title, score).

For full payload shapes and behaviour, see [`docs/reference/MANUAL.md`](docs/reference/MANUAL.md).

---

## Configuration Highlights

All behaviour is driven by environment variables loaded into `app/config.py`. The full surface lives in `.env.example`; this section enumerates the knobs that ship with the upgraded pipeline.

### LLM and embeddings

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `groq` | Primary provider; failover walks the configured set. |
| `GROQ_MODEL` / `OPENROUTER_MODEL` / `OPENAI_MODEL` | provider defaults | Per-provider model id. |
| `LLM_REQUEST_TIMEOUT_SEC` | `25.0` | Per-call timeout for both completion and embedding. |
| `LLM_RETRY_ATTEMPTS` | `2` | Bounded retries per provider before failover. |
| `EMBEDDING_PROVIDER` | `openai` | Cross-provider failover (`openai` / `openrouter` / `cohere`). |
| `OPENAI_EMBEDDING_MODEL` / `OPENROUTER_EMBEDDING_MODEL` / `COHERE_EMBEDDING_MODEL` | model ids | Embedding models per provider. |
| `EMBEDDING_DIM` | `1536` | Dimensionality used for the dense Qdrant vector. |

### Vector and relational stores

| Variable | Default | Purpose |
| --- | --- | --- |
| `VECTOR_DB` | `qdrant` | Hybrid (`qdrant`) or dense-only (`milvus`). |
| `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION` | local | Qdrant connection. |
| `MILVUS_URI` / `MILVUS_COLLECTION` | local | Milvus connection. |
| `RELATIONAL_DB` | `postgres` | Backing relational store. |
| `DATABASE_URL` / `POSTGRES_URL` / `MYSQL_URL` | — | Async DSNs (`postgres://` is auto-normalised). |
| `DB_SCHEMA` | `public` | Schema namespace for shared databases. |

### Retrieval, gating, and confidence

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAX_CHUNKS_RETURN` | `20` | Initial recall budget before rerank. |
| `RERANK_TOP_N` | `10` | Chunks kept after rerank. |
| `CONFIDENCE_THRESHOLD` | `0.40` | Minimum calibrated confidence to return an answer. |
| `RELEVANCE_MIN_TOP_SCORE` | `0.22` | Top-1 evidence floor (gate refuses below this). |
| `RELEVANCE_MIN_SECOND_SCORE` | `0.12` | Top-2 evidence floor for support. |
| `RELEVANCE_MIN_SCORE_GAP` | `0.03` | Minimum top-1 vs top-2 margin. |
| `MIN_FALLBACK_OVERLAP` | `0.20` | Minimum answer↔context Jaccard for extractive fallback. |
| `EXTRACTIVE_FALLBACK_CONFIDENCE` | `0.45` | Confidence assigned when fallback succeeds. |

### Hybrid retrieval (Qdrant)

| Variable | Default | Purpose |
| --- | --- | --- |
| `HYBRID_RRF_K` | `60` | RRF fusion constant for server-side fusion. |
| `HYBRID_DENSE_LIMIT` | `50` | Dense prefetch limit before fusion. |
| `HYBRID_SPARSE_LIMIT` | `50` | Sparse prefetch limit before fusion. |
| `SPARSE_INDEX_DIR` | `data/sparse_index` | Where the BM25 corpus statistics are persisted. |

### Diversification, citations, rewriting

| Variable | Default | Purpose |
| --- | --- | --- |
| `MMR_ENABLED` | `true` | Enable MMR after rerank. |
| `MMR_LAMBDA` | `0.7` | Relevance vs novelty trade-off (1.0 = pure relevance). |
| `MAX_PER_DOC` | `2` | Hard cap on chunks from a single document post-MMR. |
| `INCLUDE_CITATIONS_DEFAULT` | `false` | Server default if request omits `include_citations`. |
| `QUERY_REWRITE_ENABLED` | `false` | Feature flag for LLM-driven query rewriting. |
| `QUERY_REWRITE_TRIGGER_SCORE` | `0.40` | Top-score threshold below which a rewrite is attempted. |
| `INTENT_TROUBLESHOOT_TOP_K_BOOST` | `6` | Extra recall when router detects troubleshooting intent. |
| `INTENT_HOWTO_TOP_K_BOOST` | `4` | Extra recall for "how to" questions. |

### Ingestion and chunking

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `512` / `64` | Recursive splitter targets. |
| `EMBED_BATCH_SIZE` | `32` | Embedding batch size during ingestion. |
| `HEADING_AWARE_CHUNKING` | `true` | Keep headings attached to their first paragraph. |
| `OCR_ENABLED` / `OCR_MODE` | `true` / `hybrid` | Tesseract, Vision, or hybrid OCR. |
| `OCR_VISION_FALLBACK_ENABLED` | `false` | Use Vision LLM only on low-confidence Tesseract pages. |
| `PDF_STORAGE_BACKEND` | `relational` | Where original PDFs are kept (`relational` or `vector`). |

### Streaming, chat, and CORS

| Variable | Default | Purpose |
| --- | --- | --- |
| `QUERY_STREAM_CHUNK_SIZE` | `40` | Char budget per `delta` event when synthesising streams. |
| `CHAT_HISTORY_TURNS` | `5` | Recent turns surfaced in the chat prompt. |
| `MAX_SESSIONS` | `100` | In-memory session ceiling. |
| `CORS_ALLOW_ORIGINS` | `localhost` | Comma-separated origins allowed by FastAPI. |

---

## Scanned & Image-Heavy Documents

Some manuals and reports are scanned images rather than digital text. The ingestion pipeline handles these transparently:

- **Detection**: page-text density inspection with PyMuPDF; PDFs are classified as `text_pdf`, `image_pdf`, or `mixed_pdf` and routed page-by-page. Standalone image files (PNG/JPG/WEBP/TIFF/BMP) flow through the same OCR pipeline via the `image` extractor.
- **OCR pipeline**:
  - Primary: local Tesseract OCR (multilingual via `OCR_LANGUAGES`).
  - Optional: Vision-LLM fallback for low-confidence pages.
  - Returns the same `ParsedPage` model used by the regular parser, so chunking and embedding remain unchanged downstream.

Behaviour summary:

- With `OCR_VISION_FALLBACK_ENABLED=false` (default), only Tesseract is used.
- With `true`, Vision OCR is used **only** for low-confidence OCR pages.
- If enabled but no valid Vision API key exists, ingestion falls back to Tesseract-only without failing.

Drop scanned PDFs and images into the upload zone in the UI, or POST them to `/ingest`.

---

## Project Structure

```text
helpdesk-ui/                                  # Next.js frontend
  src/
    app/
      page.tsx                                # Landing
      sign-in/, sign-up/                      # Auth shell
      app/{query,chat,documents,status}/      # In-app surfaces
      layout.tsx, globals.css
    components/
      answer/                                 # Markdown, code, charts, citations
      app/                                    # Sidebar, topbar, command palette, onboarding
      auth/                                   # Auth shell + forms
      chat/                                   # Composer, sessions rail, message bubble
      documents/                              # Upload zone, doc card, inspect sheet
      landing/                                # Hero, features, demo card, testimonial
      query/                                  # One-shot query surface helpers
      status/                                 # Status tiles
      ui/                                     # Primitives (button, dialog, dropdown, ...)
    lib/                                      # auth, motion, utils, api client
    middleware.ts                             # Auth-cookie redirect for /app/*
app/
  api/                                        # FastAPI routes and SSE endpoints
  chat/                                       # Chat pipeline and session handling
  config.py                                   # Centralised settings (Pydantic-based)
  db/                                         # Relational + vector store integrations
  ingestion/
    router.py                                 # Format dispatcher
    extractors/                               # pdf, docx, spreadsheet, pptx, text, image
    pdf_parser.py, ocr_parser.py              # PDF + OCR specifics
    chunker.py, sparse.py, pipeline.py
  llm/                                        # LLM + embeddings client with provider failover
  models/                                     # Pydantic models / schemas
  query/                                      # Hybrid search, gates, diversify, rerank, rewrite, RAG, pipelines
  storage/                                    # Original-document storage backends
  main.py                                     # FastAPI application entrypoint
docs/
  reference/MANUAL.md                         # Detailed system manual and API behaviour
  reference/sampleqna.md                      # Sample Q&A
  diagram-v4.html                             # Interactive architecture diagram
tests/
  unit/                                       # Isolated unit tests
  integration/                                # API and boundary tests
  e2e/                                        # End-to-end workflow tests (mocked + optional live)
scripts/
  bootstrap_start.py                          # Render entrypoint (init schema + collection + uvicorn)
  init_db.py                                  # Relational DB initialisation
  init_vector_db.py                           # Vector DB initialisation
  seed_demo.py                                # Demo document ingestion helper
  migrate_qdrant_hybrid.py                    # One-shot migration to named dense + sparse Qdrant collection
data/
  sample_pdfs/                                # Example documents for demo and testing
START_HERE.md                                 # Single AI-agent bootstrap prompt
```

---

## Testing

- `pytest -q` — runs unit, integration, and mocked E2E suites.
- `RUN_LIVE_E2E=1 pytest tests/e2e/test_live_e2e.py -q` — exercises the live ingest → query path against real Qdrant + provider keys (cleanly skipped if Qdrant or keys are unavailable).
- `ruff check .` and `mypy app/` keep the codebase lint- and type-clean.
- `npm run lint` and `npm run build` from `helpdesk-ui/` keep the frontend lint- and type-clean.

---

## License

MIT (adjust if you publish under a different license).
