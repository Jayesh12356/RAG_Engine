# START HERE — Bootstrap the RAG Engine

Welcome. This file exists so a brand-new cloner does **not** have to read the rest of the docs to get the project running.

## How to use this file

1. Make sure you have **Cursor**, **Claude Code**, **Antigravity**, **GitHub Copilot Chat**, **Codex CLI**, or any similar AI coding agent open in this repo.
2. Copy **everything between the two `=== AI AGENT PROMPT ===` markers below** — title, persona line, all 11 steps, troubleshooting, the lot.
3. Paste it into the agent and send.
4. Answer any prompts the agent asks (mainly your API keys).
5. Wait ~3–5 minutes. The agent will install prerequisites, start every service, run both servers and confirm the UI loads at `http://localhost:3000`.

That's it. If you would rather follow the manual steps, see the [`README.md`](README.md) Quick Start section.

---

=== AI AGENT PROMPT ===

You are a senior full-stack engineer. Your single job in this conversation is to set this RAG Engine project up end-to-end on the user's machine and verify it works in the browser, with **zero hand-holding**. You may run shell commands, edit files and call any tools you have.

## Project at a glance

- **Backend** — Python 3.11+, FastAPI on port `8000`. Entry point `app.main:app`. Production entrypoint is [`scripts/bootstrap_start.py`](scripts/bootstrap_start.py).
- **Frontend** — Next.js 14 (App Router) in [`helpdesk-ui/`](helpdesk-ui/) on port `3000`.
- **Vector DB** — Qdrant via Docker (host port `6334`, container port `6333`).
- **Relational DB** — Postgres 15 via Docker (host port `5433`, user/pass/db all `helpdesk`).
- **Optional** — Tesseract for OCR on scanned PDFs and image documents.
- **Required API keys** — at least one LLM provider key (OpenRouter / Groq / OpenAI), `OPENAI_API_KEY` for embeddings (`text-embedding-3-small`, dim 1536), and optionally `COHERE_API_KEY` for reranking (a lexical fallback works without it).

## Hard rules

- Do **not** ask the user for permission between steps. Just execute. Pause only when you genuinely need an API key or to recover from a real error.
- Detect the host OS (`Windows`, `macOS`, `Linux`) once at step 1 and use the matching shell variant for every subsequent step.
- If a step has already been done (e.g. `.env` already exists, `node_modules/` already populated), skip the redundant work but still report it.
- Run long-lived commands (uvicorn, `npm run dev`) in the background so you can move on. Tail their logs only enough to confirm "started".
- Never commit secrets. Never push to git. Never run any data-destructive script.
- If you hit a blocker, report it crisply with the exact command, exit code and the relevant error lines, then propose the smallest fix.

## Step 1 — Detect OS and verify prerequisites

Detect the OS and shell. Then confirm these are installed; print a small table of `tool / found / version`:

- `python` >= 3.11
- `node` >= 20
- `npm` (bundled with Node)
- `docker` (Docker Desktop running)
- `git`
- `tesseract` (optional — needed only for OCR)

Windows (PowerShell):

```powershell
python --version; node --version; npm --version; docker --version; git --version; (Get-Command tesseract -ErrorAction SilentlyContinue).Path
```

macOS / Linux (bash/zsh):

```bash
python3 --version && node --version && npm --version && docker --version && git --version && (command -v tesseract || echo "tesseract: not installed (optional)")
```

If any required tool is missing, install it via the platform-native package manager and re-check before moving on:

- Windows: `winget install Python.Python.3.12`, `winget install OpenJS.NodeJS.LTS`, `winget install Docker.DockerDesktop`, `winget install UB-Mannheim.TesseractOCR`.
- macOS: `brew install python@3.12 node docker tesseract`.
- Linux (Debian/Ubuntu): `sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv nodejs npm tesseract-ocr` and Docker via the official Docker docs.

Confirm Docker Desktop / `dockerd` is **running**, not just installed.

## Step 2 — Configure the environment file

