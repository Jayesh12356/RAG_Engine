# IT-HELPDESK-RAG — CONTEXT.md

## Project
Configurable IT Helpdesk RAG System
Section 7 — Multi-Turn Chat with Conversation History
Builds directly on top of all 6 previous sections — do NOT modify any existing code unless fixing a bug

## What This Section Adds
- Conversation session management — each chat has a session_id
- conversation_history relational table — stores all turns per session
- Query pipeline upgraded — last N turns injected into RAG prompt as context
- POST /chat — new endpoint replacing /query for multi-turn conversations
- GET /chat/{session_id}/history — retrieve full conversation history
- DELETE /chat/{session_id} — clear a session
- GET /chat/sessions — list all active sessions
- Frontend: /chat page — full chat interface with message bubbles, session sidebar
- Session persistence — refresh page, history reloads from DB
- Context window management — last 5 turns max injected (configurable)

## What Does NOT Change
- app/llm/client.py — untouched
- app/db/vector_store.py — untouched
- app/ingestion/ — untouched
- app/query/router.py — untouched
- app/query/hybrid_search.py — untouched
- app/query/reranker.py — untouched
- POST /query — still works exactly as before (stateless, no session)
- All existing frontend pages (/query, /documents, /status) — untouched

## Demo Mode
- demo_mode=True → conversation_history stored in memory dict instead of DB
- Session IDs still generated and returned
- History still injected into prompts
- All chat endpoints work identically in demo mode

## conversation_history Table (already declared in relational.py — extend it)
  Columns:
    id:           VARCHAR(36) PRIMARY KEY   # uuid4
    session_id:   VARCHAR(36) NOT NULL      # groups turns together
    role:         VARCHAR(16) NOT NULL      # "user" | "assistant"
    content:      TEXT NOT NULL             # full message text
    question:     TEXT                      # original user question (user turns only)
    answer:       TEXT                      # full answer (assistant turns only)
    confidence:   FLOAT                     # confidence score (assistant turns only)
    sources:      JSON                      # list of SourceChunk dicts (assistant turns only)
    service_category: VARCHAR(64)           # detected category (assistant turns only)
    created_at:   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  Index: session_id (for fast history retrieval)

  Add to app/db/relational.py:
    - ConversationHistory SQLAlchemy Table definition
    - async insert_turn(session_id, role, content, question, answer, confidence, sources, service_category) → str (turn id)
    - async get_history(session_id, limit) → list[dict]
    - async get_sessions() → list[dict]  # distinct session_ids + turn count + last_active
    - async delete_session(session_id) → int  # rows deleted

## Session Manager (app/chat/session.py)
  SessionManager class
  __init__(self, demo_mode: bool = False)
  In-memory fallback when demo_mode=True: Dict[session_id, list[dict]]

  async create_session() -> str
    return str(uuid4())   # no DB write — session created on first turn

  async add_turn(session_id, role, content, question, answer, confidence, sources, service_category) -> str
    if demo_mode: append to in-memory dict
    else: call relational.insert_turn(...)

  async get_history(session_id, limit=5) -> list[HistoryTurn]
    if demo_mode: return last `limit` from in-memory dict
    else: call relational.get_history(session_id, limit)
    return as list[HistoryTurn]

  HistoryTurn Pydantic model:
    id:               str
    session_id:       str
    role:             str        # "user" | "assistant"
    content:          str
    confidence:       float | None
    service_category: str | None
    sources:          list[dict]
    created_at:       str        # ISO format

