"""Assemble a data package (D2-11): records + manifest + source index, checked by the project's validator.

Takes what earlier steps produced (``etl.build_records`` companies/participations, the sources and crawl-run
records that ``crawler.store`` saved) and writes ``<root>/<exhibition_id>/<year>/<dataset_id>/`` in the
format of ``docs/specs/data-package-contract.md``. Nothing is published unless the package passes the
validator (R1-R11):

1. a unique ``dataset_id`` is derived from the edition and the creation time (never reused: an existing
   directory is an error, packages are immutable);
2. the package is written to a hidden sibling directory;
3. ``etl.validate.validate_package`` runs on it; any finding removes the directory and raises
   ``AssembleError`` with the findings;
4. only then is it renamed into place (atomic on one filesystem).

Completeness is computed, never asserted (contract §9): ``complete`` only when the caller supplies an
official count **with its source** and it equals the number of listed participations; ``partial`` when it
differs; ``unknown`` when there is no official count. Nothing is estimated.
"""
from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from etl.package import PackageError, package_path, read_manifest, write_package
from etl.schema_registry import SchemaSet
from etl.validate import Finding, validate_package


class AssembleError(Exception):
    def __init__(self, message: str, findings: Sequence[Finding] = ()) -> None:
        super().__init__(message)
        self.findings = list(findings)


@dataclass(frozen=True)
class OfficialCount:
    """The organizer's own published exhibitor count, with the source it came from."""

    count: int
    source_id: str
    as_of: date | None = None


@dataclass(frozen=True)
class AssembledPackage:
    path: Path
    manifest: dict[str, Any]


def dataset_id_for(edition_id: str, created_at: datetime) -> str:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise AssembleError("created_at must be timezone-aware")
    return f"{edition_id}.{created_at.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"


def load_run(run_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(source records, crawl_run record) of a run directory written by ``crawler.store`` (D2-06)."""
    directory = Path(run_dir)
    try:
        crawl_run = json.loads((directory / "crawl_run.json").read_text(encoding="utf-8"))
        sources = [json.loads(line) for line in (directory / "sources.jsonl").read_text(encoding="utf-8").splitlines() if line]
    except (OSError, ValueError) as exc:
        raise AssembleError(f"cannot read run {directory}: {exc}") from None
    return sources, crawl_run


def compute_completeness(participations: Iterable[Mapping[str, Any]], official: OfficialCount | None, source_ids: set[str]) -> tuple[str, dict[str, Any]]:
    collected = sum(1 for p in participations if p.get("listing_status") == "listed")
    if official is None:
        return "unknown", {"official_exhibitor_count": None, "official_count_source_id": None, "collected_participation_count": collected}
    if official.source_id not in source_ids:
        raise AssembleError(f"the official count's source {official.source_id} is not among the package's sources")
    if isinstance(official.count, bool) or not isinstance(official.count, int) or official.count < 0:
        raise AssembleError("official count must be a non-negative integer")
    completeness: dict[str, Any] = {"official_exhibitor_count": official.count, "official_count_source_id": official.source_id, "collected_participation_count": collected}
    if official.as_of is not None:
        completeness["official_count_as_of"] = official.as_of.isoformat()
    return ("complete" if collected == official.count else "partial"), completeness


def assemble_package(
    output_root: str | Path,
    *,
    exhibition: Mapping[str, Any],
    edition: Mapping[str, Any],
    companies: Sequence[Mapping[str, Any]],
    participations: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    crawl_runs: Sequence[Mapping[str, Any]],
    data_origin: str,
    producer: Mapping[str, Any],
    created_at: datetime,
    previous_dataset_id: str | None = None,
    changes: Sequence[Mapping[str, Any]] = (),
    official_count: OfficialCount | None = None,
    notes: str | None = None,
    schemas: SchemaSet | None = None,
) -> AssembledPackage:
    schemas = schemas or SchemaSet()
    edition_id, exhibition_id, year = edition.get("edition_id"), edition.get("exhibition_id"), edition.get("year")
    if not (isinstance(edition_id, str) and isinstance(exhibition_id, str) and isinstance(year, int)):
        raise AssembleError("edition must carry edition_id, exhibition_id and year")
    dataset_id = dataset_id_for(edition_id, created_at)
    final = package_path(output_root, exhibition_id, year, dataset_id)
    if final.exists():
        raise AssembleError(f"{final} already exists; packages are immutable. Create a new package with a later created_at")
    wrong = sorted({p.get("edition_id") for p in participations if p.get("edition_id") != edition_id}, key=str)
    if wrong:
        raise AssembleError(f"participations of another edition: {wrong}")

    status, completeness = compute_completeness(participations, official_count, {s["source_id"] for s in sources})
    manifest: dict[str, Any] = {
        "schema_version": schemas.version,
        "dataset_id": dataset_id,
        "exhibition_id": exhibition_id,
        "edition_id": edition_id,
        "edition_year": year,
        "created_at": created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_origin": data_origin,
        "producer": dict(producer),
        "previous_dataset_id": previous_dataset_id,
        "completeness_status": status,
        "completeness": completeness,
    }
    if notes:
        manifest["notes"] = notes

    hidden = final.parent / f".assembling-{dataset_id}"
    if hidden.exists():
        shutil.rmtree(hidden)  # leftover of a crashed earlier attempt; it was never published
    try:
        write_package(
            hidden,
            exhibition=exhibition,
            edition=edition,
            records={"companies": companies, "participations": participations, "sources": sources, "crawl_runs": crawl_runs, "changes": changes},
            manifest=manifest,
        )
        report = validate_package(hidden, schema_dir=schemas.directory)
        if not report.ok:
            raise AssembleError(f"the assembled package is invalid ({len(report.findings)} finding(s)); nothing was published", report.findings)
        if final.exists():
            raise AssembleError(f"{final} already exists; packages are immutable")
        os.rename(hidden, final)
    except PackageError as exc:
        raise AssembleError(str(exc)) from exc
    finally:
        shutil.rmtree(hidden, ignore_errors=True)
    return AssembledPackage(final, read_manifest(final / "manifest.json"))
