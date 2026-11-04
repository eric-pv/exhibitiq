"""Persisting a crawl run's evidence (D2-06): snapshots, the run record, the log and the source records.

Layout, one directory per run, never reused::

    <root>/<exhibition_id>/<edition_id>/<crawl_run_id>/
        snapshots/<source_id>.<ext>   the raw bytes, exactly as received (immutable)
        sources.jsonl                 one schema-valid ``source`` record per snapshot, sorted by source_id
        crawl_run.json                the ``crawl_run`` record (shared contract)
        run.log.jsonl                 the event log of D1-07
        errors.json                   every error of the run (``crawl_run.error_samples`` keeps only 50)

Rules:

- **Immutable:** files are created exclusively; an existing file is never overwritten (a second write
  is an error). A run directory is finalized once.
- **Evidence first:** each snapshot is written the moment it is received (``RunStore.save`` is the
  runner's ``SnapshotSink``), so a crash later in the run does not lose what was already retrieved.
  The hash is re-checked from the bytes before writing.
- **Git is not a bulk store:** a snapshot larger than ``max_stored_bytes`` is *not stored*. Its
  ``source`` record says so (``snapshot.storage = "not_stored"`` with a note) and still carries the
  sha256, so the retrieved content can be verified if it is supplied again. Raise the limit or
  choose another storage deliberately; do not commit large files by accident.
- Locators are paths relative to ``root`` using ``/``; the ``source`` record's ``locator`` is that path
  prefixed with ``root_label`` (default ``data/raw``) so it is correct from the repository root.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from crawler.models import Snapshot
from crawler.runner import RunResult
from crawler.source_config import SourceConfig
from etl.hashing import sha256_of_bytes
from etl.jsonl import serialize_records

_ID = re.compile(r"^(src|run)_[0-7][0-9A-HJKMNP-TV-Z]{25}$")
_SEGMENT = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_EXTENSIONS = {
    "text/html": ".html", "application/xhtml+xml": ".html", "text/csv": ".csv", "application/pdf": ".pdf", "application/json": ".json",
    "application/xml": ".xml", "text/xml": ".xml", "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
DEFAULT_MAX_STORED_BYTES = 5 * 1024 * 1024


class StoreError(Exception):
    """The store was asked to do something unsafe (overwrite, bad ID, finalize twice)."""


def extension_for(media_type: str | None) -> str:
    return _EXTENSIONS.get((media_type or "").lower(), ".bin")


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError:
        raise StoreError(f"{path.name} already exists; stored evidence is immutable") from None


class RunStore:
    """The ``SnapshotSink`` for one run of one source, plus ``finalize`` for everything else."""

    def __init__(self, root: str | Path, config: SourceConfig, *, max_stored_bytes: int = DEFAULT_MAX_STORED_BYTES, root_label: str = "data/raw") -> None:
        for label, value in (("exhibition_id", config.exhibition_id), ("edition_id", config.edition_id)):
            if not _SEGMENT.fullmatch(value):
                raise StoreError(f"{label} {value!r} cannot be used as a directory name")
        if isinstance(max_stored_bytes, bool) or not isinstance(max_stored_bytes, int) or max_stored_bytes < 0:
            raise StoreError("max_stored_bytes must be a non-negative integer")
        self.root = Path(root)
        self.config = config
        self.max_stored_bytes = max_stored_bytes
        self.root_label = root_label.strip("/")
        self._saved: dict[str, str | None] = {}  # source_id -> relative locator (None = not stored)
        self._finalized = False

    # ------------------------------------------------------------------ paths
    def run_dir(self, crawl_run_id: str) -> Path:
        if not _ID.fullmatch(crawl_run_id) or not crawl_run_id.startswith("run_"):
            raise StoreError(f"invalid crawl_run_id {crawl_run_id!r}")
        return self.root / self.config.exhibition_id / self.config.edition_id / crawl_run_id

    def _relative(self, crawl_run_id: str, source_id: str, media_type: str | None) -> str:
        return f"{self.config.exhibition_id}/{self.config.edition_id}/{crawl_run_id}/snapshots/{source_id}{extension_for(media_type)}"

    # ------------------------------------------------------------------ SnapshotSink
    def save(self, snapshot: Snapshot) -> None:
        if self._finalized:
            raise StoreError("this run is already finalized")
        if not _ID.fullmatch(snapshot.source_id) or not snapshot.source_id.startswith("src_"):
            raise StoreError(f"invalid source_id {snapshot.source_id!r}")
        if snapshot.source_id in self._saved:
            raise StoreError(f"{snapshot.source_id} was already saved")
        if sha256_of_bytes(snapshot.content) != snapshot.content_sha256 or len(snapshot.content) != snapshot.size:
            raise StoreError(f"{snapshot.source_id}: content does not match its recorded sha256/size; refusing to store")
        if len(snapshot.content) > self.max_stored_bytes:
            self._saved[snapshot.source_id] = None
            return
        relative = self._relative(snapshot.crawl_run_id, snapshot.source_id, snapshot.media_type)
        self.run_dir(snapshot.crawl_run_id)  # validates the run id
        _write_new(self.root / relative, snapshot.content)
        self._saved[snapshot.source_id] = relative

    # ------------------------------------------------------------------ source records
    def source_record(self, snapshot: Snapshot) -> dict[str, Any]:
        """The schema-valid ``source`` record for a saved snapshot."""
        if snapshot.source_id not in self._saved:
            raise StoreError(f"{snapshot.source_id} was not saved through this store")
        relative = self._saved[snapshot.source_id]
        record: dict[str, Any] = {
            "source_id": snapshot.source_id,
            "source_type": self.config.source_type,
            "url": snapshot.url,
            "retrieved_at": snapshot.retrieved_at,
            "crawl_run_id": snapshot.crawl_run_id,
            "content_sha256": snapshot.content_sha256,
            "http_status": snapshot.http_status,
        }
        if snapshot.media_type and re.fullmatch(r"[a-z]+/[a-z0-9.+-]+", snapshot.media_type):
            record["media_type"] = snapshot.media_type
        notes: list[str] = []
        if snapshot.final_url != snapshot.url:
            notes.append(f"redirected to {snapshot.final_url}")
        if relative is None:
            record["snapshot"] = {"storage": "not_stored"}
            notes.append(f"raw content ({snapshot.size} bytes) was not stored: it exceeds max_stored_bytes ({self.max_stored_bytes}); only its sha256 is kept")
        else:
            record["snapshot"] = {"storage": "git", "locator": f"{self.root_label}/{relative}"}
        if notes:
            record["notes"] = "; ".join(notes)[:4000]
        return record

    # ------------------------------------------------------------------ finalize
    def finalize(self, result: RunResult) -> Path:
        """Write the run record, log, errors and source records. Returns the run directory."""
        if self._finalized:
            raise StoreError("this run is already finalized")
        crawl_run_id = result.crawl_run["crawl_run_id"]
        directory = self.run_dir(crawl_run_id)
        missing = [s.source_id for s in result.snapshots if s.source_id not in self._saved]
        if missing:
            raise StoreError(f"snapshot(s) were never saved: {', '.join(missing)}; pass the store to the runner as sink=")
        if (directory / "crawl_run.json").exists():
            raise StoreError(f"{crawl_run_id} is already finalized on disk")
        _write_new(directory / "sources.jsonl", serialize_records((self.source_record(s) for s in result.snapshots), "source_id"))
        errors = [
            {k: v for k, v in {"code": str(e.code), "message": e.message, "url": e.url, "occurred_at": e.occurred_at, "http_status": e.http_status, "retryable": e.retryable}.items() if v is not None}
            for e in result.errors
        ]
        _write_new(directory / "errors.json", (json.dumps(errors, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        _write_new(directory / "run.log.jsonl", result.log_text.encode("utf-8"))
        # the run record goes last: its presence means "this run directory is complete"
        _write_new(directory / "crawl_run.json", (json.dumps(result.crawl_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        self._finalized = True
        return directory


def verify_run(run_dir: str | Path) -> list[str]:
    """Check a stored run directory; returns problems (empty = intact). Re-hashes every stored snapshot."""
    directory = Path(run_dir)
    problems: list[str] = []
    for name in ("crawl_run.json", "sources.jsonl", "errors.json", "run.log.jsonl"):
        if not (directory / name).is_file():
            problems.append(f"missing {name}")
    sources_file = directory / "sources.jsonl"
    if not sources_file.is_file():
        return problems
    stored: set[str] = set()
    for number, line in enumerate(sources_file.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
            storage = record["snapshot"]["storage"]
            source_id, expected = record["source_id"], record["content_sha256"]
        except (ValueError, KeyError, TypeError):
            problems.append(f"sources.jsonl line {number} is not a source record")
            continue
        if storage == "not_stored":
            continue
        files = list((directory / "snapshots").glob(source_id + ".*"))
        if len(files) != 1:
            problems.append(f"{source_id}: expected one snapshot file, found {len(files)}")
            continue
        stored.add(files[0].name)
        if sha256_of_bytes(files[0].read_bytes()) != expected:
            problems.append(f"{source_id}: content does not match its sha256")
    snapshots = directory / "snapshots"
    if snapshots.is_dir():
        for path in sorted(snapshots.iterdir()):
            if path.name not in stored:
                problems.append(f"{path.name}: snapshot file without a source record")
    return problems


__all__ = ["DEFAULT_MAX_STORED_BYTES", "RunStore", "StoreError", "extension_for", "verify_run"]
