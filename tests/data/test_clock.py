"""Tests for crawler.clock (D2-01): the real clock used outside tests (added by the D3-08 module coverage check)."""
from __future__ import annotations

import time
from datetime import timezone

from crawler.clock import Clock, SystemClock
from tests.data.crawl_testkit import FakeClock


def test_system_clock_gives_utc_aware_time_close_to_now() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None and now.utcoffset() == timezone.utc.utcoffset(None)
    assert abs(now.timestamp() - time.time()) < 5


def test_system_clock_monotonic_never_goes_backwards() -> None:
    clock = SystemClock()
    values = [clock.monotonic() for _ in range(100)]
    assert values == sorted(values)


def test_system_clock_sleep_waits_and_zero_or_negative_returns_at_once() -> None:
    clock = SystemClock()
    start = time.monotonic()
    clock.sleep(0)
    clock.sleep(-1)
    assert time.monotonic() - start < 0.05
    start = time.monotonic()
    clock.sleep(0.02)
    assert time.monotonic() - start >= 0.015


def test_the_fake_clock_has_the_same_interface() -> None:
    for name in ("now", "monotonic", "sleep"):
        assert callable(getattr(SystemClock, name)) and callable(getattr(FakeClock, name)) and hasattr(Clock, name)
