"""Read and write data packages (D1-04).

A data package is a directory of 8 files (``docs/specs/data-package-contract.md`` §3):
``manifest.json`` plus 7 data files. This module writes them byte-reproducibly
(§5), computes the integrity fields of the manifest (§6), and reads them back
strictly. It does **not** validate records against the Schema: the single
validator (R1-R11) is D1-05 and loads ``schemas/v1/``.

The file-name layout and primary-key names below come from the contract text
(§3, §5), not from Schema field definitions. If the contract changes, change
them here together with the tests, which compare against the contract's own
example package.

Packages are immutable (§3): ``write_package`` never overwrites an existing
directory, and writes through a temporary directory so a failure leaves nothing
half-written.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etl.hashing import content_hash, sha256_of_bytes
from etl.jsonl import loads_strict, read_jsonl, read_single, serialize_records, serialize_single

MANIFEST_FILE = "manifest.json"
EXHIBITION_FILE = "exhibition.json"
EDITION_FILE = "edition.json"

# short name -> (file name, primary key). Sorted order of the data files is byte order of the file names.
RECORD_SETS: dict[str, tuple[str, str]] = {
    "companies": ("companies.jsonl", "company_id"),
    "participations": ("participations.jsonl", "participation_id"),
    "sources": ("sources.jsonl", "source_id"),
    "crawl_runs": ("crawl_runs.jsonl", "crawl_run_id"),
    "changes": ("changes.jsonl", "change_id"),
}
DATA_FILES: tuple[str, ...] = tuple(
    sorted([EXHIBITION_FILE, EDITION_FILE, *(name for name, _ in RECORD_SETS.values())], key=lambda n: n.encode("utf-8"))
)
# Manifest fields that this module computes; callers must not supply them.
COMPUTED_MANIFEST_FIELDS = frozenset({"files", "record_counts", "content_hash"})


class PackageError(ValueError):
    """The package is missing files, is malformed, or cannot be written safely."""


def package_path(root: str | Path, exhibition_id: str, edition_year: int, dataset_id: str) -> Path:
    """``<root>/<exhibition_id>/<edition_year>/<dataset_id>/`` (contract §3)."""
    for label, part in (("exhibition_id", exhibition_id), ("dataset_id", dataset_id)):
        if not isinstance(part, str) or not part or part in {".", ".."} or "/" in part or "\\" in part or "\x00" in part:
            raise PackageError(f"{label} is not safe to use as a directory name: {part!r}")
    if isinstance(edition_year, bool) or not isinstance(edition_year, int) or not 1000 <= edition_year <= 9999:
        raise PackageError(f"edition_year must be a four-digit year: {edition_year!r}")
    return Path(root) / exhibition_id / str(edition_year) / dataset_id


def compute_integrity(package_dir: str | Path) -> dict[str, Any]:
    """The manifest's ``files``, ``record_counts`` and ``content_hash``, computed from the bytes on disk."""
    package_dir = Path(package_dir)
    missing = [name for name in DATA_FILES if not (package_dir / name).is_file()]
    if missing:
        raise PackageError(f"{package_dir}: missing data files: {', '.join(missing)}")
    files: dict[str, dict[str, Any]] = {}
    for name in DATA_FILES:
        data = (package_dir / name).read_bytes()
        if name.endswith(".jsonl"):
            if data and not data.endswith(b"\n"):
                raise PackageError(f"{package_dir / name}: missing newline at end of file")
            records = data.count(b"\n")
        else:
            records = 1
        files[name] = {"sha256": sha256_of_bytes(data), "bytes": len(data), "records": records}
    return {
        "files": files,
        "record_counts": {short: files[name]["records"] for short, (name, _) in RECORD_SETS.items()},
        "content_hash": content_hash({name: entry["sha256"] for name, entry in files.items()}),
    }


def write_manifest(path: str | Path, manifest: Mapping[str, Any]) -> None:
    """``manifest.json``: indent 2, sorted keys, UTF-8, LF, trailing newline (format is free; §5)."""
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    Path(path).write_bytes(text.encode("utf-8"))


def read_manifest(path: str | Path) -> dict[str, Any]:
    """Read ``manifest.json``; rejects duplicate keys and NaN/Infinity."""
    path = Path(path)
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise PackageError(f"{path}: file starts with a UTF-8 BOM")
    try:
        obj = loads_strict(data.decode("utf-8"))
    except ValueError as exc:  # includes UnicodeDecodeError
        raise PackageError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise PackageError(f"{path}: manifest must be a JSON object")
    return obj


