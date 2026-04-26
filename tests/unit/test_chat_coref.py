"""Unit tests for :func:`app.query.rewrite.maybe_rewrite_with_history`."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.chat.session import HistoryTurn
from app.config import get_settings
from app.query.rewrite import (
    _format_history_for_prompt,
    _looks_like_followup,
    maybe_rewrite_with_history,
)


def _turn(role: str, content: str) -> HistoryTurn:
    return HistoryTurn(
        id="t",
        session_id="s",
        role=role,
        content=content,
        created_at="2026-01-01T00:00:00Z",
    )


# ── Heuristic detector ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "question",
    [
        "why?",
        "what about it",
        "tell me more",
        "and that one too",
        "Why is that the case?",
        "elaborate on the previous answer",
        "explain it again",
    ],
)
def test_looks_like_followup_positive(question):
    assert _looks_like_followup(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "How do I reset my VPN password?",
        "What are the steps to connect to Pulse Secure?",
        "List Jayesh Koli's projects",
        "",
        "   ",
    ],
)
def test_looks_like_followup_negative(question):
    assert _looks_like_followup(question) is False


# ── History formatter ─────────────────────────────────────────────────────


def test_format_history_truncates_long_assistant_turns():
    long_text = "x" * 600
    history = [_turn("assistant", long_text)]
    out = _format_history_for_prompt(history)
    assert "..." in out
    assert len(out) < 600


def test_format_history_caps_to_max_turns():
    history = [_turn("user", f"q{i}") for i in range(10)]
    out = _format_history_for_prompt(history, max_turns=3)
    assert out.count("\n") == 2  # 3 lines = 2 newlines


# ── maybe_rewrite_with_history ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rewrite_no_op_when_flag_off():
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = False
    history = [_turn("user", "what is VPN"), _turn("assistant", "VPN is...")]
    out = await maybe_rewrite_with_history("why?", history)
    assert out == "why?"


@pytest.mark.asyncio
async def test_rewrite_no_op_when_no_history():
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = True
    try:
        out = await maybe_rewrite_with_history("why?", [])
        assert out == "why?"
    finally:
        settings.CHAT_COREFERENCE_REWRITE = False


@pytest.mark.asyncio
async def test_rewrite_no_op_for_standalone_question():
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = True
    try:
        history = [_turn("user", "anything")]
        with patch(
            "app.query.rewrite.llm_client.complete", new_callable=AsyncMock
        ) as mc:
            out = await maybe_rewrite_with_history(
                "What are the steps to reset my VPN password?", history
            )
            assert out.startswith("What are the steps")
            mc.assert_not_awaited()
    finally:
        settings.CHAT_COREFERENCE_REWRITE = False


@pytest.mark.asyncio
@patch("app.query.rewrite.llm_client.complete", new_callable=AsyncMock)
async def test_rewrite_resolves_followup(mock_complete):
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = True
    try:
        mock_complete.return_value = (
            "What are the security implications of resetting a VPN password?"
        )
        history = [
            _turn("user", "what is VPN"),
            _turn("assistant", "VPN provides encrypted remote network access."),
            _turn("user", "how do I reset my VPN password"),
            _turn("assistant", "Visit the corporate portal..."),
        ]
        out = await maybe_rewrite_with_history("why?", history)
        assert "VPN" in out
        mock_complete.assert_awaited_once()
    finally:
        settings.CHAT_COREFERENCE_REWRITE = False


@pytest.mark.asyncio
@patch("app.query.rewrite.llm_client.complete", new_callable=AsyncMock)
async def test_rewrite_falls_open_on_llm_error(mock_complete):
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = True
    try:
        mock_complete.side_effect = RuntimeError("provider down")
        history = [_turn("user", "anything"), _turn("assistant", "answer")]
        out = await maybe_rewrite_with_history("tell me more", history)
        assert out == "tell me more"
    finally:
        settings.CHAT_COREFERENCE_REWRITE = False


@pytest.mark.asyncio
@patch("app.query.rewrite.llm_client.complete", new_callable=AsyncMock)
async def test_rewrite_keeps_original_when_llm_returns_short_garbage(mock_complete):
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = True
    try:
        mock_complete.return_value = "ok"  # too short
        history = [_turn("user", "x"), _turn("assistant", "y")]
        out = await maybe_rewrite_with_history("why?", history)
        assert out == "why?"
    finally:
        settings.CHAT_COREFERENCE_REWRITE = False


@pytest.mark.asyncio
@patch("app.query.rewrite.llm_client.complete", new_callable=AsyncMock)
async def test_rewrite_keeps_original_when_llm_echoes_input(mock_complete):
    settings = get_settings()
    settings.CHAT_COREFERENCE_REWRITE = True
    try:
        mock_complete.return_value = "Why?"
        history = [_turn("user", "x"), _turn("assistant", "y")]
        out = await maybe_rewrite_with_history("why?", history)
        assert out == "why?"
    finally:
        settings.CHAT_COREFERENCE_REWRITE = False
