"""Data carried through a crawl (D2-01).

These are plain, immutable values. They hold no exhibition-specific knowledge:
``ExtractedRecord.data`` is whatever an adapter extracted "as listed"; mapping it
into schema fields is the ETL's job (D2-07), driven by mapping configuration.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Request:
    """A request for one URL. Only ``GET`` exists on purpose: acquisition never changes anything remotely."""

    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)  # adapter bookkeeping, e.g. {"page": 2}


@dataclass(frozen=True)
class Response:
    url: str  # the URL that was requested
    final_url: str  # after redirects (each hop was checked against allowed_domains)
    status: int
    headers: Mapping[str, str]  # lower-case header names
    content: bytes
    media_type: str | None = None  # Content-Type without parameters, lower-case


@dataclass(frozen=True)
class Snapshot:
    """The raw bytes of one successful response, with the provenance the contract asks for (§4, §6).

    ``content_sha256`` is ``sha256:`` plus 64 hex characters of the **unparsed** bytes. ``source_id`` and
    ``crawl_run_id`` are assigned at acquisition time (contract §2). Persisting snapshots (to Git, a
    Release, ...) is D2-06, which fills the ``snapshot`` part of a ``source`` record.
    """

    source_id: str
    crawl_run_id: str
    url: str
    final_url: str
    retrieved_at: str  # UTC RFC 3339, ends with Z
    http_status: int
    media_type: str | None
    content_sha256: str
    size: int
    content: bytes


@dataclass(frozen=True)
class ExtractedRecord:
    """One raw record from one page, tied back to the snapshot it came from."""

    data: Mapping[str, Any]
    url: str
    source_id: str  # the Snapshot it was extracted from
    snapshot_sha256: str


@dataclass
class ParseResult:
    """What an adapter returns for one response."""

    records: list[Mapping[str, Any]] = field(default_factory=list)
    follow: list[Request] = field(default_factory=list)  # further pages to fetch (pagination, detail pages)
    warnings: list[str] = field(default_factory=list)
