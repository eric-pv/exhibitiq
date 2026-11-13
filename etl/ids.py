"""ID generation for data packages (D2-01).

Contract (``docs/specs/data-package-contract.md`` §2): every ID except the human-chosen
``exhibition_id`` is a short prefix, an underscore and a ULID: 26 characters of Crockford
Base32 (``0-9`` and ``A-Z`` without ``I L O U``) whose first character is ``0``-``7``.

    src_01JF...  (source)   run_01JF...  (crawl run)   co_...  pt_...  chg_...

A ULID is a 48-bit millisecond timestamp followed by 80 random bits, so IDs created later
sort later and collide only with negligible probability. IDs are **opaque**: never derive
them from names or domains, and never reuse one (contract §2).

Both the clock and the random source are injectable so tests are deterministic.
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PREFIXES = frozenset({"co", "pt", "src", "run", "chg"})
_MAX_MS = 2**48 - 1


def new_ulid(*, now_ms: int | None = None, rand: Callable[[int], bytes] = os.urandom) -> str:
    """A 26-character ULID. ``now_ms`` is Unix time in milliseconds (default: the system clock)."""
    milliseconds = time.time_ns() // 1_000_000 if now_ms is None else now_ms
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, int) or not 0 <= milliseconds <= _MAX_MS:
        raise ValueError(f"now_ms must be an integer between 0 and {_MAX_MS}")
    randomness = rand(10)
    if len(randomness) != 10:
        raise ValueError("rand(10) must return exactly 10 bytes")
    value = int.from_bytes(milliseconds.to_bytes(6, "big") + randomness, "big")  # 128 bits
    chars = []
    for _ in range(26):  # 26 * 5 = 130 bits: the first character carries only the top 3 bits (0-7)
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def make_id(prefix: str, *, now_ms: int | None = None, rand: Callable[[int], bytes] = os.urandom) -> str:
    """``<prefix>_<ULID>``; ``prefix`` is one of ``co``, ``pt``, ``src``, ``run``, ``chg``."""
    if prefix not in PREFIXES:
        raise ValueError(f"unknown ID prefix {prefix!r}; expected one of {sorted(PREFIXES)}")
    return f"{prefix}_{new_ulid(now_ms=now_ms, rand=rand)}"