Copy `.env.example` to `.env` if `.env` doesn't already exist. Then patch `.env` so the local-Docker hostnames and ports match this repo's `docker-compose.yml`:

| Key | Value |
| --- | --- |
| `QDRANT_URL` | `http://localhost:6334` |
| `POSTGRES_URL` | `postgresql+asyncpg://helpdesk:helpdesk@localhost:5433/helpdesk` |
| `RELATIONAL_DB` | `postgres` |
| `VECTOR_DB` | `qdrant` |
| `EMBEDDING_PROVIDER` | `openai` |
| `EMBEDDING_DIM` | `1536` |

Then ask the user **once** for the API keys you still need. Required: at least one of `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` for completion, **plus** `OPENAI_API_KEY` for embeddings. Optional but recommended: `COHERE_API_KEY` for high-quality reranking. Set `LLM_PROVIDER` to whichever provider the user supplied a key for (`openrouter`, `groq` or `openai`).

Patch the file in place — do not echo the keys back to the user or to logs.

Windows (PowerShell):

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# then patch values with (Get-Content .env) -replace 'KEY=.*', "KEY=$value" | Set-Content .env
```

macOS / Linux:

```bash
[ -f .env ] || cp .env.example .env
# then patch values with sed -i'' -e "s|^KEY=.*|KEY=$value|" .env
```

## Step 3 — Start the data services

Bring up Qdrant + Postgres in the background (skip Milvus / MySQL — they are alternates and not needed):

```bash
docker compose up -d postgres qdrant
```

Wait until both containers report healthy / running, then probe:

- `curl -fsS http://localhost:6334/readyz` — Qdrant should answer 200.
- `docker exec helpdesk_chatbot-postgres-1 pg_isready -U helpdesk` (substitute the actual container name returned by `docker compose ps`) — should return `accepting connections`.

If Docker Desktop is not running, start it first and wait for the whale icon.

## Step 4 — Install Python dependencies

Use a virtual environment so the global Python install stays clean.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

If `pip install` fails on Windows because of a `pymupdf` / `pillow` wheel build, install the Microsoft C++ Build Tools, retry, and only fall back to `pip install --no-build-isolation` if the wheels still won't compile.

## Step 5 — Install Node dependencies

```bash
cd helpdesk-ui
npm install
cd ..
```

This typically takes 60–120 seconds. The lockfile is honoured.

## Step 6 — Initialise the relational schema and the vector collection

Both scripts are idempotent — running them twice is safe.

```bash
python scripts/init_db.py
python scripts/init_vector_db.py
```

`init_db.py` creates the schema and tables. `init_vector_db.py` ensures the Qdrant collection exists with named dense + sparse vectors (the same path `scripts/bootstrap_start.py` runs in production).

## Step 7 — Start the backend

Launch FastAPI in the background. Wait for `Application startup complete` in its logs before moving on.

Windows (PowerShell):

```powershell
$env:PYTHONUTF8 = "1"; $env:PYTHONPATH = (Get-Location).Path
Start-Process -NoNewWindow -FilePath python -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--log-level","info" -RedirectStandardOutput backend.log -RedirectStandardError backend.err
```

macOS / Linux:

```bash
export PYTHONUTF8=1
export PYTHONPATH="$PWD"
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info > backend.log 2>&1 &
```

Probe:

```bash
curl -fsS http://localhost:8000/health
```

Expect a JSON payload like `{"status":"ok","llm_provider":"openrouter","embedding_provider":"openai","vector_db":"qdrant","relational_db":"postgres",...}`.

## Step 8 — Start the frontend

Next.js dev server, also backgrounded. Wait for `Ready in` in its logs before moving on.

Windows (PowerShell):

```powershell
Push-Location helpdesk-ui
Start-Process -NoNewWindow -FilePath npm -ArgumentList "run","dev" -RedirectStandardOutput ..\frontend.log -RedirectStandardError ..\frontend.err
Pop-Location
```

macOS / Linux:

```bash
( cd helpdesk-ui && nohup npm run dev > ../frontend.log 2>&1 & )
```

