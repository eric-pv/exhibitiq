"""Tests for etl.ids (D2-01). Generated IDs must match the patterns in the shared contract."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from etl.ids import PREFIXES, make_id, new_ulid

COMMON = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "v1" / "common.schema.json").read_text(encoding="utf-8"))["$defs"]
PATTERN_BY_PREFIX = {
    "co": COMMON["company_id"]["pattern"],
    "pt": COMMON["participation_id"]["pattern"],
    "src": COMMON["source_id"]["pattern"],
    "run": COMMON["crawl_run_id"]["pattern"],
    "chg": COMMON["change_id"]["pattern"],
}
ZERO = bytes(10)
ONES = b"\xff" * 10


def test_every_prefix_has_a_contract_pattern_and_vice_versa() -> None:
    assert set(PATTERN_BY_PREFIX) == set(PREFIXES)


@pytest.mark.parametrize("prefix", sorted(PREFIXES))
def test_generated_ids_match_the_contract_pattern(prefix: str) -> None:
    for _ in range(200):
        assert re.fullmatch(PATTERN_BY_PREFIX[prefix], make_id(prefix))


@pytest.mark.parametrize("now_ms, rand", [(0, ZERO), (0, lambda n: ONES), (2**48 - 1, lambda n: ONES), (1_700_000_000_000, lambda n: ZERO)])
def test_extreme_values_still_match_the_pattern(now_ms: int, rand) -> None:
    if isinstance(rand, bytes):
        value = rand
        rand = lambda n: value  # noqa: E731
    ulid = new_ulid(now_ms=now_ms, rand=rand)
    assert re.fullmatch(r"[0-7][0-9A-HJKMNP-TV-Z]{25}", ulid)


def test_known_value_is_encoded_correctly() -> None:
    assert new_ulid(now_ms=0, rand=lambda n: ZERO) == "0" * 26
    assert new_ulid(now_ms=0, rand=lambda n: ONES) == "0" * 10 + "Z" * 16  # 80 random bits = 16 chars of 5 bits
    assert new_ulid(now_ms=1, rand=lambda n: ZERO) == "0" * 9 + "1" + "0" * 16  # 1 ms = 2^80 = one unit at char 10 from the right


def test_later_timestamps_sort_later() -> None:
    ids = [new_ulid(now_ms=ms, rand=lambda n: ZERO) for ms in (1, 2, 1000, 10**12, 2**47)]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)


def test_same_millisecond_ids_differ_because_of_the_random_part() -> None:
    assert len({new_ulid(now_ms=5) for _ in range(500)}) == 500


def test_output_is_deterministic_with_injected_clock_and_randomness() -> None:
    rand = lambda n: bytes(range(n))  # noqa: E731
    assert make_id("src", now_ms=1234, rand=rand) == make_id("src", now_ms=1234, rand=rand)


def test_the_default_clock_is_close_to_now() -> None:
    import time

    ulid = new_ulid()
    decoded = 0
    for char in ulid[:10]:
        decoded = decoded * 32 + "0123456789ABCDEFGHJKMNPQRSTVWXYZ".index(char)
    assert abs(decoded - time.time() * 1000) < 5_000


@pytest.mark.parametrize("bad", [-1, 2**48, 1.5, True, "1"])
def test_invalid_timestamps_are_rejected(bad) -> None:
    with pytest.raises(ValueError):
        new_ulid(now_ms=bad)


def test_wrong_random_length_and_unknown_prefix_are_rejected() -> None:
    with pytest.raises(ValueError, match="10 bytes"):
        new_ulid(rand=lambda n: b"\x00" * 9)
    for prefix in ("", "company", "SRC", "x"):
        with pytest.raises(ValueError, match="unknown ID prefix"):
            make_id(prefix)
