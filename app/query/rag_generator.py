"""RAG answer generation, prompting and confidence scoring.

Notable design choices:
- ``_sanitize_context_text`` only normalises whitespace; non-ASCII characters
  are preserved (multilingual queries / unicode bullets / diacritics).
- ``_score_confidence`` blends top reranker score, top-second margin, answer
  ↔ context Jaccard overlap and refusal-phrase detection. Buckets are aligned
  with ``settings.CONFIDENCE_THRESHOLD`` so the gate stays predictable.
- ``_extractive_fallback_answer`` requires at least
  ``MIN_FALLBACK_OVERLAP`` token-set coverage with the question; otherwise it
  refuses cleanly instead of stitching irrelevant text together.
- The system prompt accepts a ``service_category`` so the router's category
  decision actually shapes the answer style.
"""
from __future__ import annotations

import re

import structlog
from pydantic import BaseModel

from app.config import get_settings
from app.llm import client as llm_client
from app.llm.image_client import post_process_answer as _post_process_images
from app.models.query import Citation, SearchResult

logger = structlog.get_logger(__name__)
settings = get_settings()


class GenerationResult(BaseModel):
    answer: str
    confidence: float
    citations: list[Citation] = []


REFUSAL_PHRASE = "I don't have information about this in the provided documents."

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_UNCERTAIN_RE = re.compile(
    r"\b(maybe|might|possibly|likely|assume|guess|unclear|unsure)\b",
    flags=re.IGNORECASE,
)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


# ──────────────────────────────────────────────────────────────────────────
# Confidence
# ──────────────────────────────────────────────────────────────────────────
def _score_confidence(answer: str, chunks: list) -> float:
    """Calibrated confidence in ``[0.10, 0.98]``.

    Components (each clipped to [0,1]):
      - overlap:        token Jaccard between answer and combined context
                        (most important: a grounded answer reuses context tokens)
      - top_score:      reranker top-1 similarity (capped softly so a corpus
                        whose absolute reranker scores cluster low — CVs, CSV
                        exports, papers — does not get penalised twice)
      - margin:         (top - second) signal
      - uncertainty:    penalty for hedging language

    Refusal phrase short-circuits to a low confidence so the gate refuses.
    """
    if REFUSAL_PHRASE.lower() in (answer or "").lower():
        return 0.10
    if not chunks:
        return 0.45 if answer else 0.10

    scores = sorted((float(c.score or 0.0) for c in chunks), reverse=True)
    raw_top = scores[0]
    raw_second = scores[1] if len(scores) > 1 else 0.0
    # Soft re-scaling: many rerankers (Cohere v3) return absolute scores in
    # the 0.001-0.10 range for short or domain-mismatched chunks, even when
    # the *relative* ranking is correct. We keep the raw value for the
    # margin signal (which is comparative and so already calibrated) but
    # boost the absolute "top" component using a sqrt so the confidence
    # blend is dominated by how well the answer actually matches the
    # context, not by the reranker's idiosyncratic absolute scale.
    top = max(0.0, min(1.0, raw_top**0.5)) if raw_top < 0.25 else max(0.0, min(1.0, raw_top))
    margin = max(0.0, min(1.0, raw_top - raw_second))

    answer_tokens = _tokens(answer)
    context_tokens: set[str] = set()
    for c in chunks[:5]:
        context_tokens |= _tokens(getattr(c, "text", ""))
    overlap = _jaccard(answer_tokens, context_tokens)

    has_uncertain = bool(_UNCERTAIN_RE.search(answer or ""))
    answer_len = len(_TOKEN_RE.findall(answer or ""))

    base = (
        0.50 * overlap
        + 0.25 * top
        + 0.20 * margin
        + 0.05 * min(1.0, answer_len / 60.0)
    )
    base = 0.30 + 0.65 * base  # squash into a sensible operating range
    if has_uncertain:
        base -= 0.10
    if answer_len < 4:
        base -= 0.10
    return max(0.10, min(0.98, round(base, 4)))