## Chat Pipeline (app/chat/pipeline.py)
  ChatPipeline class
  __init__(self, demo_mode: bool = False)

  async run(request: ChatRequest) -> ChatResponse

  ChatRequest Pydantic model:
    session_id:       str | None = None   # None → auto-generate new session
    question:         str
    service_category: str | None = None
    top_k:            int = 20
    rerank_top_n:     int | None = None

  ChatResponse Pydantic model:
    session_id:        str
    turn_id:           str
    question:          str
    answer:            str
    confidence:        float
    confidence_label:  str      # "high" | "moderate" | "low" | "refused"
    sources:           list[SourceChunk]
    service_category:  str
    refused:           bool
    history:           list[HistoryTurn]   # full session history including this turn

  Pipeline steps:
    STEP 1: if session_id is None → create_session() → new session_id
    STEP 2: get_history(session_id, limit=settings.chat_history_turns) → list[HistoryTurn]
    STEP 3: router.detect(question) → RouterResult
    STEP 4: hybrid_search.search(question, service_category, top_k) → list[SearchResult]
    STEP 5: reranker.rerank(question, results, top_n) → list[SearchResult]
    STEP 6: build enriched prompt with history context:
              system prompt = same strict grounding prompt as RAG generator
              + history block:
                "Previous conversation:\n"
                for each turn in history:
                  "User: {turn.content}\nAssistant: {turn.answer}\n"
              + context block (retrieved chunks)
              + current question
    STEP 7: llm_client.complete(enriched_prompt, system) → answer
    STEP 8: score confidence (same logic as rag_generator.py)
    STEP 9: confidence gate (same threshold as QueryPipeline)
    STEP 10: add_turn(session_id, "user", question, ...) → user turn id
             add_turn(session_id, "assistant", answer, ...) → assistant turn id = turn_id
    STEP 11: get_history(session_id) → full updated history
    STEP 12: return ChatResponse

  CRITICAL: history is injected BEFORE context chunks in prompt.
  History must never exceed settings.chat_history_turns turns.
  If question is follow-up (e.g. "what about the second step?") →
    hybrid_search still runs on CURRENT question only (not reformulated).
    History provides implicit context via prompt injection.

## config.py additions
  chat_history_turns: int = 5    # how many prior turns to inject
  max_sessions:       int = 100  # soft limit for in-memory demo sessions

## New API Endpoints (add to app/api/routes.py)

  POST /chat
    Body: ChatRequest
    Header: X-Demo-Mode optional
    Creates session if session_id is None
    Runs ChatPipeline.run(request)
    Returns ChatResponse
    Status 200 always (refused is valid, not error)

  GET /chat/{session_id}/history
    Query param: limit (int, default 50)
    Returns: { session_id, turns: list[HistoryTurn], total: int }
    404 if session has no turns

  DELETE /chat/{session_id}
    Deletes all turns for session from DB (or memory if demo)
    Returns: { session_id, status: "deleted", turns_removed: int }

  GET /chat/sessions
    Returns: { sessions: list[SessionSummary], total: int }
    SessionSummary: { session_id, turn_count, last_active, first_question }

## Frontend — /chat page (helpdesk-ui/src/app/chat/)

### Layout
  - Two-column: left sidebar (sessions, 280px fixed) + right chat area (flex-grow)
  - Mobile: sidebar hidden, hamburger menu reveals it as overlay

### Left Sidebar (src/components/chat-sidebar.tsx)
  - "Conversations" heading + "New Chat" button (indigo-600, full width)
  - List of sessions from GET /chat/sessions
  - Each session row: first_question truncated to 40 chars, turn_count badge, last_active
  - Active session: indigo-50 bg, indigo-600 left border
  - Click session → load history into chat area
  - Delete session button (Trash2 icon, rose, on hover)
  - Empty state: "No conversations yet" slate-400

### Chat Area (src/components/chat-area.tsx)
  - Top bar: current session_id truncated + "Clear" button
  - Message list: scrollable, flex-col, gap-4, pb-32 (space for input)
  - Auto-scroll to bottom on new message
  - User bubble: right-aligned, indigo-600 bg, white text, rounded-2xl rounded-tr-sm, max-w-[70%]
  - Assistant bubble: left-aligned, white bg, border border-slate-200, rounded-2xl rounded-tl-sm, max-w-[80%]
  - Assistant bubble contains:
      answer text (prose, whitespace-pre-wrap)
      ConfidenceGauge (small, 80x55px)
      SourceAccordion (collapsed by default)
      refused state: rose-50 bg text
  - Typing indicator: 3 dot bounce animation while waiting
  - Empty state: centered "Start a conversation" + HelpCircle icon slate-300