def write_package(
    output_dir: str | Path,
    *,
    exhibition: Mapping[str, Any],
    edition: Mapping[str, Any],
    records: Mapping[str, Iterable[Mapping[str, Any]]] | None = None,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Write a complete data package to ``output_dir`` and return the final manifest.

    ``records`` maps the short names (``companies``, ``participations``, ``sources``,
    ``crawl_runs``, ``changes``) to records; an omitted set becomes an empty (0-byte) file.
    ``manifest`` holds every manifest field except ``files``, ``record_counts`` and
    ``content_hash``, which are computed from the written bytes. ``source_snapshot_ids`` and
    ``crawl_run_ids`` are derived from the records when omitted, and must match them when given.

    Raises ``PackageError`` if ``output_dir`` already exists (packages are immutable).
    """
    output_dir = Path(output_dir)
    records = dict(records or {})
    unknown = sorted(set(records) - set(RECORD_SETS))
    if unknown:
        raise PackageError(f"unknown record sets: {', '.join(unknown)}")
    forbidden = sorted(COMPUTED_MANIFEST_FIELDS & set(manifest))
    if forbidden:
        raise PackageError(f"manifest fields are computed by write_package, do not supply: {', '.join(forbidden)}")
    if output_dir.exists():
        raise PackageError(f"{output_dir} already exists; data packages are immutable")

    materialized = {short: list(records.get(short, ())) for short in RECORD_SETS}
    payloads: dict[str, bytes] = {
        EXHIBITION_FILE: serialize_single(exhibition),
        EDITION_FILE: serialize_single(edition),
    }
    for short, (name, key) in RECORD_SETS.items():
        payloads[name] = serialize_records(materialized[short], key)

    final_manifest = dict(manifest)
    for field, short in (("source_snapshot_ids", "sources"), ("crawl_run_ids", "crawl_runs")):
        key = RECORD_SETS[short][1]
        derived = sorted(record[key] for record in materialized[short])
        if field in final_manifest:
            if sorted(final_manifest[field]) != derived:
                raise PackageError(f"manifest {field} does not match the {short} records")
        else:
            final_manifest[field] = derived

    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=parent))
    try:
        os.chmod(staging, 0o755)
        for name, data in payloads.items():
            (staging / name).write_bytes(data)
        final_manifest.update(compute_integrity(staging))
        write_manifest(staging / MANIFEST_FILE, final_manifest)
        if output_dir.exists():
            raise PackageError(f"{output_dir} already exists; data packages are immutable")
        os.rename(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final_manifest


@dataclass(frozen=True)
class Package:
    manifest: dict[str, Any]
    exhibition: dict[str, Any]
    edition: dict[str, Any]
    records: dict[str, list[dict[str, Any]]]


def read_package(package_dir: str | Path, *, require_canonical: bool = False) -> Package:
    """Read a package strictly (serialization only; semantic validation is D1-05)."""
    package_dir = Path(package_dir)
    absent = [name for name in (MANIFEST_FILE, *DATA_FILES) if not (package_dir / name).is_file()]
    if absent:
        raise PackageError(f"{package_dir}: missing files: {', '.join(absent)}")
    return Package(
        manifest=read_manifest(package_dir / MANIFEST_FILE),
        exhibition=read_single(package_dir / EXHIBITION_FILE, require_canonical=require_canonical),
        edition=read_single(package_dir / EDITION_FILE, require_canonical=require_canonical),
        records={
            short: read_jsonl(package_dir / name, require_canonical=require_canonical)
            for short, (name, _) in RECORD_SETS.items()
        },
    )


class SourceIndex:
    """Lookup of source records by ``source_id`` (from ``sources.jsonl``), for reference checks."""

    _KEY = RECORD_SETS["sources"][1]

    def __init__(self, records: Iterable[Mapping[str, Any]]) -> None:
        self._by_id: dict[str, Mapping[str, Any]] = {}
        for index, record in enumerate(records):
            source_id = record.get(self._KEY)
            if not isinstance(source_id, str) or not source_id:
                raise PackageError(f"source record {index} has no usable {self._KEY!r}")
            if source_id in self._by_id:
                raise PackageError(f"duplicate {self._KEY}: {source_id!r}")
            self._by_id[source_id] = record

    @classmethod
    def from_file(cls, path: str | Path) -> "SourceIndex":
        return cls(read_jsonl(path))

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._by_id

    def __getitem__(self, source_id: str) -> Mapping[str, Any]:
        return self._by_id[source_id]

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._by_id, key=lambda s: s.encode("utf-8")))

    def ids(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def missing(self, source_ids: Iterable[str]) -> list[str]:
        """The given IDs that are not in the index, sorted and de-duplicated."""
        return sorted({s for s in source_ids if s not in self._by_id}, key=lambda s: s.encode("utf-8"))