# ──────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────
_BASE_SYSTEM_PROMPT = (
    "You are a precise document-grounded assistant. Answer ONLY from the provided context.\n"
    "Documents may be of any type (CVs/resumes, papers, manuals, IT runbooks, financial sheets, "
    "tabular CSV/Excel exports, presentations, web pages, code, JSON exports, scanned images). "
    "Treat every document equally and answer truthfully from it.\n\n"
    "GROUNDING RULES:\n"
    "• Use only facts present in context. Never invent steps, settings, paths, names, dates, numbers, or product details.\n"
    "• If context partially answers, state only the confirmed part and call out what is missing.\n"
    "• If the answer is absent, ambiguous, or unsupported, refuse.\n"
    "• Numerical values, identifiers, code, URLs, file paths must be quoted exactly as they appear in context.\n"
    "• MULTI-PART QUESTIONS: When the question asks for two or more things (e.g. 'X AND Y', 'list X and Y'), "
    "you MUST answer every part that the context supports. Use clear sub-headings or separate bullet groups so each "
    "part is visibly addressed. If the context supports one part but not another, answer the supported part and "
    "explicitly say the other part is not in the documents.\n"
    "• PII PRECISION: For specific personal identifiers (home address, full street address, exact salary, "
    "date of birth, phone number, ID/account number) only answer if the EXACT, COMPLETE value is in context. "
    "A city, town, state, region, or country alone is NOT a 'home address' — a home address is a full street "
    "address with house/flat number, street, area, city, state, postal/PIN code. A job title is NOT a salary. "
    "An email is NOT a phone number. If only a partial value (city only, year only, last-4-digits only) is "
    "available, refuse with the standard refusal phrase rather than presenting the partial as the full answer.\n\n"
    "FORMAT RULES — follow strictly:\n"
    "• Identity / definition questions ('what is', 'who is'): 1–2 sentence answer. Bold the key term or name on first mention.\n"
    "• Lists ('benefits', 'types', 'limitations', 'skills', 'projects', 'companies'): Bullet list, no intro sentence.\n"
    "• Comparisons ('compare', 'difference', 'vs'): GFM markdown table ONLY. No text outside the table.\n"
    "• Tabular data requests ('list with columns', 'tabulate', rows of values, 'show me the table', "
    "'top N by X'): GFM markdown table with a header row, alignment row, and one row per record. "
    "Use `tabular-nums`-friendly formatting (right-align numbers conceptually; do not invent units).\n"
    "• Code, configs, JSON, SQL, shell, paths in answers: ALWAYS wrap in fenced code blocks with the language tag "
    "(```python, ```sql, ```json, ```bash, ```yaml). Never inline more than ~80 chars of code.\n"
    "• Step-by-step ('how does', 'steps', 'process', 'workflow'): Numbered list (1. 2. 3.).\n"
    "• Math / formulas in context: render with `$...$` for inline and `$$...$$` for block math (LaTeX).\n"
    "• Yes/No questions ('does', 'is', 'can'): Start with 'Yes.' or 'No.' then one brief reason.\n"
    "• Scenario/recommendation ('which', 'best', 'recommend'): State recommendation first, then 2–3 bullet justifications.\n"
    "• Summaries ('summarize', 'overview', 'tl;dr'): 3-bullet structured summary unless a length is specified.\n\n"
    "STYLE:\n"
    "• Keep it clean and direct.\n"
    "• For SHORT expected answers: maximum 2 sentences.\n"
    "• For LONG expected answers: complete but compact structure, no filler.\n"
    "• Use Markdown only when it improves clarity (lists, tables, code, math). Plain prose otherwise.\n\n"
    "STRICT BANS:\n"
    "• NO headers (##), NO 'Introduction', NO 'Conclusion', NO 'In summary'\n"
    "• NO preamble ('Based on the context', 'According to the document')\n"
    "• NO citations or references like [Page N] or [Source]\n"
    "• NO filler. Answer the question directly, nothing more.\n"
    "• NO speculation, NO outside knowledge, NO answering from prior conversation memory if the new context does not support it.\n\n"
    f"If the answer is NOT in the context, reply EXACTLY: '{REFUSAL_PHRASE}'"
)


