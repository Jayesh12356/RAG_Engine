import structlog
from typing import List, Optional
from app.models.query import SearchResult
from app.db.vector_store import get_vector_store
from app.llm import client as llm_client
from app.config import get_settings
from app.ingestion.sparse import BM25SparseEncoder

logger = structlog.get_logger(__name__)
settings = get_settings()

class HybridSearch:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        if not demo_mode:
            self.vector_store = get_vector_store()

    async def search(self, question: str, service_category: Optional[str], top_k: int) -> List[SearchResult]:
        if self.demo_mode:
            logger.info("hybrid_search_demo", question=question, category=service_category)
            return [
                SearchResult(
                    chunk_id="demo_chunk_1",
                    document_id="demo_doc_1",
                    text="To reset your VPN password, go to the portal and click 'Reset'.",
                    score=0.91,
                    metadata={"pdf_name": "vpn_guide.pdf", "page_number": 1, "section_title": "VPN Reset"}
                ),
                SearchResult(
                    chunk_id="demo_chunk_2",
                    document_id="demo_doc_1",
                    text="VPN connections require two-factor authentication via the Duo app.",
                    score=0.87,
                    metadata={"pdf_name": "vpn_guide.pdf", "page_number": 2, "section_title": "Authentication"}
                ),
                SearchResult(
                    chunk_id="demo_chunk_3",
                    document_id="demo_doc_2",
                    text="If SSL certificate errors occur, ensure your VPN is active before accessing internal sites.",
                    score=0.74,
                    metadata={"pdf_name": "ssl_troubleshooting.pdf", "page_number": 5, "section_title": "VPN & SSL"}
                )
            ]

        try:
            logger.info("hybrid_search_embed_start", question=question)
            dense_vectors = await llm_client.embed([question])
            dense_vector = dense_vectors[0]

            sparse_vector = None
            if getattr(self.vector_store, "supports_sparse", False):
                logger.info("hybrid_search_sparse_start")
                sparse_encoder = BM25SparseEncoder()
                sparse_encoder.fit([question])
                sparse_vector_raw = sparse_encoder.encode(question)
                sparse_vector = {str(k): v for k, v in sparse_vector_raw.items()}

            filter_dict = None
            if service_category and service_category.upper() != "GENERAL":
                # The payload field is 'service_name', not 'service_category'
                # We do a case-insensitive search by using the exact category
                filter_dict = {"service_name": service_category}

            logger.info("hybrid_search_vector_store_start", filter=filter_dict)
            results = await self.vector_store.hybrid_search(
                collection=settings.vector_collection,
                dense_vec=dense_vector,
                sparse_vec=sparse_vector,
                top_k=top_k,
                filter=filter_dict
            )

            if filter_dict and len(results) < 3:
                logger.warning("search.filter.fallback", original_results=len(results), retrying_unfiltered=True)
                unfiltered_results = await self.vector_store.hybrid_search(
                    collection=settings.vector_collection,
                    dense_vec=dense_vector,
                    sparse_vec=sparse_vector,
                    top_k=top_k,
                    filter=None
                )
                if len(unfiltered_results) > len(results):
                    results = unfiltered_results

            logger.info("hybrid_search_success", hits=len(results))
            return results

        except Exception as e:
            logger.error("hybrid_search_error", error=str(e))
            return []
