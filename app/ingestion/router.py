"""Format router for ingestion.

Maps a file's extension to the right extractor and exposes one ``extract()``
public entry point. Existing callers (``IngestPipeline``) used to call
``parse_pdf`` directly; they now go through this router so any future format
addition is a single-line change here.
"""
from __future__ import annotations

import os

import structlog

from app.ingestion.extractors.docx import parse_docx
from app.ingestion.extractors.image import parse_image
from app.ingestion.extractors.pdf import parse_pdf
from app.ingestion.extractors.pptx import parse_pptx
from app.ingestion.extractors.spreadsheet import parse_spreadsheet
from app.ingestion.extractors.text import parse_text_family
from app.ingestion.pdf_parser import ParsedPage

logger = structlog.get_logger(__name__)

# Extension -> extractor key. Add new formats here.
EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".csv": "spreadsheet",
    ".pptx": "pptx",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
    ".html": "text",
    ".htm": "text",
    ".json": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tiff": "image",
    ".tif": "image",
    ".bmp": "image",
}

SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(sorted(EXTENSION_MAP.keys()))


def is_supported(filename: str) -> bool:
    return os.path.splitext((filename or "").lower())[1] in EXTENSION_MAP


def supported_extensions_human() -> str:
    """Human-readable list for HTTP error messages."""
    grouped = {
        "PDF": [".pdf"],
        "Word": [".docx"],
        "Spreadsheet": [".xlsx", ".xls", ".csv"],
        "Presentation": [".pptx"],
        "Text/Markdown/HTML/JSON": [".txt", ".md", ".markdown", ".html", ".htm", ".json"],
        "Image": [".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp"],
    }
    return "; ".join(f"{k} ({', '.join(v)})" for k, v in grouped.items())


def extract(path: str, demo_mode: bool = False) -> list[ParsedPage]:
    """Extract a document into ``ParsedPage``s based on its extension."""
    ext = os.path.splitext(path.lower())[1]
    handler = EXTENSION_MAP.get(ext)
    if handler is None:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {supported_extensions_human()}"
        )
    logger.info("ingestion.router.dispatch", path=os.path.basename(path), kind=handler)

    if handler == "pdf":
        return parse_pdf(path, demo_mode=demo_mode)
    if handler == "docx":
        return parse_docx(path)
    if handler == "spreadsheet":
        return parse_spreadsheet(path)
    if handler == "pptx":
        return parse_pptx(path)
    if handler == "text":
        return parse_text_family(path)
    if handler == "image":
        return parse_image(path)
    raise ValueError(f"Unknown handler '{handler}' for ext '{ext}'")