# Visual-mode add-on. Appended to the base prompt only when the active LLM is
# vision-capable (per ``settings.llm_is_visual_capable``). It unlocks Mermaid
# diagrams, Recharts JSON quantitative charts, and the image-request hook
# (post-processed server-side into a real image when an image API key exists).
_VISUAL_MODE_ADDENDUM = (
    "\n\nVISUAL-MODE EXTRAS (only use when the data clearly justifies it — never decoratively):\n"
    "• MERMAID for relationships, flows, sequences, state machines, ER diagrams, timelines and "
    "architecture/dependency graphs grounded in context. Emit a fenced ```mermaid block. "
    "Use simple, valid mermaid syntax: flowchart LR/TB, sequenceDiagram, classDiagram, erDiagram, "
    "stateDiagram-v2, pie. Do NOT use angle brackets or HTML entities in node labels. Prefer "
    "camelCase node IDs (no spaces). Wrap labels in quotes when they contain parentheses or colons.\n"
    "• CHARTS for quantitative data drawn directly from numeric context (spreadsheet/CSV rows, "
    "tables in PDFs, JSON arrays of numbers). Emit a fenced ```chart block whose body is STRICT "
    "JSON with this schema:\n"
    "    {\n"
    "      \"type\": \"bar\" | \"line\" | \"pie\" | \"area\",\n"
    "      \"title\": \"<short title>\",\n"
    "      \"xKey\": \"<column-name-for-x>\",\n"
    "      \"yKey\": \"<column-name-for-y>\" | [\"<col1>\", \"<col2>\", ...],\n"
    "      \"data\":  [{\"<xKey>\": <value>, \"<yKey>\": <value>}, ...]\n"
    "    }\n"
    "  Rules: every numeric value must be present in the context (no extrapolation). Keep ≤ 30 data "
    "points. Do not emit a chart for prose, definitions, or single-row answers — render those as text "
    "or a small table. Always include `xKey`, `yKey`, `title`. Use `pie` only when the data sums to a "
    "meaningful whole (use {\"name\": str, \"value\": number} per slice).\n"
    "• IMAGE GENERATION: only when the user explicitly asks for an illustration / diagram / "
    "visualisation that cannot be expressed as a chart or mermaid (e.g. 'draw a picture of …'). "
    "Emit a single fenced ```image-request block whose body is STRICT JSON: "
    "`{\"prompt\": \"<concise visual description grounded in context>\", \"alt\": \"<short alt text>\"}`. "
    "Do not generate images decoratively. The server replaces the block with a real image inline.\n"
    "• You may combine these with regular markdown (a chart followed by a 1-sentence interpretation, a "
    "mermaid diagram followed by a numbered list of the steps it depicts), but every visual must be "
    "directly supported by the provided context."
)

# Backwards-compatible export — many tests and callers import ``SYSTEM_PROMPT``.
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT


def build_system_prompt(service_category: str | None) -> str:
    """Build the system prompt, auto-extending it with visual-mode rules when
    the configured LLM is vision-capable (per ``settings.llm_is_visual_capable``).

    The deployer never sets a flag — drop a vision model in ``OPENAI_MODEL`` /
    ``OPENROUTER_MODEL`` / ``GROQ_MODEL`` and the prompt grows. Drop a small
    text-only model and the prompt stays compact and chart-free.
    """
    visual = get_settings().llm_is_visual_capable
    base = _BASE_SYSTEM_PROMPT + (_VISUAL_MODE_ADDENDUM if visual else "")
    if not service_category or service_category.upper() == "GENERAL":
        return base
    cat = service_category.upper()
    addendum = (
        "\n\nDOMAIN HINT:\n"
        f"• The user's question is most likely about the '{cat}' service.\n"
        "• Prefer terminology and steps from this domain when context supports it.\n"
        "• Do NOT use this hint as evidence — only the provided context counts."
    )
    return base + addendum


