"""Document ingestion pipeline.

Pipeline stages:
    1. Route by extension to the right extractor (PDF, DOCX, spreadsheet,
       PPTX, text family, image) and produce a list of ``ParsedPage``s.
    2. Chunk pages (kind-aware: table/row/image kept whole, prose split).
    3. Build a fresh BM25 corpus from the chunk texts; persist its IDF
       snapshot so the query path scores tokens identically.
    4. For each batch of chunks: embed densely via the LLM client (with
       provider failover) and encode sparsely via BM25.
    5. Upsert into the vector store. When the store advertises native
       sparse support we pass ``sparse_vec`` directly; otherwise the
       sparse representation is dropped (legacy stores that do not
       support it) — payload bloat is no longer needed.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime

import structlog
from pydantic import BaseModel

from app.config import get_settings
from app.db.relational import ChunkModel, DocumentModel, get_session_maker
from app.db.vector_store import get_vector_store
from app.ingestion.chunker import ChunkData, chunk_pages
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.router import extract as router_extract
from app.ingestion.sparse import BM25SparseEncoder
from app.llm import client as llm_client
from app.storage.pdf_storage import get_pdf_storage

logger = structlog.get_logger()


class IngestionResult(BaseModel):
    document_id: str
    pdf_name: str
    total_pages: int
    total_chunks: int
    service_name: str
    status: str
    error: str | None = None


class IngestPipeline:
    def __init__(self, demo_mode: bool = False) -> None:
        self.demo_mode = demo_mode
        self.settings = get_settings()

    async def run(
        self,
        pdf_path: str,
        service_name_override: str | None = None,
        pdf_bytes: bytes | None = None,
        content_type: str = "application/pdf",
    ) -> IngestionResult:
        doc_id = str(uuid.uuid4())
        try:
            logger.info("ingestion.start", path=pdf_path)

            ext = os.path.splitext(pdf_path.lower())[1]
            if ext == ".pdf":
                # Preserve the existing PDF diagnostics path so observability
                # (image_pages, ocr_pages, vision_fallback_pages) is unchanged.
                pages, parse_diagnostics = parse_pdf(
                    pdf_path, self.demo_mode, include_diagnostics=True
                )
                logger.info(
                    "ingestion.parser.route",
                    pdf_name=os.path.basename(pdf_path),
                    pdf_type=parse_diagnostics.pdf_type,
                    image_pages=parse_diagnostics.image_pages,
                    text_pages=parse_diagnostics.text_pages,
                    ocr_pages=parse_diagnostics.ocr_pages,
                    vision_fallback_pages=parse_diagnostics.vision_fallback_pages,
                )
            else:
                pages = router_extract(pdf_path, demo_mode=self.demo_mode)
                logger.info(
                    "ingestion.parser.route",
                    pdf_name=os.path.basename(pdf_path),
                    pdf_type=ext.lstrip(".") or "unknown",
                    pages=len(pages),
                )

            if not pages:
                raise ValueError("No pages parsed from document")

            pdf_name = pages[0].pdf_name
            total_pages = pages[0].total_pages
            service_name = service_name_override or pages[0].service_name

            chunks: list[ChunkData] = chunk_pages(pages)
            if service_name_override:
                for c in chunks:
                    c.service_name = service_name_override

            total_chunks = len(chunks)
            if total_chunks == 0:
                raise ValueError("No chunks generated")

            sparse_encoder = BM25SparseEncoder()
            sparse_encoder.fit([c.text for c in chunks])
            try:
                sparse_encoder.save(self.settings.SPARSE_INDEX_DIR)
            except Exception as exc:
                logger.warning("ingestion.sparse_persist_failed", error=str(exc))

            vector_store = get_vector_store()
            store_supports_sparse = bool(getattr(vector_store, "supports_sparse", False))
            batch_size = self.settings.EMBED_BATCH_SIZE

            for i in range(0, total_chunks, batch_size):
                batch = chunks[i : i + batch_size]
                texts = [c.text for c in batch]

                dense_vectors = await llm_client.embed_documents(texts)
                sparse_vectors = sparse_encoder.encode_batch(texts)

                for chunk, dense_vec, sparse_vec in zip(batch, dense_vectors, sparse_vectors, strict=False):
                    payload = chunk.model_dump()
                    payload["document_id"] = doc_id

                    if store_supports_sparse:
                        await vector_store.upsert(
                            collection=self.settings.vector_collection,
                            id=chunk.chunk_id,
                            vector=dense_vec,
                            payload=payload,
                            sparse_vector=sparse_vec,
                        )
                    else:
                        await vector_store.upsert(
                            collection=self.settings.vector_collection,
                            id=chunk.chunk_id,
                            vector=dense_vec,
                            payload=payload,
                        )

            session_maker = get_session_maker()
            async with session_maker() as session:
                async with session.begin():
                    session.add(
                        DocumentModel(
                            id=doc_id,
                            filename=pdf_name,
                            content="",
                            metadata_={
                                "service_name": service_name,
                                "total_pages": total_pages,
                                "total_chunks": total_chunks,
                            },
                            created_at=datetime.now(),
                        )
                    )

                    for c in chunks:
                        session.add(
                            ChunkModel(
                                id=c.chunk_id,
                                document_id=doc_id,
                                text=c.text,
                                metadata_={
                                    "page_number": c.page_number,
                                    "chunk_index": c.chunk_index,
                                    "section_title": c.section_title,
                                },
                            )
                        )

            if pdf_bytes is not None:
                storage = get_pdf_storage()
                await storage.save_pdf(
                    document_id=doc_id,
                    filename=pdf_name,
                    content_type=content_type or "application/pdf",
                    pdf_bytes=pdf_bytes,
                )

            logger.info("ingestion.complete", document_id=doc_id, chunks=total_chunks)

            return IngestionResult(
                document_id=doc_id,
                pdf_name=pdf_name,
                total_pages=total_pages,
                total_chunks=total_chunks,
                service_name=service_name,
                status="success",
            )

        except Exception as e:
            logger.error("ingestion.failed", error=str(e), path=pdf_path)
            return IngestionResult(
                document_id=doc_id,
                pdf_name=os.path.basename(pdf_path),
                total_pages=0,
                total_chunks=0,
                service_name=service_name_override or "Unknown",
                status="failed",
                error=str(e),
            )
