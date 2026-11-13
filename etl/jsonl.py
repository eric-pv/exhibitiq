"""Canonical JSON / JSONL serialization and strict reading (D1-04).

Implements ``docs/specs/data-package-contract.md`` §5:

- UTF-8 without BOM, LF line endings, every line (including the last) ends with ``\\n``.
- A line is ``json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))``.
- JSONL records are sorted by primary key in UTF-8 byte order; keys are unique.
- An empty JSONL file is zero bytes.

Same input, same bytes: that is what makes ``content_hash`` reproducible.
Field definitions live only in ``schemas/``; this module knows no fields except
the primary-key name a caller passes in.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

_BOM = b"\xef\xbb\xbf"


class JsonlError(ValueError):
    """Serialization or parsing violated the package serialization rules."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate object key {key!r}")
        obj[key] = value
    return obj


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def loads_strict(text: str) -> Any:
    """``json.loads`` that rejects duplicate object keys and NaN/Infinity (raises ``ValueError``)."""
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)


def canonical_line(record: Mapping[str, Any]) -> str:
    """One canonical JSON line, including the trailing newline."""
    try:
        return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise JsonlError(f"record cannot be serialized as canonical JSON: {exc}") from exc


def _encode(text: str) -> bytes:
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise JsonlError(f"text is not valid UTF-8: {exc}") from exc


def serialize_single(record: Mapping[str, Any]) -> bytes:
    """Bytes of a single-record ``.json`` file (``exhibition.json``, ``edition.json``)."""
    if not isinstance(record, Mapping):
        raise JsonlError("record must be an object")
    return _encode(canonical_line(record))


def serialize_records(records: Iterable[Mapping[str, Any]], key: str) -> bytes:
    """Bytes of a JSONL file: canonical lines sorted by ``key`` (UTF-8 byte order), keys unique."""
    items: list[tuple[bytes, str]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise JsonlError(f"record {index} is not an object")
        value = record.get(key)
        if not isinstance(value, str) or not value:
            raise JsonlError(f"record {index} has no usable primary key {key!r}")
        if value in seen:
            raise JsonlError(f"duplicate primary key {key}={value!r}")
        seen.add(value)
        items.append((_encode(value), canonical_line(record)))
    items.sort(key=lambda item: item[0])
    return _encode("".join(line for _, line in items))


def parse_jsonl_bytes(data: bytes, *, name: str = "<bytes>", require_canonical: bool = False) -> list[dict[str, Any]]:
    """Strictly parse JSONL bytes. Rejects BOM, CR, blank lines, a missing final newline,
    non-object lines, duplicate object keys and NaN/Infinity. With ``require_canonical`` a
    line must also be byte-identical to its canonical form."""
    if data.startswith(_BOM):
        raise JsonlError(f"{name}: file starts with a UTF-8 BOM")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JsonlError(f"{name}: not valid UTF-8: {exc}") from exc
    if "\r" in text:
        raise JsonlError(f"{name}: contains CR; only LF line endings are allowed")
    if text == "":
        return []
    if not text.endswith("\n"):
        raise JsonlError(f"{name}: missing newline at end of file")
    records: list[dict[str, Any]] = []
    for number, line in enumerate(text[:-1].split("\n"), start=1):
        if line == "":
            raise JsonlError(f"{name}:{number}: blank line")
        try:
            obj = loads_strict(line)
        except ValueError as exc:
            raise JsonlError(f"{name}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise JsonlError(f"{name}:{number}: line is not a JSON object")
        if require_canonical and canonical_line(obj) != line + "\n":
            raise JsonlError(f"{name}:{number}: line is not in canonical form")
        records.append(obj)
    return records


def read_jsonl(path: str | Path, *, require_canonical: bool = False) -> list[dict[str, Any]]:
    path = Path(path)
    return parse_jsonl_bytes(path.read_bytes(), name=str(path), require_canonical=require_canonical)


def read_single(path: str | Path, *, require_canonical: bool = False) -> dict[str, Any]:
    """Read a single-record ``.json`` file: exactly one canonical-format line."""
    path = Path(path)
    records = parse_jsonl_bytes(path.read_bytes(), name=str(path), require_canonical=require_canonical)
    if len(records) != 1:
        raise JsonlError(f"{path}: expected exactly 1 record, found {len(records)}")
    return records[0]
