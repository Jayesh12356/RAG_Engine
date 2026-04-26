"""PII redaction for ingestion (Wave 3.4).

Redaction is a deterministic regex pass that runs **after parsing and before
embedding**, so every downstream consumer (vector store, BM25, summarizer,
verifier, source preview) only ever sees the redacted text. We deliberately
reuse the structural patterns from :data:`app.query.pipeline._PII_INTENTS`
plus a few extras (email, IPv4, credit-card-like sequences) that aren't
useful as query intents but are very useful to scrub from retrieved snippets.

The default backend is ``"regex"`` because it has no extra dependencies and
is fast enough to run on every chunk. Operators who want broader recall can
opt into the optional :mod:`presidio_analyzer` extra (``pii`` group in
``pyproject.toml``) and set ``INGEST_REDACT_BACKEND="presidio"`` — we then
combine regex + presidio results, taking the union.

Toggle redaction via the ``INGEST_REDACT_PII`` environment variable. When
disabled (the default for backward compatibility) :func:`redact_text` is a
no-op that returns the input unchanged.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

import structlog

logger = structlog.get_logger(__name__)


# ── Regex catalogue ─────────────────────────────────────────────────────────
# (entity, replacement, pattern). Order matters: more specific patterns must
# precede the catch-all numeric ones so an email isn't mangled by the phone
# number regex.
_REDACTION_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "EMAIL",
        "[REDACTED_EMAIL]",
        re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ),
    ),
    (
        "URL",
        "[REDACTED_URL]",
        re.compile(
            r"\bhttps?://[^\s<>\"]+", re.IGNORECASE,
        ),
    ),
    (
        "IPV4",
        "[REDACTED_IP]",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b"
        ),
    ),
    (
        "CREDIT_CARD",
        "[REDACTED_CARD]",
        re.compile(
            r"\b(?:\d[ -]*?){13,19}\b"
        ),
    ),
    (
        "AADHAAR",
        "[REDACTED_AADHAAR]",
        re.compile(
            r"\b\d{4}\s?\d{4}\s?\d{4}\b"
        ),
    ),
    (
        "PAN",
        "[REDACTED_PAN]",
        re.compile(
            r"\b[A-Z]{5}\d{4}[A-Z]\b"
        ),
    ),
    (
        "SSN",
        "[REDACTED_SSN]",
        re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        ),
    ),
    # Phone numbers are dialled last so longer card / aadhaar matches win.
    (
        "PHONE",
        "[REDACTED_PHONE]",
        re.compile(r"\+?\d[\d\s\-().]{8,}\d"),
    ),
    (
        "DATE_OF_BIRTH",
        "[REDACTED_DOB]",
        re.compile(
            r"\b(?:dob|date\s*of\s*birth)[:\s]*"
            r"\d{1,2}[/\-\s](?:0?[1-9]|1[0-2]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[/\-\s]\d{2,4}\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass
class RedactionReport:
    """Aggregate counts per entity for a single ingestion run."""

    counts: dict[str, int]
    total: int

    def merge(self, other: "RedactionReport") -> "RedactionReport":
        merged: dict[str, int] = dict(self.counts)
        for k, v in other.counts.items():
            merged[k] = merged.get(k, 0) + v
        return RedactionReport(counts=merged, total=self.total + other.total)


def is_redaction_enabled() -> bool:
    """Return ``True`` when the operator has opted in to redaction."""
    raw = os.getenv("INGEST_REDACT_PII", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _backend() -> str:
    return (os.getenv("INGEST_REDACT_BACKEND") or "regex").strip().lower()


def _regex_redact(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    redacted = text
    for entity, replacement, pattern in _REDACTION_PATTERNS:
        new_text, n = pattern.subn(replacement, redacted)
        if n:
            counts[entity] = counts.get(entity, 0) + n
            redacted = new_text
    return redacted, counts


def _presidio_redact(text: str) -> tuple[str, dict[str, int]]:
    """Optional second pass via :mod:`presidio_analyzer`.

    Falls back silently to a no-op when the optional extra isn't installed
    or initialisation fails. The presidio analyzer + a tiny anonymizer pass
    catches cases the regex misses (international phone numbers without a
    country code prefix, person names, etc).
    """
    try:  # pragma: no cover — exercised only when extras are installed
        analyzer = _presidio_engine()
    except Exception:
        return text, {}

    try:  # pragma: no cover
        results = analyzer.analyze(
            text=text,
            language="en",
            entities=[
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "PERSON",
                "CREDIT_CARD",
                "IP_ADDRESS",
                "US_SSN",
                "IN_AADHAAR",
                "IN_PAN",
                "DATE_TIME",
                "URL",
            ],
        )
    except Exception as exc:  # pragma: no cover
        logger.debug("redact.presidio_failed", error=str(exc))
        return text, {}

    if not results:
        return text, {}

    # Merge overlapping spans so we don't double-replace.
    spans = sorted(results, key=lambda r: r.start)
    merged: list[tuple[int, int, str]] = []
    for r in spans:
        if merged and r.start <= merged[-1][1]:
            prev = merged.pop()
            merged.append((prev[0], max(prev[1], r.end), prev[2]))
        else:
            merged.append((r.start, r.end, r.entity_type))

    out: list[str] = []
    counts: dict[str, int] = {}
    cursor = 0
    for start, end, entity in merged:
        out.append(text[cursor:start])
        out.append(f"[REDACTED_{entity}]")
        counts[entity] = counts.get(entity, 0) + 1
        cursor = end
    out.append(text[cursor:])
    return "".join(out), counts


_presidio_singleton = None


def _presidio_engine():  # pragma: no cover — exercised only with extras
    global _presidio_singleton
    if _presidio_singleton is None:
        from presidio_analyzer import AnalyzerEngine  # type: ignore

        _presidio_singleton = AnalyzerEngine()
    return _presidio_singleton


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    """Redact PII from ``text`` and return ``(redacted, counts_by_entity)``.

    Pure no-op (returns the input) when ``INGEST_REDACT_PII`` is unset,
    so the embed/store path is unchanged for existing deployments.
    """
    if not text:
        return text, {}
    if not is_redaction_enabled():
        return text, {}

    redacted, counts = _regex_redact(text)
    if _backend() == "presidio":
        redacted, more = _presidio_redact(redacted)
        for k, v in more.items():
            counts[k] = counts.get(k, 0) + v
    return redacted, counts


def redact_chunks(texts: Iterable[str]) -> tuple[list[str], RedactionReport]:
    """Redact a sequence of chunk texts and aggregate the per-entity counts."""
    out: list[str] = []
    aggregate: dict[str, int] = {}
    total = 0
    for raw in texts:
        red, counts = redact_text(raw or "")
        out.append(red)
        for k, v in counts.items():
            aggregate[k] = aggregate.get(k, 0) + v
            total += v
    return out, RedactionReport(counts=aggregate, total=total)
