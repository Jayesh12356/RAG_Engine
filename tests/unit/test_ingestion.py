import pytest
import os
import uuid
import fitz
from unittest.mock import AsyncMock, MagicMock
from app.ingestion.pdf_parser import parse_pdf, ParsedPage, _detect_pdf_type
from app.ingestion.chunker import chunk_pages, ChunkData
from app.ingestion.sparse import BM25SparseEncoder
from app.ingestion.pipeline import IngestPipeline, IngestionResult

def test_parse_pdf_demo():
    pages = parse_pdf("nonexistent.pdf", demo_mode=True)
    assert isinstance(pages, list)
    assert len(pages) >= 1
    assert isinstance(pages[0], ParsedPage)
    assert pages[0].pdf_name != ""

def test_chunk_pages():
    pages = [
        ParsedPage(
            page_number=1,
            text="A" * 600,
            pdf_name="test.pdf",
            service_name="test",
            section_title="sec1",
            total_pages=2
        ),
        ParsedPage(
            page_number=2,
            text="B" * 600,
            pdf_name="test.pdf",
            service_name="test",
            section_title="sec2",
            total_pages=2
        )
    ]
    chunks = chunk_pages(pages)
    assert all(isinstance(c, ChunkData) for c in chunks)
    for c in chunks:
        uuid_obj = uuid.UUID(c.chunk_id)
        assert str(uuid_obj) == c.chunk_id
        assert c.pdf_name == "test.pdf"
        assert c.service_name == "test"

def test_table_kept_whole():
    table_text = "Headline\n| Col1 | Col2 |\n|---|---|\n| A | B |\n| C | D |\nFooter text"
    page = ParsedPage(
        page_number=3,
        text=table_text,
        pdf_name="test.pdf",
        service_name="test",
        section_title="sec3",
        total_pages=3
    )
    chunks = chunk_pages([page])
    assert len(chunks) == 1
    assert "| Col1" in chunks[0].text

def test_sparse_encoder():
    encoder = BM25SparseEncoder()
    encoder.fit(["reset vpn password", "ssl certificate error", "out of office"])
    res = encoder.encode("vpn password reset")
    assert isinstance(res, dict)
    assert len(res) > 0
    assert all(isinstance(v, float) for v in res.values())


def test_detect_pdf_type_identifies_image_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "tiny")
    pdf_type, image_pages = _detect_pdf_type(doc)
    doc.close()
    assert pdf_type in {"image_pdf", "mixed_pdf"}
    assert 1 in image_pages


def test_parse_pdf_routes_ocr_for_image_pdf(monkeypatch):
    image_pdf_path = os.path.join("image_pdfs", "Increase_Laptop_Battery.pdf")
    if not os.path.exists(image_pdf_path):
        pytest.skip("image_pdfs sample is not available in this environment")

    monkeypatch.setattr(
        "app.ingestion.pdf_parser._detect_pdf_type",
        lambda _doc: ("image_pdf", {1}),
    )
    monkeypatch.setattr(
        "app.ingestion.pdf_parser.extract_page_text_with_ocr",
        lambda page, page_number, pdf_name: {
            "text": "OCR extracted scanned text",
            "confidence": 0.95,
            "used_vision": False,
            "fallback_attempted": False,
        },
    )

    pages, diagnostics = parse_pdf(image_pdf_path, include_diagnostics=True)
    assert diagnostics.pdf_type == "image_pdf"
    assert diagnostics.ocr_pages >= 1
    assert "OCR extracted scanned text" in pages[0].text
    
@pytest.mark.asyncio
async def test_pipeline_demo(monkeypatch):
    async def mock_embed(texts):
        return [[0.0] * 1536 for _ in texts]
    monkeypatch.setattr("app.llm.client.embed", mock_embed)
    
    mock_vs = MagicMock()
    mock_vs.upsert = AsyncMock()
    monkeypatch.setattr("app.ingestion.pipeline.get_vector_store", lambda: mock_vs)
    
    mock_session_maker = MagicMock()
    mock_session = AsyncMock()
    mock_session_maker.return_value = mock_session
    mock_session.__aenter__.return_value = mock_session
    
    mock_begin = AsyncMock()
    mock_session.begin = MagicMock(return_value=mock_begin)
    mock_begin.__aenter__.return_value = mock_begin
    
    monkeypatch.setattr("app.ingestion.pipeline.get_session_maker", lambda: mock_session_maker)
    
    pipeline = IngestPipeline(demo_mode=True)
    result = await pipeline.run("nonexistent.pdf")
    
    assert result.status == "success"
    assert result.total_chunks > 0

@pytest.mark.asyncio
async def test_pipeline_returns_model(monkeypatch):
    async def mock_embed(texts):
        return [[0.0] * 1536 for _ in texts]
    monkeypatch.setattr("app.llm.client.embed", mock_embed)
    
    mock_vs = MagicMock()
    mock_vs.upsert = AsyncMock()
    monkeypatch.setattr("app.ingestion.pipeline.get_vector_store", lambda: mock_vs)
    
    mock_session_maker = MagicMock()
    mock_session = AsyncMock()
    mock_session_maker.return_value = mock_session
    mock_session.__aenter__.return_value = mock_session
    
    mock_begin = AsyncMock()
    mock_session.begin = MagicMock(return_value=mock_begin)
    mock_begin.__aenter__.return_value = mock_begin
    
    monkeypatch.setattr("app.ingestion.pipeline.get_session_maker", lambda: mock_session_maker)
    
    pipeline = IngestPipeline(demo_mode=True)
    result = await pipeline.run("nonexistent.pdf")
    
    assert isinstance(result, IngestionResult)
    assert isinstance(result.document_id, str)
    assert len(result.document_id) > 0
    assert result.error is None
