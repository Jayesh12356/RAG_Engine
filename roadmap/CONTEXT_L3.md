```markdown
# IT-HELPDESK-RAG — CONTEXT.md

## Project
Configurable IT Helpdesk RAG System
Query Pipeline — routing → hybrid search → re-rank → RAG generation → confidence gate → response assembly
Builds directly on top of Ingestion — all Foundation + Ingestion code remains intact

## What This Section Adds
- Query router — detects service_category and intent from user question
- Hybrid search — dense + sparse simultaneous query against vector DB
- Cohere re-ranker — top-20 → top-5 precision step
- RAG generator — strict grounding prompt, answer ONLY from context
- Confidence gate — score below threshold → refuse to answer
- Response assembler — answer + source chunks + page numbers + PDF URLs
- Query pipeline wiring all steps together
- Query unit tests with mocked dependencies

## Demo Mode
- ALL external calls have a --demo-mode fallback
- demo_mode=True → skip live vector DB calls, use hardcoded sample chunks
- LLM still runs in demo mode (RAG generation always uses real LLM)
- Every query stage MUST implement both live and demo paths

## Stack (unchanged — do not modify any existing files)
- LLM:          Configurable via LLM_PROVIDER (groq/openrouter/openai)
- Embeddings:   Configurable via EMBEDDING_PROVIDER (openai/openrouter/cohere)
- Vector DB:    Configurable via VECTOR_DB (qdrant/milvus)
- Relational DB: Configurable via RELATIONAL_DB (postgres/mysql)
- Re-ranking:   Cohere Rerank v3 (cohere SDK) — COHERE_API_KEY required
- API:          FastAPI
- Config:       pydantic-settings
- Logging:      structlog
- Python:       3.11+, async throughout

## Existing Code (already built — do NOT rebuild or modify)
- app/config.py — all settings including CONFIDENCE_THRESHOLD, RERANK_TOP_N, MAX_CHUNKS_RETURN
- app/main.py — FastAPI app
- app/llm/client.py — complete() + embed()
- app/db/vector_store.py — VectorStore ABC, hybrid_search(), search_by_vector()
- app/db/relational.py — async SQLAlchemy engine
- app/models/document.py — Document, Chunk
- app/models/query.py — QueryRequest, QueryResponse, SearchResult
- app/ingestion/ — full ingestion pipeline (do not touch)

## Query Pipeline Spec

### app/models/query.py — ensure these models exist (add if missing)
  QueryRequest:
    question:         str
    service_category: str | None = None   # if None → router detects it
    top_k:            int = 20            # chunks to retrieve before rerank
    rerank_top_n:     int | None = None   # if None → use settings.RERANK_TOP_N

  SourceChunk:
    chunk_id:      str
    text:          str
    pdf_name:      str
    pdf_url:       str        # "/pdfs/{pdf_name}" — viewer link
    page_number:   int
    section_title: str
    score:         float      # rerank score

  QueryResponse:
    question:          str
    answer:            str
    confidence:        float        # 0.0–1.0
    confidence_label:  str          # "high" | "moderate" | "low" | "refused"
    sources:           list[SourceChunk]
    service_category:  str
    refused:           bool = False  # True if confidence < threshold

### app/query/router.py
- QueryRouter class
- async detect(question: str) -> RouterResult
- RouterResult Pydantic model:
    service_category: str    # e.g. "VPN", "SSL", "EMAIL", "GENERAL"
    intent:           str    # e.g. "troubleshoot", "howto", "info"
    key_terms:        list[str]
- Uses llm_client.complete() with structured JSON prompt
- Prompt instructs LLM to return ONLY JSON:
    {"service_category": "...", "intent": "...", "key_terms": [...]}
- Parse JSON from response — strip markdown fences before parsing
- Fallback: if parse fails → RouterResult(service_category="GENERAL", intent="info", key_terms=[])
- demo fallback: if demo_mode=True → skip LLM, return RouterResult from question heuristics
    (if "vpn" in question.lower() → "VPN", if "ssl" in question.lower() → "SSL", else "GENERAL")

### app/query/hybrid_search.py
- HybridSearch class
- __init__(self, demo_mode: bool = False)
- async search(question: str, service_category: str | None, top_k: int) -> list[SearchResult]
- Steps:
    1. embed question → dense_vector via llm_client.embed([question])[0]
    2. build sparse_vector: BM25SparseEncoder fit on [question] + encode(question)
       (single-query BM25 — good enough for query-time sparse)
    3. build metadata filter: if service_category and service_category != "GENERAL"
           filter = {"service_category": service_category}  (match payload field)
       else filter = None
    4. call vector_store.hybrid_search(
           collection=settings.vector_collection,
           dense_vec=dense_vector,
           sparse_vec=sparse_vector,
           top_k=top_k,
           filter=filter
       ) → list[SearchResult]
    5. return results
- demo fallback: if demo_mode=True → return 3 hardcoded SearchResult objects
    with realistic VPN/SSL content, scores 0.91, 0.87, 0.74

### app/query/reranker.py
- CohereReranker class
- __init__(self, demo_mode: bool = False)
- async rerank(question: str, results: list[SearchResult], top_n: int) -> list[SearchResult]
- Uses cohere SDK: co.rerank(model=settings.COHERE_RERANK_MODEL, query=question, documents=[r.text for r in results], top_n=top_n)
- Map rerank scores back to SearchResult objects
- Return top_n results sorted by rerank score descending
- demo fallback: if demo_mode=True → return results[:top_n] with mock scores 0.95, 0.88, 0.76, 0.61, 0.54
- On cohere error: log warning, return results[:top_n] unmodified (graceful degrade)

### app/query/rag_generator.py
- RAGGenerator class
- async generate(question: str, chunks: list[SearchResult], service_category: str) -> GenerationResult
- GenerationResult Pydantic model:
    answer:     str
    confidence: float   # 0.0–1.0
- System prompt (STRICT GROUNDING — do not soften):
    "You are an IT support assistant. Answer ONLY using the provided context.
     If the answer is not explicitly in the context, say exactly:
     'I don't have information on this topic in our documentation.'
     Do NOT infer. Do NOT use outside knowledge. Quote exact steps from context.
     Cite sources inline as [Page N, PDF_Name]."
- User prompt:
    "Context:\n{numbered chunks with page + pdf_name}\n\nQuestion: {question}\n\nAnswer:"
- Call llm_client.complete(prompt=user_prompt, system=system_prompt)
- Parse confidence from response:
    if response starts with refusal phrase → confidence = 0.1
    elif len(chunks) >= 3 and chunks[0].score > 0.8 → confidence = 0.90
    elif len(chunks) >= 2 and chunks[0].score > 0.6 → confidence = 0.75
    else → confidence = 0.55
- Return GenerationResult(answer=response, confidence=confidence)

### app/query/pipeline.py
- QueryPipeline class
- __init__(self, demo_mode: bool = False)
- async run(request: QueryRequest) -> QueryResponse
- Pipeline steps in order:
    STEP 1: router.detect(request.question) → RouterResult
            if request.service_category provided → override router result
    STEP 2: hybrid_search.search(question, service_category, request.top_k) → list[SearchResult]
            if 0 results → return QueryResponse(refused=True, confidence=0.0, answer="I don't have information on this topic...")
    STEP 3: reranker.rerank(question, results, top_n) → list[SearchResult] (top_n = request.rerank_top_n or settings.RERANK_TOP_N)
    STEP 4: rag_generator.generate(question, reranked_chunks, service_category) → GenerationResult
    STEP 5: confidence gate:
            if generation.confidence < settings.CONFIDENCE_THRESHOLD:
                return QueryResponse(
                    refused=True,
                    answer="I don't have information on this topic in our documentation.",
                    confidence=generation.confidence,
                    confidence_label="refused",
                    sources=[],
                    service_category=service_category
                )
    STEP 6: build SourceChunk list from reranked results:
            pdf_url = f"/pdfs/{chunk.payload['pdf_name']}"
    STEP 7: assign confidence_label:
            >= 0.85 → "high" | >= 0.60 → "moderate" | else → "low"
    STEP 8: return QueryResponse(answer, confidence, confidence_label, sources, service_category, refused=False)
- All steps logged via structlog with timing
- On any error: log, return QueryResponse(refused=True, answer=str(e), confidence=0.0)

## Required .env Variables (additions — ensure in .env.example)
  COHERE_API_KEY=
  COHERE_RERANK_MODEL=rerank-english-v3.0
  CONFIDENCE_THRESHOLD=0.6
  RERANK_TOP_N=5
  MAX_CHUNKS_RETURN=20

## config.py additions (add if not present)
  cohere_api_key:       str = ""
  cohere_rerank_model:  str = "rerank-english-v3.0"
  confidence_threshold: float = 0.6
  rerank_top_n:         int = 5
  max_chunks_return:    int = 20

## Files to Create
  - app/query/__init__.py
  - app/query/router.py
  - app/query/hybrid_search.py
  - app/query/reranker.py
  - app/query/rag_generator.py
  - app/query/pipeline.py
  - tests/unit/test_query.py

## tests/unit/test_query.py — Required Tests
  test_router_demo_vpn:
    QueryRouter(demo_mode=True).detect("how do I reset my VPN password?")
    assert result.service_category == "VPN"
    assert result.intent is non-empty string

  test_router_demo_general:
    QueryRouter(demo_mode=True).detect("hello")
    assert result.service_category == "GENERAL"

  test_hybrid_search_demo:
    HybridSearch(demo_mode=True).search("vpn password", "VPN", top_k=20)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)

  test_reranker_demo:
    CohereReranker(demo_mode=True).rerank("vpn", [mock SearchResult x3], top_n=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score

  test_rag_generator_refusal:
    mock llm_client.complete to return "I don't have information on this topic in our documentation."
    result = RAGGenerator().generate("unknown question", [], "GENERAL")
    assert result.confidence < settings.CONFIDENCE_THRESHOLD

  test_pipeline_demo_success:
    QueryPipeline(demo_mode=True)
    mock rag_generator.generate to return GenerationResult(answer="Open Pulse Secure...", confidence=0.91)
    run(QueryRequest(question="how do I reset my VPN password?"))
    assert response.refused == False
    assert response.confidence >= 0.6
    assert len(response.sources) > 0

  test_pipeline_confidence_gate:
    QueryPipeline(demo_mode=True)
    mock rag_generator.generate to return GenerationResult(answer="...", confidence=0.3)
    run(QueryRequest(question="anything"))
    assert response.refused == True
    assert response.confidence_label == "refused"

## Acceptance Criteria
  [ ] QueryRouter(demo_mode=True).detect("vpn issue") → service_category="VPN"
  [ ] QueryRouter LLM path parses JSON and returns RouterResult
  [ ] HybridSearch(demo_mode=True).search() → 3 SearchResult objects
  [ ] CohereReranker(demo_mode=True).rerank() → results sorted by score desc
  [ ] RAGGenerator system prompt contains "ONLY" and "Do NOT infer"
  [ ] Confidence gate fires correctly when confidence < CONFIDENCE_THRESHOLD
  [ ] QueryResponse.refused=True when gate fires
  [ ] QueryResponse.sources populated with SourceChunk including pdf_url
  [ ] All 7 unit tests pass with mocked dependencies
  [ ] No hardcoded model/DB/API strings outside config.py
  [ ] structlog used everywhere, no print()
  [ ] Cohere error → graceful degrade (no crash)
  [ ] Zero results from search → refused response, no crash

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
- Query Pipeline (router, hybrid search, reranker, RAG generator, pipeline wiring)

## Files Created
- (Foundation + Ingestion files — see roadmap/)
- app/models/query.py (updated)
- app/query/__init__.py
- app/query/router.py
- app/query/hybrid_search.py
- app/query/reranker.py
- app/query/rag_generator.py
- app/query/pipeline.py
- tests/unit/test_query.py

## Progress Tracker
  [x] app/query/router.py — QueryRouter with demo fallback
  [x] app/query/hybrid_search.py — dense + sparse + filter
  [x] app/query/reranker.py — Cohere rerank with graceful degrade
  [x] app/query/rag_generator.py — strict grounding prompt + confidence scoring
  [x] app/query/pipeline.py — all steps wired, confidence gate active
  [x] models/query.py — SourceChunk + QueryResponse verified/updated
  [x] all 7 unit tests pass
  [x] No hardcoded strings
  [x] structlog only, no print()

## Next
QA COMPLETE
```

