"""Standalone image extractor — ``.png``, ``.jpg``, ``.jpeg``, ``.webp``,
``.tiff``, ``.bmp``.

Reuses the existing OCR + vision-LLM stack from ``ocr_parser.py``. We render
the image into a PyMuPDF pixmap (without spinning up a fake PDF) by loading
the image directly via PIL and converting it to a pixmap-shaped object the
existing helpers accept.
"""
from __future__ import annotations

import io
import os

import fitz
import structlog

from app.config import get_settings
from app.ingestion.ocr_parser import (
    _extract_with_tesseract,
    _extract_with_vision_llm,
    _score_text_quality,
)
from app.ingestion.pdf_parser import ParsedPage

logger = structlog.get_logger(__name__)


def _image_to_pixmap(path: str) -> fitz.Pixmap:
    """Load any PIL-readable image, return a PyMuPDF Pixmap (RGB) at native DPI.

    PyMuPDF can read PNG/JPEG/TIFF/BMP/WEBP directly via ``fitz.Pixmap`` for
    most paths; for a couple of older webp builds we round-trip through PIL +
    PNG bytes which guarantees compatibility.
    """
    try:
        return fitz.Pixmap(path)
    except Exception:
        from PIL import Image

        with Image.open(path) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="PNG")
            return fitz.Pixmap(buf.getvalue())


def parse_image(path: str) -> list[ParsedPage]:
    settings = get_settings()
    pdf_name = os.path.basename(path)
    service_name = os.path.splitext(pdf_name)[0].replace("_", " ")

    pix = _image_to_pixmap(path)

    used_vision = False
    text = ""

    if settings.OCR_MODE == "vision":
        text = _extract_with_vision_llm(pix, enabled=True).strip()
        if text:
            used_vision = True
        else:
            text, _ = _extract_with_tesseract(pix, settings.OCR_LANGUAGES)
    elif settings.OCR_MODE == "tesseract":
        text, _ = _extract_with_tesseract(pix, settings.OCR_LANGUAGES)
    else:
        text, conf = _extract_with_tesseract(pix, settings.OCR_LANGUAGES)
        if (
            settings.OCR_VISION_FALLBACK_ENABLED
            and conf < settings.OCR_TEXT_CONFIDENCE_THRESHOLD
        ):
            fallback = _extract_with_vision_llm(pix, enabled=True).strip()
            if fallback and _score_text_quality(fallback) >= conf:
                text = fallback
                used_vision = True

    text = (text or "").strip() or "(no text detected in image)"

    page = ParsedPage(
        page_number=1,
        text=text,
        pdf_name=pdf_name,
        service_name=service_name,
        section_title="Image",
        total_pages=1,
        kind="image",
    )
    logger.info(
        "image.parse.complete",
        path=path,
        chars=len(text),
        used_vision=used_vision,
    )
    return [page]
