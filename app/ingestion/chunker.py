"""Page → chunk splitter with table / list / heading awareness.

We deliberately avoid splitting through:
    - tables (≥2 lines with multiple pipes/tabs)
    - ordered lists (≥3 numbered lines)
    - headings + the first paragraph that follows them, when
      ``HEADING_AWARE_CHUNKING`` is enabled. This keeps short definition-style
      Q&A intact ("**VPN**: …") and prevents the common failure where the
      heading and answer end up in two adjacent chunks with the heading
      floating alone.
"""
from __future__ import annotations

import re
import uuid

import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion.pdf_parser import ParsedPage

logger = structlog.get_logger()


_HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+\S"),                # markdown heading
    re.compile(r"^\d+(\.\d+)*\s+[A-Z][^\n]{2,80}$"),  # 1.2 Section Title
    re.compile(r"^[A-Z][A-Z0-9 \-_/]{4,80}$"),  # ALL CAPS heading line
]


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 120:
        return False
    return any(p.match(s) for p in _HEADING_PATTERNS)


def _heading_aware_blocks(block: str) -> list[str]:
    """Split a block at heading boundaries, keeping each heading attached
    to the body that immediately follows it.
    """
    lines = block.split("\n")
    indices = [i for i, ln in enumerate(lines) if _is_heading_line(ln)]
    if not indices:
        return [block]
    sections: list[str] = []
    last = 0
    for idx in indices:
        if idx > last:
            chunk = "\n".join(lines[last:idx]).strip()
            if chunk:
                sections.append(chunk)
        last = idx
    tail = "\n".join(lines[last:]).strip()
    if tail:
        sections.append(tail)
    return [s for s in sections if s]


class ChunkData(BaseModel):
    chunk_id: str
    text: str
    pdf_name: str
    service_name: str
    section_title: str
    page_number: int
    chunk_index: int
    total_pages: int


def _merge_short_blocks(blocks: list[str], target_chars: int) -> list[str]:
    """Coalesce consecutive small blocks until each window is at least
    ``target_chars`` characters long.

    The PDF parser emits one PyMuPDF text-block per ``\\n\\n``-separated
    entry. CVs and slide decks can produce dozens of one-line blocks
    ("Jayesh Koli", "EDUCATION", "CGPA: 9.0"), each of which would otherwise
    become its own under-the-quality-floor 1-3 word chunk. Merging them here
    preserves order and the heading-with-body relationship while giving the
    recursive splitter and reranker something substantive to score.
    """
    merged: list[str] = []
    buf = ""
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if not buf:
            buf = block
            continue
        if len(buf) < target_chars:
            buf = f"{buf}\n\n{block}"
        else:
            merged.append(buf)
            buf = block
    if buf:
        merged.append(buf)
    return merged


def chunk_pages(pages: list[ParsedPage]) -> list[ChunkData]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    list_re = re.compile(r"^\s*\d+\.\s")

    target_min_chars = max(180, settings.CHUNK_SIZE // 4)
    # Tables can legitimately exceed CHUNK_SIZE (a 30-row spreadsheet window
    # with wide columns easily blows past 512 chars). The spreadsheet
    # extractor already chunks tables into windows, so we trust their size
    # and let through anything up to 6× CHUNK_SIZE rather than fragmenting
    # a markdown table that the LLM needs to read as a whole.
    table_max_chars = settings.CHUNK_SIZE * 6

    chunks: list[ChunkData] = []
    for page in pages:
        # Pre-chunked, structured pages (spreadsheet rows/tables, slides,
        # OCR'd images) are kept whole so that a row's "header: value" pairs
        # never fragment, and a markdown table never breaks across chunks.
        page_kind = getattr(page, "kind", "prose")
        if page_kind in {"row", "image"}:
            page_chunks: list[str] = [page.text.strip()] if page.text.strip() else []
        elif page_kind == "table":
            text = page.text.strip()
            if not text:
                page_chunks = []
            elif len(text) <= table_max_chars:
                page_chunks = [text]
            else:
                # Very wide table window — fall back to the splitter only
                # then; this is rare because spreadsheet windows are bounded.
                page_chunks = [t for t in splitter.split_text(text) if t.strip()]
        else:
            raw_blocks = [b for b in page.text.split("\n\n") if b.strip()]
            merged_blocks = _merge_short_blocks(raw_blocks, target_min_chars)
            page_chunks = []

            for block in merged_blocks:
                sub_blocks = (
                    _heading_aware_blocks(block)
                    if settings.HEADING_AWARE_CHUNKING
                    else [block]
                )

                for sub in sub_blocks:
                    lines = sub.split("\n")
                    table_lines = sum(
                        1 for line in lines if line.count("|") >= 2 or line.count("\t") >= 2
                    )
                    ordered_list_lines = sum(1 for line in lines if list_re.match(line))

                    if table_lines >= 2 or ordered_list_lines >= 3:
                        if len(sub) <= settings.CHUNK_SIZE * 2:
                            page_chunks.append(sub.strip())
                            continue

                    if len(sub) <= settings.CHUNK_SIZE:
                        page_chunks.append(sub.strip())
                        continue

                    split_texts = splitter.split_text(sub)
                    page_chunks.extend(t for t in split_texts if t.strip())

        for i, text in enumerate(page_chunks):
            text = text.strip()
            if not text:
                continue
            chunks.append(
                ChunkData(
                    chunk_id=str(uuid.uuid4()),
                    text=text,
                    pdf_name=page.pdf_name,
                    service_name=page.service_name,
                    section_title=page.section_title,
                    page_number=page.page_number,
                    chunk_index=i,
                    total_pages=page.total_pages,
                )
            )

    return chunks
