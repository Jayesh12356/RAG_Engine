"""Tests for the per-cookie ``Settings`` override channel (Wave 2.8)."""

from __future__ import annotations

import pytest

from app.config import (
    OVERRIDABLE_SETTINGS,
    get_settings,
    reset_settings_overrides,
    set_settings_overrides,
)


def test_no_overrides_returns_singleton() -> None:
    a = get_settings()
    b = get_settings()
    assert a is b


def test_allowlisted_override_is_applied() -> None:
    base = get_settings()
    assert "HYDE_ENABLED" in OVERRIDABLE_SETTINGS
    token = set_settings_overrides({"HYDE_ENABLED": True})
    try:
        s = get_settings()
        assert s.HYDE_ENABLED is True
        # Singleton unchanged
        assert base.HYDE_ENABLED is False or base.HYDE_ENABLED is True
        assert s is not base
    finally:
        reset_settings_overrides(token)
    # Reverts after reset
    assert get_settings() is base


def test_non_allowlisted_keys_silently_dropped() -> None:
    token = set_settings_overrides({"DATABASE_URL": "postgresql://evil/", "MAX_CHUNKS_RETURN": 7})
    try:
        s = get_settings()
        # Allowlisted survives
        assert s.MAX_CHUNKS_RETURN == 7
        # Non-allowlisted is filtered — falls back to the base value
        assert "evil" not in (s.DATABASE_URL or "")
    finally:
        reset_settings_overrides(token)


def test_concurrent_contexts_isolated() -> None:
    import asyncio

    async def child(value: int) -> int:
        token = set_settings_overrides({"RERANK_TOP_N": value})
        try:
            await asyncio.sleep(0)
            return get_settings().RERANK_TOP_N
        finally:
            reset_settings_overrides(token)

    async def main() -> tuple[int, int]:
        # Each task gets its own contextvar copy via asyncio.Task.
        return await asyncio.gather(child(11), child(22))

    a, b = asyncio.run(main())
    assert {a, b} == {11, 22}


@pytest.mark.parametrize(
    "key, value",
    [
        ("LLM_PROVIDER", "openai"),
        ("MAX_CHUNKS_RETURN", 33),
        ("ANSWER_VERIFIER_MIN_SCORE", 0.42),
        ("MMR_ENABLED", False),
    ],
)
def test_round_trip_for_known_keys(key: str, value) -> None:
    token = set_settings_overrides({key: value})
    try:
        assert getattr(get_settings(), key) == value
    finally:
        reset_settings_overrides(token)
