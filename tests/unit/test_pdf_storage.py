import base64
import pytest

from app.config import Settings
from app.storage.pdf_storage import get_pdf_storage, RelationalPdfStorage, VectorPdfStorage


def test_pdf_storage_factory_relational(monkeypatch):
    settings = Settings(PDF_STORAGE_BACKEND="relational")
    monkeypatch.setattr("app.storage.pdf_storage.get_settings", lambda: settings)
    assert isinstance(get_pdf_storage(), RelationalPdfStorage)


def test_pdf_storage_factory_vector(monkeypatch):
    settings = Settings(PDF_STORAGE_BACKEND="vector")
    monkeypatch.setattr("app.storage.pdf_storage.get_settings", lambda: settings)
    assert isinstance(get_pdf_storage(), VectorPdfStorage)


@pytest.mark.asyncio
async def test_vector_pdf_storage_save_get_delete(monkeypatch):
    class DummyStore:
        def __init__(self):
            self.rows = []

        async def ensure_collection(self, name, dim):
            return None

        async def delete_by_filter(self, collection, filter):
            self.rows = [
                r for r in self.rows
                if not (r.get("document_id") == filter.get("document_id") and r.get("record_type") == filter.get("record_type"))
            ]

        async def upsert_payload(self, collection, id, payload):
            self.rows = [r for r in self.rows if not (r.get("document_id") == payload["document_id"] and r.get("chunk_index") == payload["chunk_index"])]
            self.rows.append(payload.copy())

        async def fetch_payloads(self, collection, filter, limit=10000):
            out = [
                r.copy() for r in self.rows
                if r.get("document_id") == filter.get("document_id") and r.get("record_type") == filter.get("record_type")
            ]
            return out[:limit]

    settings = Settings(
        PDF_STORAGE_BACKEND="vector",
        PDF_VECTOR_COLLECTION="pdf_files_test",
        PDF_VECTOR_CHUNK_BYTES=10,
    )
    dummy = DummyStore()
    monkeypatch.setattr("app.storage.pdf_storage.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.pdf_storage.get_vector_store", lambda: dummy)

    storage = VectorPdfStorage()
    raw = b"abcdefghijklmnopqrstuvwxyz"
    await storage.save_pdf("doc-1", "x.pdf", "application/pdf", raw)

    assert len(dummy.rows) >= 1
    assert all("data_b64" in r for r in dummy.rows)
    assert base64.b64decode(dummy.rows[0]["data_b64"].encode("ascii"))

    loaded = await storage.get_pdf("doc-1")
    assert loaded is not None
    assert loaded.document_id == "doc-1"
    assert loaded.filename == "x.pdf"
    assert loaded.pdf_bytes == raw

    await storage.delete_pdf("doc-1")
    loaded_after = await storage.get_pdf("doc-1")
    assert loaded_after is None