### Input Bar (src/components/chat-input.tsx)
  - Fixed bottom of chat area
  - Textarea: auto-grow up to 5 lines, Enter=submit, Shift+Enter=newline
  - Send button: indigo-600, SendHorizonal icon, disabled while loading
  - Demo mode toggle checkbox left of send
  - Service category select (same options as /query page)

### src/app/chat/page.tsx
  State:
    sessionId: string | null
    messages: ChatMessage[]     # local state for instant render
    sessions: SessionSummary[]
    loading: boolean
    demoMode: boolean

  On mount: GET /chat/sessions → populate sidebar
  New chat: set sessionId=null, clear messages
  Select session: GET /chat/{id}/history → populate messages
  Submit question:
    1. Append user message to messages immediately (optimistic)
    2. Show typing indicator
    3. POST /chat with {session_id, question, ...}
    4. On response: set sessionId from response, append assistant message
    5. Refresh sessions sidebar
  On delete session: DELETE /chat/{id} → refresh sidebar → clear if active

### Nav update (src/components/nav.tsx)
  Add "Chat" link between "Query" and "Documents"
  Icon: MessageSquare (lucide)

## Files to Create
  - app/chat/__init__.py
  - app/chat/session.py
  - app/chat/pipeline.py
  - helpdesk-ui/src/app/chat/page.tsx
  - helpdesk-ui/src/app/chat/loading.tsx
  - helpdesk-ui/src/components/chat-sidebar.tsx
  - helpdesk-ui/src/components/chat-area.tsx
  - helpdesk-ui/src/components/chat-input.tsx
  - tests/unit/test_chat.py
  - tests/integration/test_chat_api.py

## Files to Modify (minimal, surgical changes only)
  - app/db/relational.py — add ConversationHistory table + 4 new async functions
  - app/api/routes.py — add 4 new /chat endpoints
  - app/config.py — add chat_history_turns + max_sessions
  - helpdesk-ui/src/components/nav.tsx — add Chat link
  - helpdesk-ui/src/types/index.ts — add ChatRequest, ChatResponse, HistoryTurn, SessionSummary

## tests/unit/test_chat.py
  test_session_manager_demo_create:
    SessionManager(demo_mode=True).create_session()
    assert returns non-empty string UUID

  test_session_manager_demo_add_and_get:
    manager = SessionManager(demo_mode=True)
    session_id = await manager.create_session()
    await manager.add_turn(session_id, "user", "how do I reset VPN?", ...)
    await manager.add_turn(session_id, "assistant", "Open Pulse Secure...", ...)
    history = await manager.get_history(session_id, limit=5)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"

  test_session_history_limit:
    add 10 turns to demo session
    get_history(session_id, limit=5)
    assert len(result) == 5
    assert result[-1] is the most recent turn

  test_chat_pipeline_demo_new_session:
    mock hybrid_search, reranker, llm_client.complete, session_manager
    ChatPipeline(demo_mode=True).run(ChatRequest(question="how do I reset VPN?"))
    assert response.session_id is non-empty
    assert response.refused == False
    assert len(response.history) >= 1

  test_chat_pipeline_history_injected:
    mock llm_client.complete — capture prompt argument
    pre-populate session with 2 prior turns
    run ChatPipeline with that session_id
    assert "Previous conversation" in captured prompt

  test_chat_pipeline_confidence_gate:
    mock llm_client.complete → return refusal phrase
    response = ChatPipeline(demo_mode=True).run(ChatRequest(question="weather in Paris?"))
    assert response.refused == True
    assert response.confidence_label == "refused"

## tests/integration/test_chat_api.py
  test_post_chat_new_session:
    POST /chat {"question": "how do I reset my VPN password?"}
    header X-Demo-Mode: true
    assert status 200
    assert response["session_id"] is non-empty
    assert response["refused"] == False

  test_post_chat_continues_session:
    first = POST /chat {"question": "how do I reset VPN?"}
    session_id = first["session_id"]
    second = POST /chat {"session_id": session_id, "question": "what about SSL?"}
    assert second["session_id"] == session_id
    assert len(second["history"]) == 4   # 2 user + 2 assistant turns

  test_get_history:
    POST /chat to create session
    GET /chat/{session_id}/history
    assert status 200
    assert total >= 2

  test_delete_session:
    POST /chat to create session
    DELETE /chat/{session_id}
    assert status 200
    assert response["status"] == "deleted"
    GET /chat/{session_id}/history → assert 404

  test_get_sessions:
    POST /chat twice (two turns same session)
    GET /chat/sessions
    assert total >= 1
    assert sessions[0]["turn_count"] >= 2

