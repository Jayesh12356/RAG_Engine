import uuid
import os
import structlog
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import insert

from app.config import get_settings
from app.llm import client as llm_client
from app.db.vector_store import get_vector_store
from app.db.relational import get_session_maker, DocumentModel, ChunkModel
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.chunker import chunk_pages
from app.ingestion.sparse import BM25SparseEncoder

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
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        self.settings = get_settings()

    async def run(self, pdf_path: str, service_name_override: str | None = None) -> IngestionResult:
        doc_id = str(uuid.uuid4())
        try:
            logger.info("ingestion.start", path=pdf_path)
            
            pages, parse_diagnostics = parse_pdf(pdf_path, self.demo_mode, include_diagnostics=True)
            if not pages:
                raise ValueError("No pages parsed from PDF")
            logger.info(
                "ingestion.parser.route",
                pdf_name=os.path.basename(pdf_path),
                pdf_type=parse_diagnostics.pdf_type,
                image_pages=parse_diagnostics.image_pages,
                text_pages=parse_diagnostics.text_pages,
                ocr_pages=parse_diagnostics.ocr_pages,
                vision_fallback_pages=parse_diagnostics.vision_fallback_pages,
            )
                
            pdf_name = pages[0].pdf_name
            total_pages = pages[0].total_pages
            service_name = service_name_override or pages[0].service_name

            chunks = chunk_pages(pages)
            if service_name_override:
                for c in chunks:
                    c.service_name = service_name_override

            total_chunks = len(chunks)
            if total_chunks == 0:
                raise ValueError("No chunks generated")

            sparse_encoder = BM25SparseEncoder()
            sparse_encoder.fit([c.text for c in chunks])
            
            vector_store = get_vector_store()
            batch_size = self.settings.EMBED_BATCH_SIZE
            
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i+batch_size]
                texts = [c.text for c in batch]
                
                dense_vectors = await llm_client.embed(texts)
                sparse_vectors = sparse_encoder.encode_batch(texts)
                
                for chunk, dense_vec, sparse_vec in zip(batch, dense_vectors, sparse_vectors):
                    payload = chunk.model_dump()
                    payload["sparse_vector"] = sparse_vec
                    
                    await vector_store.upsert(
                        collection=self.settings.vector_collection,
                        id=chunk.chunk_id,
                        vector=dense_vec,
                        payload=payload
                    )

            session_maker = get_session_maker()
            async with session_maker() as session:
                async with session.begin():
                    session.add(DocumentModel(
                        id=doc_id,
                        filename=pdf_name,
                        content="", 
                        metadata_={
                            "service_name": service_name,
                            "total_pages": total_pages,
                            "total_chunks": total_chunks
                        },
                        created_at=datetime.now()
                    ))
                    
                    for c in chunks:
                        session.add(ChunkModel(
                            id=c.chunk_id,
                            document_id=doc_id,
                            text=c.text,
                            metadata_={
                                "page_number": c.page_number,
                                "chunk_index": c.chunk_index,
                                "section_title": c.section_title
                            }
                        ))

            logger.info("ingestion.complete", document_id=doc_id, chunks=total_chunks)
            
            return IngestionResult(
                document_id=doc_id,
                pdf_name=pdf_name,
                total_pages=total_pages,
                total_chunks=total_chunks,
                service_name=service_name,
                status="success"
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
                error=str(e)
            )
