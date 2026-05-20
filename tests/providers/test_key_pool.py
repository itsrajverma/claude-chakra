"""Unit tests for ``providers.key_pool.KeyPool``."""

from __future__ import annotations

import pytest

from providers.key_pool import KeyPool


def test_requires_at_least_one_key():
    with pytest.raises(ValueError):
        KeyPool([], scope="nim")
    with pytest.raises(ValueError):
        KeyPool(["", "  "], scope="nim")


def test_single_key_returns_same_value():
    pool = KeyPool(["only"], scope="nim")
    assert pool.next_live_key() == "only"
    assert pool.next_live_key() == "only"


def test_round_robin_across_live_keys():
    pool = KeyPool(["a", "b", "c"], scope="nim")
    assert [pool.next_live_key() for _ in range(6)] == ["a", "b", "c", "a", "b", "c"]


def test_rate_limited_key_skipped_until_cooldown_expires(monkeypatch):
    clock = {"now": 1000.0}

    def fake_monotonic() -> float:
        return clock["now"]

    monkeypatch.setattr("providers.key_pool.time.monotonic", fake_monotonic)

    pool = KeyPool(["a", "b", "c"], scope="nim", default_cooldown_seconds=30.0)

    first = pool.next_live_key()
    assert first == "a"
    pool.report_rate_limit("a")

    # 'a' is now cooling; expect 'b', 'c', then back to 'b' (skipping 'a').
    assert pool.next_live_key() == "b"
    assert pool.next_live_key() == "c"
    assert pool.next_live_key() == "b"

    # Advance past cooldown — 'a' becomes live again.
    clock["now"] += 31.0
    keys_after_cool = {pool.next_live_key() for _ in range(6)}
    assert keys_after_cool == {"a", "b", "c"}


def test_all_cooling_returns_soonest_free(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        "providers.key_pool.time.monotonic", lambda: clock["now"]
    )

    pool = KeyPool(["a", "b"], scope="nim", default_cooldown_seconds=60.0)
    pool.report_rate_limit("a", cooldown_seconds=60.0)
    # Advance enough for both to be cooling but 'a' to be soonest-free.
    pool.report_rate_limit("b", cooldown_seconds=120.0)

    assert pool.all_cooling()
    assert pool.next_live_key() == "a"


def test_empty_keys_are_dropped():
    pool = KeyPool(["x", "", "  ", "y"], scope="nim")
    assert pool.size == 2
    seen = {pool.next_live_key() for _ in range(4)}
    assert seen == {"x", "y"}