## Acceptance Criteria
  [ ] POST /chat with no session_id → new session created, ChatResponse returned
  [ ] POST /chat with existing session_id → history injected into prompt
  [ ] "Previous conversation" block appears in LLM prompt when history exists
  [ ] History limited to chat_history_turns (default 5) turns in prompt
  [ ] GET /chat/{session_id}/history → all turns returned
  [ ] DELETE /chat/{session_id} → session gone, GET returns 404
  [ ] GET /chat/sessions → lists all sessions with turn_count + first_question
  [ ] demo_mode=True → in-memory storage, no DB calls
  [ ] /chat page loads, shows session sidebar
  [ ] New Chat button clears messages, new session_id on next submit
  [ ] User bubble right-aligned indigo, assistant bubble left-aligned white
  [ ] Typing indicator shown while waiting for response
  [ ] SourceAccordion present in assistant bubbles
  [ ] Session click loads history from GET /chat/{id}/history
  [ ] Enter submits, Shift+Enter newlines in input
  [ ] Nav shows "Chat" link, active when on /chat
  [ ] npm run build zero TypeScript errors
  [ ] All 6 unit tests pass
  [ ] All 5 integration tests pass
  [ ] No hardcoded strings outside config.py
  [ ] No print() anywhere
  [ ] structlog used throughout

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
   - Run pytest tests/unit/test_chat.py -v
   - Run pytest tests/integration/test_chat_api.py -v
   - Run cd helpdesk-ui && npm run build
   - Verify all acceptance criteria
STEP 4 — SELF-HEAL LOOP
6. Fix every failure → re-run → repeat until ZERO failures
STEP 5 — COMPLETION
7. Only when ALL tests pass + npm run build clean + all criteria met →
   update Next → QA COMPLETE
FAIL-SAFE: never halt, always infer, always fix and retry.
OUTPUT: only the final fully updated CONTEXT.md.

## Built
- Foundation complete (see roadmap/CONTEXT_L1.md)
- Ingestion complete (see roadmap/CONTEXT_L2.md)
- Query Pipeline complete (see roadmap/CONTEXT_L3.md)
- API Layer complete (see roadmap/CONTEXT_L4.md)
- Frontend complete (see roadmap/CONTEXT_L5.md)
- E2E QA complete (see roadmap/CONTEXT_L6.md)

## Files Created
- (all previous files — see roadmap/)

## Progress Tracker
  [x] app/db/relational.py — ConversationHistory table + 4 async functions added
  [x] app/config.py — chat_history_turns + max_sessions added
  [x] app/chat/__init__.py
  [x] app/chat/session.py — SessionManager with demo fallback
  [x] app/chat/pipeline.py — ChatPipeline with history injection
  [x] app/api/routes.py — 4 new /chat endpoints added
  [x] helpdesk-ui/src/types/index.ts — ChatRequest, ChatResponse, HistoryTurn, SessionSummary added
  [x] helpdesk-ui/src/components/chat-sidebar.tsx
  [x] helpdesk-ui/src/components/chat-area.tsx
  [x] helpdesk-ui/src/components/chat-input.tsx
  [x] helpdesk-ui/src/app/chat/page.tsx
  [x] helpdesk-ui/src/app/chat/loading.tsx
  [x] helpdesk-ui/src/components/nav.tsx — Chat link added
  [x] tests/unit/test_chat.py — 6 tests
  [x] tests/integration/test_chat_api.py — 5 tests
  [x] pytest tests/unit/test_chat.py — all pass
  [x] pytest tests/integration/test_chat_api.py — all pass
  [x] npm run build — zero TypeScript errors
  [x] all 21 acceptance criteria verified

## Next
QA COMPLETE