import structlog
import cohere
from typing import List
import re
from app.models.query import SearchResult
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))

class CohereReranker:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        if not demo_mode:
            self.client = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)

    async def rerank(self, question: str, results: List[SearchResult], top_n: int) -> List[SearchResult]:
        if not results:
            return []

        if self.demo_mode:
            logger.info("rerank_demo_mode", q=question, docs=len(results))
            mock_scores = [0.95, 0.88, 0.76, 0.61, 0.54]
            out = results[:top_n]
            for i, res in enumerate(out):
                res.score = mock_scores[i] if i < len(mock_scores) else (0.5 - i * 0.01)
            return sorted(out, key=lambda x: x.score, reverse=True)

        try:
            logger.info("rerank_start", docs=len(results), top_n=top_n)
            texts = [r.text for r in results]
            
            response = await self.client.rerank(
                model=settings.COHERE_RERANK_MODEL,
                query=question,
                documents=texts,
                top_n=top_n
            )

            reranked_results = []
            for item in response.results:
                original_result = results[item.index]
                # Update score
                original_result.score = item.relevance_score
                reranked_results.append(original_result)

            logger.info("rerank_success", returned=len(reranked_results))
            return reranked_results
            
        except Exception as e:
            logger.warning("rerank_error_fallback", error=str(e))
            # Accuracy-first local fallback: lexical overlap + original score
            q_tokens = _tokenize(question)
            rescored = []
            for r in results:
                t_tokens = _tokenize(r.text)
                overlap = len(q_tokens & t_tokens)
                coverage = overlap / max(1, len(q_tokens))
                r.score = (0.65 * float(r.score)) + (0.35 * coverage)
                rescored.append(r)
            rescored.sort(key=lambda x: x.score, reverse=True)
            return rescored[:top_n]
