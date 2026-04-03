import re
import structlog
from pydantic import BaseModel
from typing import List
from app.models.query import SearchResult
from app.llm import client as llm_client
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class GenerationResult(BaseModel):
    answer: str
    confidence: float


REFUSAL_PHRASE = "I don't have information on this topic in our documentation."


def _score_confidence(answer: str, chunks: list) -> float:
    """Score confidence based on refusal detection + reranker scores."""
    if REFUSAL_PHRASE in answer:
        return 0.10
    if not chunks:
        return 0.50

    best = max(c.score for c in chunks)
    answer_len = len(answer.split())
    has_uncertain_language = bool(re.search(r"\b(maybe|might|possibly|likely|assume|guess)\b", answer, flags=re.IGNORECASE))
    if has_uncertain_language:
        return 0.45

    if best >= 0.85 and len(chunks) >= 3:
        base = 0.95
    elif best >= 0.75 and len(chunks) >= 2:
        base = 0.90
    elif best >= 0.60:
        base = 0.85
    elif best >= 0.40:
        base = 0.75
    elif len(chunks) >= 1:
        base = 0.65
    else:
        base = 0.55
    if answer_len < 4:
        base -= 0.10
    return max(0.10, min(0.98, base))


SYSTEM_PROMPT = (
    "You are an IT helpdesk assistant. Answer ONLY from the provided context.\n\n"
    "GROUNDING RULES:\n"
    "• Use only facts present in context. Never invent steps, settings, paths, or product names.\n"
    "• If context partially answers, state only the confirmed part and call out what is missing.\n"
    "• If the answer is absent, ambiguous, or unsupported, refuse.\n\n"
    "FORMAT RULES — follow strictly:\n"
    "• Definition questions ('what is'): 1–2 sentence answer. Bold the key term.\n"
    "• Benefit/feature lists ('benefits', 'types', 'limitations'): Bullet list, no intro sentence.\n"
    "• Comparisons ('compare', 'difference', 'vs'): Markdown table ONLY. No text outside the table.\n"
    "• Step-by-step ('how does', 'steps'): Numbered list (1. 2. 3.).\n"
    "• Yes/No questions ('does', 'is', 'can'): Start with 'Yes.' or 'No.' then one brief reason.\n"
    "• Scenario/recommendation ('which', 'best', 'design'): State recommendation first, then 2–3 bullet justifications.\n\n"
    "STYLE:\n"
    "• Keep it clean and direct.\n"
    "• For SHORT expected answers: maximum 2 sentences.\n"
    "• For LONG expected answers: complete but compact structure, no filler.\n\n"
    "STRICT BANS:\n"
    "• NO headers (##), NO 'Introduction', NO 'Conclusion', NO 'In summary'\n"
    "• NO preamble ('Based on the context', 'According to the document')\n"
    "• NO citations or references like [Page N] or [Source]\n"
    "• NO filler. Answer the question directly, nothing more.\n\n"
    f"If the answer is NOT in the context, reply EXACTLY: '{REFUSAL_PHRASE}'"
)


def _clean_answer(answer: str) -> str:
    """Post-process LLM output to strip noise and enforce clean formatting."""
    # Strip common LLM preambles
    answer = re.sub(
        r'^(?:Based on the (?:provided )?context,?\s*|According to the (?:provided )?(?:context|document|text),?\s*|'
        r'From the (?:provided )?context,?\s*|The (?:provided )?context (?:states|mentions|indicates) that\s*)',
        '', answer, flags=re.IGNORECASE
    )

    # Strip trailing summary/conclusion fluff
    answer = re.sub(
        r'\n+(?:In summary|In conclusion|To summarize|Overall|To conclude)[,:].*$',
        '', answer, flags=re.IGNORECASE | re.DOTALL
    )

    # Strip markdown headers
    answer = re.sub(r'^#{1,4}\s+.*$', '', answer, flags=re.MULTILINE)

    # Strip citation artifacts like [Page 1, VPN.pdf] or [Source 1]
    answer = re.sub(r'\[(?:Page|Source|Ref)\s*\d*[^]]*\]', '', answer)

    # Collapse excessive blank lines
    answer = re.sub(r'\n{3,}', '\n\n', answer)

    return answer.strip()


