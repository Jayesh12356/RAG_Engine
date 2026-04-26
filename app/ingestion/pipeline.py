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
from app.db.relational import (
    ChunkModel,
    DocumentModel,
    get_session_maker,
    update_ingestion_task,
)
from app.db.vector_store import get_vector_store
from app.ingestion.chunker import ChunkData, chunk_pages
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.redact import is_redaction_enabled, redact_chunks
from app.ingestion.router import extract as router_extract
from app.ingestion.sparse import BM25SparseEncoder
from app.ingestion.summarizer import summarize_document
from app.llm import client as llm_client
from app.observability.webhooks import fire_and_forget
from app.query.cache import bump_corpus_version
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

    async def _progress(
        self,
        task_id: str | None,
        *,
        stage: str,
        progress: int,
        status: str = "running",
        message: str | None = None,
        document_id: str | None = None,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        error: str | None = None,
    ) -> None:
        """Emit a progress patch to the ``ingestion_tasks`` row.

        Silently no-ops when ``task_id`` is missing (foreground ingest)
        or when the relational write fails (e.g. demo mode without a
        configured DB) so the pipeline keeps running.
        """
        if not task_id:
            return
        try:
            await update_ingestion_task(
                task_id,
                stage=stage,
                status=status,
                progress=progress,
                document_id=document_id,
                total_chunks=total_chunks,
                processed_chunks=processed_chunks,
                message=message,
                error=error,
            )
        except Exception as exc:
            logger.warning("ingestion.progress_update_failed", error=str(exc))

    async def _next_document_version(self, filename: str) -> int:
        """Return the next ``documents.version`` value for ``filename``.

        Older copies are kept (the new chunks live alongside them in the
        vector store) so historical questions stay answerable, but
        retrieval can prefer the most recent revision.

        Falls back to ``1`` whenever the relational layer is unavailable
        (e.g. demo mode without a configured DB) so ingestion never fails
        for a versioning lookup.
        """
        try:
            from sqlalchemy import func, select  # local import keeps cold-start light

            session_maker = get_session_maker()
        except Exception:
            return 1
        try:
            async with session_maker() as session:
                stmt = select(func.max(DocumentModel.version)).where(
                    DocumentModel.filename == filename
                )
                result = await session.execute(stmt)
                current = result.scalar()
        except Exception as exc:
            logger.debug("ingestion.version_lookup_failed", error=str(exc))
            return 1
        if current is None:
            return 1
        try:
            return int(current) + 1
        except (TypeError, ValueError):
            return 1

    async def run(
        self,
        pdf_path: str,
        service_name_override: str | None = None,
        pdf_bytes: bytes | None = None,
        content_type: str = "application/pdf",
        task_id: str | None = None,
        original_filename: str | None = None,
    ) -> IngestionResult:
        doc_id = str(uuid.uuid4())
        try:
            logger.info("ingestion.start", path=pdf_path)
            await self._progress(
                task_id,
                stage="parsing",
                progress=5,
                document_id=doc_id,
                message="Parsing document",
            )

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

            # The /ingest route stores the upload at ``/tmp/{task_id}_{filename}``
            # so ``pages[0].pdf_name`` would otherwise change on every upload and
            # break document versioning + de-duplication. When the route passes
            # the original filename we promote it to the canonical pdf_name and
            # rewrite the parsed pages + chunks so all downstream citations
            # show the user-facing name rather than the temp-file artefact.
            parsed_name = pages[0].pdf_name
            pdf_name = (
                os.path.basename(original_filename)
                if original_filename
                else parsed_name
            )
            if pdf_name != parsed_name:
                for p in pages:
                    p.pdf_name = pdf_name
            total_pages = pages[0].total_pages
            service_name = service_name_override or pages[0].service_name
            doc_version = await self._next_document_version(pdf_name)

            await self._progress(
                task_id,
                stage="chunking",
                progress=20,
                message="Chunking pages",
            )

            chunks: list[ChunkData] = chunk_pages(pages)
            if service_name_override:
                for c in chunks:
                    c.service_name = service_name_override
            # Mirror the canonical pdf_name into every chunk so vector payloads
            # and citation labels stay consistent across uploads of the same
            # file (the chunker copies pdf_name from each page).
            if pdf_name != parsed_name:
                for c in chunks:
                    c.pdf_name = pdf_name

            total_chunks = len(chunks)
            if total_chunks == 0:
                raise ValueError("No chunks generated")

            # Redact PII before embedding/persistence so every downstream
            # surface (vectors, BM25, citations, summary) sees the same
            # scrubbed text. No-op when INGEST_REDACT_PII is unset.
            if is_redaction_enabled():
                redacted_texts, redaction_report = redact_chunks([c.text for c in chunks])
                if redaction_report.total > 0:
                    logger.info(
                        "ingestion.redacted",
                        document_id=doc_id,
                        total=redaction_report.total,
                        counts=redaction_report.counts,
                    )
                for c, redacted in zip(chunks, redacted_texts, strict=False):
                    c.text = redacted

            sparse_encoder = BM25SparseEncoder()
            sparse_encoder.fit([c.text for c in chunks])
            try:
                sparse_encoder.save(self.settings.SPARSE_INDEX_DIR)
            except Exception as exc:
                logger.warning("ingestion.sparse_persist_failed", error=str(exc))

            await self._progress(
                task_id,
                stage="embedding",
                progress=30,
                total_chunks=total_chunks,
                message=f"Embedding {total_chunks} chunks",
            )

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
                    payload["doc_version"] = doc_version

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

                processed = min(total_chunks, i + len(batch))
                pct = 30 + int(50 * (processed / max(1, total_chunks)))
                await self._progress(
                    task_id,
                    stage="embedding",
                    progress=pct,
                    total_chunks=total_chunks,
                    processed_chunks=processed,
                    message=f"Embedded {processed}/{total_chunks} chunks",
                )

            await self._progress(
                task_id,
                stage="persisting",
                progress=85,
                message="Writing to database",
            )

            summary: str | None = None
            try:
                if self.settings.AUTO_SUMMARY_ENABLED:
                    head_texts = [c.text for c in chunks[:6]]
                    summary = await summarize_document(head_texts)
            except Exception as exc:
                logger.warning("ingestion.summary_failed", error=str(exc))
                summary = None

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
                                "version": doc_version,
                            },
                            summary=summary,
                            version=doc_version,
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
            bump_corpus_version(reason="ingest")
            await self._progress(
                task_id,
                stage="complete",
                progress=100,
                status="complete",
                document_id=doc_id,
                total_chunks=total_chunks,
                processed_chunks=total_chunks,
                message="Ingestion complete",
            )

            fire_and_forget(
                "ingestion.complete",
                {
                    "document_id": doc_id,
                    "pdf_name": pdf_name,
                    "service_name": service_name,
                    "total_pages": total_pages,
                    "total_chunks": total_chunks,
                    "task_id": task_id,
                    "version": doc_version,
                },
            )

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
            await self._progress(
                task_id,
                stage="failed",
                progress=100,
                status="failed",
                error=str(e),
                message="Ingestion failed",
            )
            return IngestionResult(
                document_id=doc_id,
                pdf_name=os.path.basename(pdf_path),
                total_pages=0,
                total_chunks=0,
                service_name=service_name_override or "Unknown",
                status="failed",
                error=str(e),
            )
