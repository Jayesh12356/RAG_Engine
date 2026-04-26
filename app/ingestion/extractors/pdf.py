"""Thin wrapper over the existing ``parse_pdf`` so the router exposes one
uniform call signature across formats.
"""
from __future__ import annotations

from app.ingestion.pdf_parser import ParsedPage, parse_pdf as _parse_pdf


def parse_pdf(path: str, demo_mode: bool = False) -> list[ParsedPage]:
    pages = _parse_pdf(path, demo_mode=demo_mode, include_diagnostics=False)
    return list(pages)