def _extractive_fallback_answer(question: str, chunks: List[SearchResult]) -> str:
    if not chunks:
        return REFUSAL_PHRASE
    q = question.lower()
    top = [_sanitize_context_text(c.text) for c in chunks[:5] if c.text and c.text.strip()]
    if not top:
        return REFUSAL_PHRASE
    q_tokens = set(re.findall(r"[a-z0-9]+", q))
    scored_sentences: list[tuple[float, str]] = []
    for text in top:
        for sent in re.split(r"(?<=[.!?])\s+", text):
            s = sent.strip()
            if len(s.split()) < 6:
                continue
            s_tokens = set(re.findall(r"[a-z0-9]+", s.lower()))
            overlap = len(q_tokens & s_tokens)
            score = overlap / max(1, len(q_tokens))
            if score > 0:
                scored_sentences.append((score, s))
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    best = [s for _, s in scored_sentences[:3]] or top[:3]
    if any(k in q for k in ("compare", "difference", "vs")) and len(best) >= 2:
        a = best[0][:220]
        b = best[1][:220]
        return f"- **Point 1:** {a}\n- **Point 2:** {b}"
    if any(k in q for k in ("how", "steps", "process")):
        lines = []
        for i, t in enumerate(best, 1):
            lines.append(f"{i}. {t[:220]}")
        return "\n".join(lines)
    if len(question.split()) <= 8:
        return best[0][:260]
    bullets = [f"- {t[:220]}" for t in best]
    return "\n".join(bullets)


def _sanitize_context_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^[\W_]+", "", cleaned)
    cleaned = cleaned.encode("ascii", errors="ignore").decode("ascii")
    return cleaned


def _filter_chunks_for_quality(chunks: List[SearchResult]) -> List[SearchResult]:
    out: List[SearchResult] = []
    seen = set()
    for c in chunks:
        txt = _sanitize_context_text(c.text)
        # Skip very short/heading-like fragments that degrade answer quality.
        if len(txt.split()) < 8:
            continue
        key = txt[:180].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out or chunks[:3]


def _detect_response_mode(question: str) -> str:
    q = question.lower().strip()
    short_starts = (
        "what is", "who is", "is ", "can ", "does ", "do ", "when ", "where ", "which is"
    )
    long_markers = (
        "how to", "how do", "how does", "steps", "compare", "difference",
        "best practice", "design", "architecture", "troubleshoot", "workflow"
    )
    if any(m in q for m in long_markers) or len(q.split()) > 14:
        return "LONG"
    if any(q.startswith(s) for s in short_starts):
        return "SHORT"
    return "LONG"


def build_user_prompt(question: str, chunks: List[SearchResult], history_block: str = "") -> str:
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


class RAGGenerator:
    async def generate(self, question: str, chunks: List[SearchResult],
                       service_category: str) -> GenerationResult:
        filtered_chunks = _filter_chunks_for_quality(chunks)
        user_prompt = build_user_prompt(question, filtered_chunks)

        try:
            logger.info("rag_generate_start", question=question,
                        chunks_sent=len(chunks))

            answer = await llm_client.complete(
                prompt=user_prompt, system=SYSTEM_PROMPT
            )
            answer = answer.strip()

            if not answer:
                logger.warning("rag_empty_response_retry", question=question)
                answer = await llm_client.complete(
                    prompt=user_prompt, system=SYSTEM_PROMPT
                )
                answer = answer.strip()

            answer = _clean_answer(answer)
            confidence = _score_confidence(answer, filtered_chunks)

            logger.info("rag_generate_success", confidence=confidence,
                        answer_len=len(answer))
            return GenerationResult(answer=answer, confidence=confidence)

        except Exception as e:
            logger.error("rag_generate_error", error=str(e))
            fallback_answer = _extractive_fallback_answer(question, chunks)
            if fallback_answer != REFUSAL_PHRASE:
                return GenerationResult(
                    answer=fallback_answer,
                    confidence=0.58
                )
            return GenerationResult(
                answer=REFUSAL_PHRASE,
                confidence=0.0
            )