# ──────────────────────────────────────────────────────────────────────────
# Output post-processing
# ──────────────────────────────────────────────────────────────────────────
def _clean_answer(answer: str) -> str:
    """Strip preamble/summary noise, headers, and stray citation tags."""
    answer = re.sub(
        r"^(?:Based on the (?:provided )?context,?\s*"
        r"|According to the (?:provided )?(?:context|document|text),?\s*"
        r"|From the (?:provided )?context,?\s*"
        r"|The (?:provided )?context (?:states|mentions|indicates) that\s*)",
        "",
        answer,
        flags=re.IGNORECASE,
    )
    answer = re.sub(
        r"\n+(?:In summary|In conclusion|To summarize|Overall|To conclude)[,:].*$",
        "",
        answer,
        flags=re.IGNORECASE | re.DOTALL,
    )
    answer = re.sub(r"^#{1,4}\s+.*$", "", answer, flags=re.MULTILINE)
    answer = re.sub(r"\[(?:Page|Source|Ref)\s*\d*[^]]*\]", "", answer)
    answer = re.sub(r"\n{3,}", "\n\n", answer)
    return answer.strip()


def _sanitize_context_text(text: str) -> str:
    """Normalise whitespace; preserve unicode (no ASCII stripping)."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"^[\W_]+", "", cleaned)
    return cleaned


def _filter_chunks_for_quality(chunks: list[SearchResult]) -> list[SearchResult]:
    out: list[SearchResult] = []
    seen: set[str] = set()
    for c in chunks:
        txt = _sanitize_context_text(c.text)
        if len(txt.split()) < 8:
            continue
        key = txt[:180].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out or list(chunks[:3])


def _detect_response_mode(question: str) -> str:
    q = (question or "").lower().strip()
    short_starts = (
        "what is", "who is", "is ", "can ", "does ", "do ", "when ", "where ", "which is",
    )
    long_markers = (
        "how to", "how do", "how does", "steps", "compare", "difference",
        "best practice", "design", "architecture", "troubleshoot", "workflow",
    )
    if any(m in q for m in long_markers) or len(q.split()) > 14:
        return "LONG"
    if any(q.startswith(s) for s in short_starts):
        return "SHORT"
    return "LONG"


def build_user_prompt(question: str, chunks: list[SearchResult], history_block: str = "") -> str:
    quality_chunks = _filter_chunks_for_quality(chunks)
    context_blocks = [_sanitize_context_text(chunk.text) for chunk in quality_chunks]
    context_text = "\n\n---\n\n".join(context_blocks)
    response_mode = _detect_response_mode(question)
    mode_instruction = (
        "Expected answer length: SHORT (max 2 sentences)."
        if response_mode == "SHORT"
        else "Expected answer length: LONG (structured and detailed, but compact)."
    )
    history = f"{history_block}\n" if history_block else ""
    return (
        f"{history}Context:\n{context_text}\n\n"
        f"Question: {question}\n"
        f"{mode_instruction}\n\n"
        "Answer:"
    )


# ──────────────────────────────────────────────────────────────────────────
# Extractive fallback (LLM down)
# ──────────────────────────────────────────────────────────────────────────
def _extractive_fallback_answer(question: str, chunks: list[SearchResult]) -> str:
    if not chunks:
        return REFUSAL_PHRASE
    q_tokens = _tokens(question)
    if not q_tokens:
        return REFUSAL_PHRASE

    top_chunks = [_sanitize_context_text(c.text) for c in chunks[:5] if c.text and c.text.strip()]
    if not top_chunks:
        return REFUSAL_PHRASE

    scored: list[tuple[float, str]] = []
    for text in top_chunks:
        for sent in re.split(r"(?<=[.!?])\s+", text):
            s = sent.strip()
            if len(s.split()) < 6:
                continue
            s_tokens = _tokens(s)
            overlap = len(q_tokens & s_tokens) / max(1, len(q_tokens))
            if overlap > 0:
                scored.append((overlap, s))
    scored.sort(key=lambda x: x[0], reverse=True)

    settings_local = get_settings()
    threshold = settings_local.MIN_FALLBACK_OVERLAP
    qualifying = [s for ov, s in scored if ov >= threshold]
    if not qualifying:
        return REFUSAL_PHRASE
    best = qualifying[:3]

    q_lower = (question or "").lower()
    if any(k in q_lower for k in ("compare", "difference", "vs")) and len(best) >= 2:
        a = best[0][:220]
        b = best[1][:220]
        return f"- **Point 1:** {a}\n- **Point 2:** {b}"
    if any(k in q_lower for k in ("how", "steps", "process")):
        return "\n".join(f"{i}. {t[:220]}" for i, t in enumerate(best, 1))
    if len(question.split()) <= 8:
        return best[0][:260]
    return "\n".join(f"- {t[:220]}" for t in best)


# ──────────────────────────────────────────────────────────────────────────
# Citations
# ──────────────────────────────────────────────────────────────────────────
def build_citations(chunks: list[SearchResult]) -> list[Citation]:
    citations: list[Citation] = []
    for c in chunks:
        meta = getattr(c, "metadata", None) or {}
        citations.append(
            Citation(
                chunk_id=getattr(c, "chunk_id", "") or meta.get("chunk_id", ""),
                document_id=getattr(c, "document_id", "") or meta.get("document_id", ""),
                pdf_name=meta.get("pdf_name", ""),
                page_number=int(meta.get("page_number", 0) or 0),
                section_title=meta.get("section_title", ""),
                score=float(getattr(c, "score", 0.0) or 0.0),
            )
        )
    return citations


# ──────────────────────────────────────────────────────────────────────────
# Generator
# ──────────────────────────────────────────────────────────────────────────
class RAGGenerator:
    async def generate(
        self,
        question: str,
        chunks: list[SearchResult],
        service_category: str | None = None,
    ) -> GenerationResult:
        filtered_chunks = _filter_chunks_for_quality(chunks)
        user_prompt = build_user_prompt(question, filtered_chunks)
        system_prompt = build_system_prompt(service_category)

        try:
            logger.info(
                "rag_generate_start",
                question=question,
                chunks_sent=len(filtered_chunks),
                service_category=service_category,
            )

            answer = await llm_client.complete(prompt=user_prompt, system=system_prompt)
            answer = (answer or "").strip()

            if not answer:
                logger.warning("rag_empty_response_retry", question=question)
                answer = await llm_client.complete(prompt=user_prompt, system=system_prompt)
                answer = (answer or "").strip()

            answer = _clean_answer(answer)
            answer = _post_process_images(answer)
            confidence = _score_confidence(answer, filtered_chunks)

            logger.info(
                "rag_generate_success",
                confidence=confidence,
                answer_len=len(answer),
            )
            return GenerationResult(
                answer=answer,
                confidence=confidence,
                citations=build_citations(filtered_chunks),
            )

        except Exception as e:
            logger.error("rag_generate_error", error=str(e))
            fallback_answer = _extractive_fallback_answer(question, chunks)
            if fallback_answer != REFUSAL_PHRASE:
                return GenerationResult(
                    answer=fallback_answer,
                    confidence=get_settings().EXTRACTIVE_FALLBACK_CONFIDENCE,
                    citations=build_citations(filtered_chunks),
                )
            return GenerationResult(answer=REFUSAL_PHRASE, confidence=0.10, citations=[])