## Step 9 — Verify every UI route

Hit each route through HTTP, asserting `200` and reporting the cold-render time. The agent should set a fake `rag_engine_uid` cookie when probing `/app/*` so the auth middleware ([`helpdesk-ui/src/middleware.ts`](helpdesk-ui/src/middleware.ts)) lets the request through.

| Route | Expected |
| --- | --- |
| `GET http://localhost:3000/` | 200 |
| `GET http://localhost:3000/sign-in` | 200 |
| `GET http://localhost:3000/sign-up` | 200 |
| `GET http://localhost:3000/app` | 200 (with cookie) |
| `GET http://localhost:3000/app/query` | 200 (with cookie) |
| `GET http://localhost:3000/app/chat` | 200 (with cookie) |
| `GET http://localhost:3000/app/documents` | 200 (with cookie) |
| `GET http://localhost:3000/app/status` | 200 (with cookie) |

Print a small results table. The first hit on `/app/query` and `/app/chat` may take 10–25 seconds in dev mode (one-time webpack compile); subsequent hits should be sub-500 ms.

## Step 10 — Smoke the full RAG pipeline

End-to-end POST to confirm the pipeline runs and the refusal guardrail is wired:

```bash
curl -fsS -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "X-Demo-Mode: true" \
  -d '{"question":"List the supported document formats.","include_citations":true}'
```

You should receive a 200 with a structured response (`answer`, `confidence`, `refused`, `citations`). In demo mode without indexed corpus, expect `refused: true` and a clean refusal sentence — that proves the evidence/confidence gates are active.

## Step 11 — (Optional) Seed demo content

Only run this if the user explicitly asked for sample data:

```bash
python scripts/seed_demo.py
```

## Final report

When everything is green, print a single concise summary that includes:

- OS / shell detected.
- Tool versions.
- Container statuses for `postgres` and `qdrant`.
- `/health` response body.
- The route-by-route 200 table.
- Where to point the browser (`http://localhost:3000`).
- The two log file paths (`backend.log`, `frontend.log`) so the user can `tail -f` them.

## Troubleshooting

- **Port already in use** (3000, 8000, 5433, 6334): identify the holder (`netstat -ano | findstr :8000` on Windows, `lsof -i :8000` elsewhere) and either stop it or use a different host port. For the frontend, Next.js will offer 3001 automatically.
- **Docker not running**: start Docker Desktop / `dockerd`, wait for the daemon to be healthy, then re-run step 3.
- **`pip install` wheel build failures on Windows**: install Microsoft C++ Build Tools, then retry. As a last resort, `pip install --no-build-isolation -e ".[dev]"`.
- **Tesseract not on PATH (Windows)**: set `TESSERACT_CMD` in `.env` to the full executable path (typically `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- **`embedding.consistency_failed` at startup**: an embedding model with a different output dimensionality is configured. Either change `EMBEDDING_DIM` to match the model, or switch the model. The default pair (`text-embedding-3-small` + `EMBEDDING_DIM=1536`) is known-good.
- **Qdrant 502 on `/readyz`**: container is still warming up; wait 5–10 seconds and re-probe.
- **`/app/*` redirects to `/sign-in` even with a cookie**: ensure the cookie name is exactly `rag_engine_uid` and `path=/`.
- **Frontend can't reach backend on Vercel**: `NEXT_PUBLIC_API_URL` is missing in the Vercel project — set it to your hosted backend URL and redeploy.

=== END AI AGENT PROMPT ===

---

## After bootstrap

- The repo-root [`README.md`](README.md) is the source of truth for features, configuration, deployment and tests.
- The UI README lives in [`helpdesk-ui/README.md`](helpdesk-ui/README.md).
- The implementation manual is [`docs/reference/MANUAL.md`](docs/reference/MANUAL.md).
- Sample Q&A content for testing: [`docs/reference/sampleqna.md`](docs/reference/sampleqna.md).
- Interactive architecture diagram: [`docs/diagram-v4.html`](docs/diagram-v4.html).
