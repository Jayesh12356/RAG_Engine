"""Unit tests for the groundedness verifier."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.models.query import SearchResult
from app.query.verifier import _parse_score, verify_groundedness


def _chunks() -> list[SearchResult]:
    return [
        SearchResult(
            chunk_id="c1",
            document_id="d",
            text="Resetting a VPN password requires email verification through the corporate portal.",
            score=0.8,
        )
    ]


# ── _parse_score ----------------------------------------------------------


def test_parse_score_strict_json():
    score, reason = _parse_score('{"score": 0.42, "reason": "missing detail"}')
    assert score == 0.42
    assert reason == "missing detail"


def test_parse_score_clamps_to_unit_interval():
    s, _ = _parse_score('{"score": 1.7}')
    assert s == 1.0
    s2, _ = _parse_score('{"score": -0.5}')
    assert s2 == 0.0


def test_parse_score_regex_fallback():
    s, reason = _parse_score('verdict says "score": 0.31 something')
    assert s == 0.31
    assert reason == "regex"


def test_parse_score_loose_number():
    s, reason = _parse_score("score is around 0.7")
    assert s == 0.7
    assert reason == "loose"


def test_parse_score_unparseable_fails_open():
    s, reason = _parse_score("totally garbage with no digits")
    assert s == 1.0
    assert reason == "unparseable"


def test_parse_score_empty_string():
    s, reason = _parse_score("")
    assert s == 1.0
    assert reason == "empty"


# ── verify_groundedness --------------------------------------------------


@pytest.mark.asyncio
async def test_verifier_short_circuits_when_disabled():
    settings = get_settings()
    settings.ANSWER_VERIFIER_ENABLED = False
    passed, score, reason = await verify_groundedness("q", "a", _chunks())
    assert passed is True
    assert score == 1.0
    assert reason == "disabled"


@pytest.mark.asyncio
async def test_verifier_short_circuits_for_empty_answer():
    settings = get_settings()
    settings.ANSWER_VERIFIER_ENABLED = True
    try:
        passed, score, reason = await verify_groundedness("q", "", _chunks())
        assert passed is True
        assert reason == "trivial"
    finally:
        settings.ANSWER_VERIFIER_ENABLED = False


@pytest.mark.asyncio
@patch("app.query.verifier.llm_client.complete", new_callable=AsyncMock)
async def test_verifier_passes_when_score_above_threshold(mock_complete):
    settings = get_settings()
    settings.ANSWER_VERIFIER_ENABLED = True
    settings.ANSWER_VERIFIER_MIN_SCORE = 0.5
    try:
        mock_complete.return_value = '{"score": 0.85, "reason": "ok"}'
        passed, score, _ = await verify_groundedness(
            "q", "an answer", _chunks()
        )
        assert passed is True
        assert score == 0.85
    finally:
        settings.ANSWER_VERIFIER_ENABLED = False


@pytest.mark.asyncio
@patch("app.query.verifier.llm_client.complete", new_callable=AsyncMock)
async def test_verifier_fails_when_score_below_threshold(mock_complete):
    settings = get_settings()
    settings.ANSWER_VERIFIER_ENABLED = True
    settings.ANSWER_VERIFIER_MIN_SCORE = 0.6
    try:
        mock_complete.return_value = '{"score": 0.2, "reason": "hallucinated"}'
        passed, score, reason = await verify_groundedness(
            "q", "an answer", _chunks()
        )
        assert passed is False
        assert score == 0.2
        assert reason == "hallucinated"
    finally:
        settings.ANSWER_VERIFIER_ENABLED = False


@pytest.mark.asyncio
@patch("app.query.verifier.llm_client.complete", new_callable=AsyncMock)
async def test_verifier_fails_open_on_llm_error(mock_complete):
    settings = get_settings()
    settings.ANSWER_VERIFIER_ENABLED = True
    try:
        mock_complete.side_effect = RuntimeError("provider down")
        passed, score, reason = await verify_groundedness(
            "q", "a", _chunks()
        )
        assert passed is True
        assert score == 1.0
        assert reason.startswith("llm-error:")
    finally:
        settings.ANSWER_VERIFIER_ENABLED = False
