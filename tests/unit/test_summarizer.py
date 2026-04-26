"""Unit tests for the document auto-summarizer."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ingestion.summarizer import _clean_summary, _coalesce_text, summarize_document


def test_coalesce_text_caps_at_limit():
    out = _coalesce_text(["aaaa", "bbbb", "cccc"], cap_chars=10)
    assert len(out) <= 10


def test_coalesce_text_skips_empty_snippets():
    out = _coalesce_text(["", "  ", "real text"], cap_chars=100)
    assert out.strip() == "real text"


def test_coalesce_text_returns_empty_when_input_empty():
    assert _coalesce_text([], cap_chars=100) == ""
    assert _coalesce_text(["", ""], cap_chars=100) == ""


def test_clean_summary_strips_filler():
    assert _clean_summary("Here is a summary: about the doc.") == "a summary: about the doc."
    assert _clean_summary('"Quoted summary"').endswith("Quoted summary")


def test_clean_summary_collapses_whitespace():
    assert _clean_summary("foo   bar\n\nbaz") == "foo bar baz"


def test_clean_summary_caps_length():
    long = "x " * 1000
    assert len(_clean_summary(long)) <= 600


def test_clean_summary_handles_empty():
    assert _clean_summary("") == ""


@pytest.mark.asyncio
@patch("app.ingestion.summarizer.llm_client.complete", new_callable=AsyncMock)
async def test_summarize_document_returns_clean_summary(mock_complete):
    mock_complete.return_value = (
        "Here is a summary: This document explains VPN setup and password reset."
    )
    out = await summarize_document(
        ["VPN setup overview", "Password reset procedures"],
    )
    assert out is not None
    assert "VPN" in out


@pytest.mark.asyncio
@patch("app.ingestion.summarizer.llm_client.complete", new_callable=AsyncMock)
async def test_summarize_document_returns_none_on_empty_text(mock_complete):
    out = await summarize_document([])
    assert out is None
    mock_complete.assert_not_called()


@pytest.mark.asyncio
@patch("app.ingestion.summarizer.llm_client.complete", new_callable=AsyncMock)
async def test_summarize_document_fails_open_on_llm_error(mock_complete):
    mock_complete.side_effect = RuntimeError("boom")
    out = await summarize_document(["something"])
    assert out is None


@pytest.mark.asyncio
@patch("app.ingestion.summarizer.llm_client.complete", new_callable=AsyncMock)
async def test_summarize_document_returns_none_when_llm_returns_blank(mock_complete):
    mock_complete.return_value = ""
    out = await summarize_document(["something"])
    assert out is None
