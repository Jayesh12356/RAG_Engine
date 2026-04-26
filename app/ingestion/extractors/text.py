"""Plain-text family extractor — ``.txt``, ``.md``, ``.html``, ``.htm`` and
``.json``.

* ``.txt``: utf-8 with chardet fallback for legacy encodings.
* ``.md``: kept as-is (markdown is already a great input for the chunker and
  for downstream LLM rendering).
* ``.html``/``.htm``: stripped to readable prose with BeautifulSoup; tables
  are rendered as GFM tables so column relationships survive.
* ``.json``: pretty-printed; we also flatten dotted paths so the embedder can
  match deep keys ("config.auth.timeout: 30s").
"""
from __future__ import annotations

import json
import os
from typing import Any

import structlog

from app.ingestion.pdf_parser import ParsedPage

logger = structlog.get_logger(__name__)

MAX_FLAT_PAIRS = 800


def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            import chardet

            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "latin-1"
            return raw.decode(encoding, errors="replace")
        except Exception:
            return raw.decode("latin-1", errors="replace")


def _html_to_markdown(html_str: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("beautifulsoup4 is required for .html ingestion") from exc

    soup = BeautifulSoup(html_str, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    parts: list[str] = []

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if title:
        parts.append(f"# {title}")

    body = soup.body or soup
    for el in body.descendants:
        name = getattr(el, "name", None)
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            txt = el.get_text(" ", strip=True)
            if txt:
                parts.append(f"{'#' * level} {txt}")
        elif name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [c.get_text(" ", strip=True).replace("|", "\\|") for c in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                head = rows[0] + [""] * (width - len(rows[0]))
                parts.append("| " + " | ".join(head) + " |")
                parts.append("| " + " | ".join(["---"] * width) + " |")
                for r in rows[1:]:
                    r2 = r + [""] * (width - len(r))
                    parts.append("| " + " | ".join(r2) + " |")
        elif name == "li":
            txt = el.get_text(" ", strip=True)
            if txt:
                parts.append(f"- {txt}")
        elif name in {"p", "blockquote"}:
            txt = el.get_text(" ", strip=True)
            if txt:
                parts.append(txt)

    return "\n\n".join(p for p in parts if p)


def _flatten_json(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def walk(node: Any, key: str) -> None:
        if len(out) >= MAX_FLAT_PAIRS:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{key}.{k}" if key else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{key}[{i}]")
        else:
            out.append((key or "value", str(node) if node is not None else ""))

    walk(obj, prefix)
    return out


def parse_text_family(path: str) -> list[ParsedPage]:
    pdf_name = os.path.basename(path)
    service_name = os.path.splitext(pdf_name)[0].replace("_", " ")
    ext = os.path.splitext(path)[1].lower()

    raw = _read_text(path)

    if ext in {".html", ".htm"}:
        text = _html_to_markdown(raw)
        section_title = "Web page"
        kind = "prose"
    elif ext == ".json":
        try:
            parsed = json.loads(raw)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            pairs = _flatten_json(parsed)
            flat = "\n".join(f"{k}: {v}" for k, v in pairs if v)
            text = f"```json\n{pretty}\n```\n\n# Flattened\n{flat}".strip()
        except Exception:
            text = raw
        section_title = "JSON"
        kind = "prose"
    elif ext == ".md":
        text = raw
        section_title = "Markdown"
        kind = "prose"
    else:
        text = raw
        section_title = "Text"
        kind = "prose"

    pages = [
        ParsedPage(
            page_number=1,
            text=text.strip(),
            pdf_name=pdf_name,
            service_name=service_name,
            section_title=section_title,
            total_pages=1,
            kind=kind,
        )
    ]
    logger.info("text.parse.complete", path=path, ext=ext, chars=len(text))
    return pages
