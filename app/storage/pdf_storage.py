import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, delete

from app.config import get_settings
from app.db.relational import get_session_maker, DocumentFileModel
from app.db.vector_store import get_vector_store


@dataclass
class StoredPdf:
    document_id: str
    filename: str
    content_type: str
    pdf_bytes: bytes


class PdfStorage(ABC):
    @abstractmethod
    async def save_pdf(self, document_id: str, filename: str, content_type: str, pdf_bytes: bytes) -> None:
        pass

    @abstractmethod
    async def get_pdf(self, document_id: str) -> Optional[StoredPdf]:
        pass

    @abstractmethod
    async def delete_pdf(self, document_id: str) -> None:
        pass


class RelationalPdfStorage(PdfStorage):
    async def save_pdf(self, document_id: str, filename: str, content_type: str, pdf_bytes: bytes) -> None:
        async with get_session_maker()() as session:
            await session.execute(delete(DocumentFileModel).where(DocumentFileModel.document_id == document_id))
            session.add(
                DocumentFileModel(
                    document_id=document_id,
                    filename=filename,
                    content_type=content_type or "application/pdf",
                    pdf_blob=pdf_bytes,
                )
            )
            await session.commit()

    async def get_pdf(self, document_id: str) -> Optional[StoredPdf]:
        async with get_session_maker()() as session:
            stmt = select(DocumentFileModel).where(DocumentFileModel.document_id == document_id)
            res = await session.execute(stmt)
            row = res.scalar_one_or_none()
            if row is None:
                return None
            return StoredPdf(
                document_id=document_id,
                filename=row.filename,
                content_type=row.content_type or "application/pdf",
                pdf_bytes=row.pdf_blob,
            )

    async def delete_pdf(self, document_id: str) -> None:
        async with get_session_maker()() as session:
            await session.execute(delete(DocumentFileModel).where(DocumentFileModel.document_id == document_id))
            await session.commit()


class VectorPdfStorage(PdfStorage):
    async def save_pdf(self, document_id: str, filename: str, content_type: str, pdf_bytes: bytes) -> None:
        settings = get_settings()
        chunk_size = max(int(settings.PDF_VECTOR_CHUNK_BYTES), 4096)
        collection = settings.PDF_VECTOR_COLLECTION
        store = get_vector_store()
        await store.ensure_collection(collection, dim=1)
        await store.delete_by_filter(collection, {"document_id": document_id, "record_type": "pdf_chunk"})

        total_chunks = (len(pdf_bytes) + chunk_size - 1) // chunk_size if pdf_bytes else 1
        if not pdf_bytes:
            payload = {
                "record_type": "pdf_chunk",
                "document_id": document_id,
                "chunk_index": 0,
                "total_chunks": 1,
                "filename": filename,
                "content_type": content_type or "application/pdf",
                "data_b64": "",
            }
            await store.upsert_payload(collection, f"pdffile:{document_id}:0", payload)
            return

        for idx in range(total_chunks):
            start = idx * chunk_size
            part = pdf_bytes[start : start + chunk_size]
            payload = {
                "record_type": "pdf_chunk",
                "document_id": document_id,
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "filename": filename,
                "content_type": content_type or "application/pdf",
                "data_b64": base64.b64encode(part).decode("ascii"),
            }
            await store.upsert_payload(collection, f"pdffile:{document_id}:{idx}", payload)

    async def get_pdf(self, document_id: str) -> Optional[StoredPdf]:
        settings = get_settings()
        store = get_vector_store()
        payloads = await store.fetch_payloads(
            settings.PDF_VECTOR_COLLECTION,
            {"document_id": document_id, "record_type": "pdf_chunk"},
            limit=200000,
        )
        if not payloads:
            return None

        ordered = sorted(payloads, key=lambda p: int(p.get("chunk_index", 0)))
        filename = ordered[0].get("filename", f"{document_id}.pdf")
        content_type = ordered[0].get("content_type", "application/pdf")
        raw = b"".join(base64.b64decode((p.get("data_b64") or "").encode("ascii")) for p in ordered)
        return StoredPdf(document_id=document_id, filename=filename, content_type=content_type, pdf_bytes=raw)

    async def delete_pdf(self, document_id: str) -> None:
        settings = get_settings()
        store = get_vector_store()
        await store.delete_by_filter(
            settings.PDF_VECTOR_COLLECTION,
            {"document_id": document_id, "record_type": "pdf_chunk"},
        )


def get_pdf_storage() -> PdfStorage:
    settings = get_settings()
    if settings.PDF_STORAGE_BACKEND == "vector":
        return VectorPdfStorage()
    return RelationalPdfStorage()
