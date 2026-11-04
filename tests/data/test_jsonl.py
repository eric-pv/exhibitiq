"""Tests for etl.jsonl (D1-04): canonical serialization and strict reading."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from etl.jsonl import (
    JsonlError,
    canonical_line,
    parse_jsonl_bytes,
    read_jsonl,
    read_single,
    serialize_records,
    serialize_single,
)


def test_canonical_line_matches_the_contract_expression() -> None:
    record = {"b": 1, "a": "中文é", "c": [1, {"z": None, "y": True}]}
    expected = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    assert canonical_line(record) == expected
    assert expected == '{"a":"中文é","b":1,"c":[1,{"y":true,"z":null}]}\n'


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_canonical_line_rejects_nan_and_infinity(bad: float) -> None:
    with pytest.raises(JsonlError):
        canonical_line({"x": bad})


def test_serialize_records_sorts_by_key_in_utf8_byte_order() -> None:
    records = [{"id": "b"}, {"id": "B"}, {"id": "a"}, {"id": "é"}, {"id": "Z"}]
    out = serialize_records(records, "id").decode("utf-8").splitlines()
    assert [json.loads(line)["id"] for line in out] == ["B", "Z", "a", "b", "é"]  # byte order, not locale


def test_serialize_records_is_independent_of_input_order() -> None:
    a = [{"id": "x", "v": 1}, {"id": "y", "v": 2}]
    assert serialize_records(a, "id") == serialize_records(reversed(a), "id")


def test_empty_jsonl_is_zero_bytes() -> None:
    assert serialize_records([], "id") == b""
    assert parse_jsonl_bytes(b"") == []


@pytest.mark.parametrize(
    "records, fragment",
    [
        ([{"id": "a"}, {"id": "a"}], "duplicate primary key"),
        ([{"other": "a"}], "primary key"),
        ([{"id": ""}], "primary key"),
        ([{"id": 7}], "primary key"),
        (["not an object"], "not an object"),
    ],
)
def test_serialize_records_rejects_bad_input(records: list, fragment: str) -> None:
    with pytest.raises(JsonlError, match=fragment):
        serialize_records(records, "id")


def test_lone_surrogate_is_rejected() -> None:
    with pytest.raises(JsonlError):
        serialize_single({"x": "\ud800"})


def test_serialize_single_is_one_canonical_line() -> None:
    assert serialize_single({"b": 1, "a": 2}) == b'{"a":2,"b":1}\n'


def test_round_trip_and_require_canonical() -> None:
    records = [{"id": "a", "n": 1}, {"id": "b", "n": 2}]
    data = serialize_records(records, "id")
    assert parse_jsonl_bytes(data, require_canonical=True) == records


@pytest.mark.parametrize(
    "data, fragment",
    [
        (b"\xef\xbb\xbf" + b'{"a":1}\n', "BOM"),
        (b'{"a":1}\r\n', "CR"),
        (b'{"a":1}', "missing newline"),
        (b'{"a":1}\n\n{"b":2}\n', "blank line"),
        (b'\xff\xfe\n', "UTF-8"),
        (b"[1,2]\n", "not a JSON object"),
        (b'{"a":1,"a":2}\n', "duplicate object key"),
        (b'{"a":NaN}\n', "NaN"),
        (b'{"a":\n', "invalid JSON"),
    ],
)
def test_strict_reader_rejects_malformed_files(data: bytes, fragment: str) -> None:
    with pytest.raises(JsonlError, match=fragment):
        parse_jsonl_bytes(data, name="f.jsonl")


def test_error_messages_carry_file_and_line_number() -> None:
    with pytest.raises(JsonlError, match=r"f\.jsonl:2:"):
        parse_jsonl_bytes(b'{"a":1}\n[1]\n', name="f.jsonl")


def test_require_canonical_rejects_valid_but_non_canonical_lines() -> None:
    data = b'{"b": 1, "a": 2}\n'
    assert parse_jsonl_bytes(data) == [{"b": 1, "a": 2}]
    with pytest.raises(JsonlError, match="not in canonical form"):
        parse_jsonl_bytes(data, require_canonical=True)


def test_read_single_requires_exactly_one_record(tmp_path: Path) -> None:
    one = tmp_path / "one.json"
    one.write_bytes(b'{"a":1}\n')
    assert read_single(one) == {"a": 1}
    two = tmp_path / "two.json"
    two.write_bytes(b'{"a":1}\n{"a":2}\n')
    with pytest.raises(JsonlError, match="exactly 1 record"):
        read_single(two)
    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")
    with pytest.raises(JsonlError, match="exactly 1 record"):
        read_single(empty)


def test_read_jsonl_from_file(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_bytes(serialize_records([{"id": "a"}], "id"))
    assert read_jsonl(path, require_canonical=True) == [{"id": "a"}]
