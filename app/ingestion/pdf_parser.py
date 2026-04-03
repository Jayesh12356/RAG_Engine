import os
import fitz
import structlog
from pydantic import BaseModel
from app.config import get_settings
from app.ingestion.ocr_parser import extract_page_text_with_ocr

logger = structlog.get_logger()


class ParseDiagnostics(BaseModel):
    pdf_type: str
    image_pages: int
    text_pages: int
    ocr_pages: int
    vision_fallback_pages: int

class ParsedPage(BaseModel):
    page_number: int
    text: str
    pdf_name: str
    service_name: str
    section_title: str
    total_pages: int

def _extract_page_text_and_title(page: fitz.Page) -> tuple[str, str]:
    rect = page.rect
    height = rect.height
    top_margin = height * 0.05
    bottom_margin = height * 0.95

    blocks = page.get_text("dict")["blocks"]
    page_text: list[str] = []
    max_font_size = -1.0
    section_title = ""

    for block in blocks:
        if block["type"] != 0:
            continue
        bbox = block["bbox"]
        if bbox[1] < top_margin or bbox[3] > bottom_margin:
            continue

        block_text_parts: list[str] = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                if span_text:
                    block_text_parts.append(span_text)
                span_size = float(span.get("size", 0))
                if span_text.strip() and span_size > max_font_size:
                    max_font_size = span_size
                    section_title = span_text.strip()
        block_text = " ".join(block_text_parts).strip()
        if block_text:
            page_text.append(block_text)
    return "\n\n".join(page_text).strip(), section_title


def _detect_pdf_type(doc: fitz.Document) -> tuple[str, set[int]]:
    settings = get_settings()
    image_pages: set[int] = set()
    total_pages = len(doc)
    if total_pages == 0:
        return "text_pdf", image_pages

    for idx in range(total_pages):
        page = doc.load_page(idx)
        text = page.get_text("text").strip()
        if len(text) < settings.PDF_IMAGE_PAGE_CHAR_THRESHOLD:
            image_pages.add(idx + 1)

    image_ratio = len(image_pages) / total_pages
    if image_ratio >= settings.PDF_IMAGE_RATIO_THRESHOLD and len(image_pages) == total_pages:
        return "image_pdf", image_pages
    if image_pages:
        if image_ratio >= settings.PDF_IMAGE_RATIO_THRESHOLD:
            return "image_pdf", image_pages
        return "mixed_pdf", image_pages
    return "text_pdf", image_pages


def parse_pdf(path: str, demo_mode: bool = False, include_diagnostics: bool = False):
    pdf_name = os.path.basename(path)
    service_name = os.path.splitext(pdf_name)[0].replace("_", " ")

    if not os.path.exists(path):
        if demo_mode:
            demo_path = "data/sample_pdfs/VPN_Setup_Guide.pdf"
            if os.path.exists(demo_path):
                path = demo_path
                pdf_name = os.path.basename(path)
                service_name = "VPN"
            else:
                logger.warning("demo PDF not found, returning synthetic page")
                pages = [ParsedPage(
                    page_number=1,
                    text="Synthetic demo content",
                    pdf_name=pdf_name,
                    service_name=service_name,
                    section_title="Demo Section",
                    total_pages=1
                )]
                diagnostics = ParseDiagnostics(
                    pdf_type="text_pdf",
                    image_pages=0,
                    text_pages=1,
                    ocr_pages=0,
                    vision_fallback_pages=0,
                )
                return (pages, diagnostics) if include_diagnostics else pages
        else:
            raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(path)
    total_pages = len(doc)
    pdf_type, image_page_numbers = _detect_pdf_type(doc)
    settings = get_settings()
    parsed_pages: list[ParsedPage] = []
    ocr_pages = 0
    vision_fallback_pages = 0

    try:
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            page_number = page_num + 1
            extracted_text, section_title = _extract_page_text_and_title(page)
            needs_ocr = page_number in image_page_numbers and settings.OCR_ENABLED

            if needs_ocr:
                ocr = extract_page_text_with_ocr(page, page_number=page_number, pdf_name=pdf_name)
                if ocr["text"].strip():
                    extracted_text = ocr["text"].strip()
                section_title = section_title or f"Page {page_number}"
                ocr_pages += 1
                if ocr["used_vision"]:
                    vision_fallback_pages += 1

            parsed_pages.append(ParsedPage(
                page_number=page_number,
                text=extracted_text,
                pdf_name=pdf_name,
                service_name=service_name,
                section_title=section_title or "Unknown",
                total_pages=total_pages
            ))
    finally:
        doc.close()

    diagnostics = ParseDiagnostics(
        pdf_type=pdf_type,
        image_pages=len(image_page_numbers),
        text_pages=total_pages - len(image_page_numbers),
        ocr_pages=ocr_pages,
        vision_fallback_pages=vision_fallback_pages,
    )
    logger.info("pdf.parse.complete", pdf_name=pdf_name, **diagnostics.model_dump())
    return (parsed_pages, diagnostics) if include_diagnostics else parsed_pages
