"""Word (.docx) extractor.

Emits one ``ParsedPage`` per top-level section (driven by Heading 1/2). Tables
inside the document are rendered as GitHub-flavoured markdown tables and kept
in their parent section so the chunker can preserve them as a whole unit.
"""
from __future__ import annotations

import os

import structlog

from app.ingestion.pdf_parser import ParsedPage

logger = structlog.get_logger(__name__)


def _is_heading(style_name: str | None) -> int:
    """Return heading level (1-9) or 0 if not a heading."""
    if not style_name:
        return 0
    name = style_name.strip().lower()
    if not name.startswith("heading"):
        return 0
    parts = name.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 1


def _render_table(table) -> str:
    """Render a ``docx`` table as a GFM markdown table."""
    rows: list[list[str]] = []
    for row in table.rows:
        rows.append([cell.text.strip().replace("\n", " ") for cell in row.cells])
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    out: list[str] = []
    out.append("| " + " | ".join(header) + " |")
    out.append("| " + " | ".join(["---"] * len(header)) + " |")
    for r in body:
        cells = list(r) + [""] * max(0, len(header) - len(r))
        out.append("| " + " | ".join(cells[: len(header)]) + " |")
    return "\n".join(out)


def parse_docx(path: str) -> list[ParsedPage]:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("python-docx is required for .docx ingestion") from exc

    pdf_name = os.path.basename(path)
    service_name = os.path.splitext(pdf_name)[0].replace("_", " ")

    doc = Document(path)

    sections: list[dict] = []
    current = {"title": "Document", "lines": [], "kind": "prose"}

    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}", 1)[-1]
        if tag == "p":
            from docx.text.paragraph import Paragraph

            para = Paragraph(child, doc)
            text = (para.text or "").strip()
            level = _is_heading(para.style.name if para.style else None)
            if level and level <= 2 and text:
                if current["lines"]:
                    sections.append(current)
                current = {"title": text, "lines": [], "kind": "prose"}
            elif text:
                current["lines"].append(text)
        elif tag == "tbl":
            from docx.table import Table

            table = Table(child, doc)
            rendered = _render_table(table)
            if rendered:
                if current["lines"] and current["kind"] == "prose":
                    sections.append(current)
                    current = {"title": current["title"], "lines": [], "kind": "prose"}
                sections.append({"title": current["title"], "lines": [rendered], "kind": "table"})
        # Other element types (sectPr, sdt, ...) are ignored intentionally.

    if current["lines"]:
        sections.append(current)

    pages: list[ParsedPage] = []
    total = max(1, len(sections))
    for i, sec in enumerate(sections, start=1):
        body_text = "\n\n".join(sec["lines"]).strip()
        if not body_text:
            continue
        if sec["title"] and sec["title"] != "Document":
            body_text = f"# {sec['title']}\n\n{body_text}"
        pages.append(
            ParsedPage(
                page_number=i,
                text=body_text,
                pdf_name=pdf_name,
                service_name=service_name,
                section_title=sec["title"] or "Document",
                total_pages=total,
                kind=sec["kind"],
            )
        )
    if not pages:
        pages.append(
            ParsedPage(
                page_number=1,
                text="",
                pdf_name=pdf_name,
                service_name=service_name,
                section_title="Document",
                total_pages=1,
                kind="prose",
            )
        )
    logger.info("docx.parse.complete", path=path, sections=len(pages))
    return pages
