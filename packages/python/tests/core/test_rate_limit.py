"""Sliding-window rate limiter — unit tests for the primitive itself.

Wire-level tests (login + setup endpoints returning 429) live in
test_rate_limit_routes.py. These pin the algorithm so a regression
in the bookkeeping (e.g. failing to expire old hits) gets caught
before it papers over with route-level mocks."""

from __future__ import annotations

import time

import pytest

from awaithumans.server.core.rate_limit import RateLimiter


def test_under_limit_returns_true() -> None:
    rl = RateLimiter(limit=3, window_seconds=60)
    assert rl.check("k") is True
    assert rl.check("k") is True
    assert rl.check("k") is True


def test_at_limit_returns_false() -> None:
    rl = RateLimiter(limit=2, window_seconds=60)
    assert rl.check("k") is True
    assert rl.check("k") is True
    assert rl.check("k") is False
    # And stays false within the window.
    assert rl.check("k") is False


def test_keys_are_independent() -> None:
    rl = RateLimiter(limit=1, window_seconds=60)
    assert rl.check("alice") is True
    # alice exhausted, bob fresh
    assert rl.check("alice") is False
    assert rl.check("bob") is True


def test_reset_clears_counter() -> None:
    rl = RateLimiter(limit=1, window_seconds=60)
    assert rl.check("k") is True
    assert rl.check("k") is False
    rl.reset("k")
    assert rl.check("k") is True


def test_window_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hits older than `window_seconds` must drop out of the count.
    Without this, every key would eventually be permanently blocked."""
    fake_now = [1000.0]

    def fake_monotonic() -> float:
        return fake_now[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    rl = RateLimiter(limit=2, window_seconds=10)
    assert rl.check("k") is True  # t=1000
    assert rl.check("k") is True  # t=1000
    assert rl.check("k") is False  # at limit

    fake_now[0] = 1011.0  # window has rolled
    assert rl.check("k") is True  # earliest two hits expired


def test_partial_window_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    """When some hits are still inside the window, only the expired
    ones drop. Catches an off-by-one in the cutoff comparison."""
    fake_now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

    rl = RateLimiter(limit=3, window_seconds=10)
    rl.check("k")
    fake_now[0] = 1005.0
    rl.check("k")
    fake_now[0] = 1009.0
    rl.check("k")  # 3rd hit, at limit

    fake_now[0] = 1011.0  # First hit (t=1000) is just past the window
    # Two recent hits remain → one slot free
    assert rl.check("k") is True
    # Now full again
    assert rl.check("k") is False


def test_init_validates_inputs() -> None:
    with pytest.raises(ValueError):
        RateLimiter(limit=0, window_seconds=10)
    with pytest.raises(ValueError):
        RateLimiter(limit=10, window_seconds=0)
