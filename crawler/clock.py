"""Time for the crawler (D2-01): one small interface so tests never really wait.

The runner asks the clock for the wall time (for timestamps), a monotonic time (for rate limiting)
and to sleep (rate limiting, retry back-off). ``SystemClock`` is the real thing; tests pass a fake
one that advances instantly and deterministically.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """The current time, timezone-aware (UTC)."""

    def monotonic(self) -> float:
        """Seconds from an arbitrary start; never goes backwards."""

    def sleep(self, seconds: float) -> None:
        """Wait for ``seconds`` (>= 0)."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
