"""The data-package validator (D1-05): the single implementation of rules R1-R11.

Rules are those of ``docs/specs/data-package-contract.md`` §12. Structure comes
from the Schema files in ``schemas/v1/`` (loaded locally, never over the
network); this module adds only the cross-record rules a Schema cannot express.

Design:
- It never raises on a bad package: every problem becomes a ``Finding`` with its
  rule number, file and (when known) line. All findings are reported, not just
  the first.
- It checks serialization and structure only. It does not judge whether data is
  true, and knows no specific exhibition.
- If any of the 8 files is missing (R1) the remaining rules cannot run and are
  skipped.

Command line: ``python -m etl.validate <package_dir> [--schemas DIR] [--json]``;
exit code 0 = valid, 1 = violations found, 2 = could not run (e.g. schemas missing).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etl.jsonl import JsonlError, canonical_line, parse_jsonl_bytes
from etl.package import (
    DATA_FILES,
    EDITION_FILE,
    EXHIBITION_FILE,
    MANIFEST_FILE,
    RECORD_SETS,
    PackageError,
    compute_integrity,
    read_manifest,
)
from etl.schema_registry import SchemaError, SchemaSet

# Schema entity (file name stem in schemas/v1/) for each package file.
SINGLE_ENTITIES = {EXHIBITION_FILE: "exhibition", EDITION_FILE: "edition"}
RECORD_ENTITIES = {
    "companies": "company",
    "participations": "participation",
    "sources": "source",
    "crawl_runs": "crawl_run",
    "changes": "change",
}


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str
    file: str | None = None
    line: int | None = None

    def sort_key(self) -> tuple[int, str, int, str]:
        return (int(self.rule[1:]), self.file or "", self.line or 0, self.message)

    def __str__(self) -> str:
        where = ""
        if self.file:
            where = f" {self.file}" + (f":{self.line}" if self.line else "")
        return f"{self.rule}{where}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "file": self.file, "line": self.line, "message": self.message}


@dataclass
class Report:
    package_dir: str
    schema_version: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def rules(self) -> set[str]:
        return {f.rule for f in self.findings}

    def text(self) -> str:
        head = f"{self.package_dir} (schema {self.schema_version})"
        if self.ok:
            return f"OK {head}: all rules R1-R11 passed"
        body = "\n".join(f"  {f}" for f in self.findings)
        return f"INVALID {head}: {len(self.findings)} finding(s)\n{body}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_dir": self.package_dir,
            "schema_version": self.schema_version,
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _source_refs(record: dict[str, Any]) -> set[str]:
    """Every source ID a record cites: ``source_ids``, ``field_sources`` values, alias ``source_ids``."""
    refs = set(_strings(record.get("source_ids")))
    for ids in _dict(record.get("field_sources")).values():
        refs.update(_strings(ids))
    aliases = record.get("aliases")
    if isinstance(aliases, list):
        for alias in aliases:
            refs.update(_strings(_dict(alias).get("source_ids")))
    return refs


class _Run:
    def __init__(self, package_dir: Path, schemas: SchemaSet) -> None:
        self.dir = package_dir
        self.schemas = schemas
        self.findings: list[Finding] = []
        self.manifest: dict[str, Any] | None = None
        self.singles: dict[str, dict[str, Any] | None] = {}
        self.tables: dict[str, list[dict[str, Any]] | None] = {}

    def add(self, rule: str, message: str, file: str | None = None, line: int | None = None) -> None:
        self.findings.append(Finding(rule, message, file, line))

    # ------------------------------------------------------------------ R1-R3
    def r1_files(self) -> bool:
        missing = [name for name in (MANIFEST_FILE, *DATA_FILES) if not (self.dir / name).is_file()]
        for name in missing:
            self.add("R1", "required file is missing", name)
        return not missing

    def r2_r3_manifest(self) -> None:
        try:
            self.manifest = read_manifest(self.dir / MANIFEST_FILE)
        except PackageError as exc:
            self.add("R2", f"manifest cannot be read: {exc}", MANIFEST_FILE)
            return
        for message in self.schemas.errors("manifest", self.manifest):
            self.add("R2", message, MANIFEST_FILE)
        declared = self.manifest.get("schema_version")
        if declared not in self.schemas.accepted:
            accepted = ", ".join(self.schemas.accepted)
            self.add("R3", f"schema_version is {declared!r}, schemas/v1/COMPATIBILITY.json accepts {accepted}", MANIFEST_FILE)

    # --------------------------------------------------------------- R4, R5
    def _load(self, name: str) -> list[dict[str, Any]] | None:
        """Parse one data file; serialization problems are R5 findings (and the file is skipped)."""
        data = (self.dir / name).read_bytes()
        try:
            records = parse_jsonl_bytes(data, name=name)
        except JsonlError as exc:
            self.add("R5", str(exc), name)
            return None
        lines = data.decode("utf-8").split("\n")[:-1] if data else []
        for number, (line, record) in enumerate(zip(lines, records), start=1):
            if canonical_line(record) != line + "\n":
                self.add("R5", "line is not in canonical form (contract §5)", name, number)
        return records

    def r4_r5_records(self) -> None:
        for name, entity in SINGLE_ENTITIES.items():
            records = self._load(name)
            self.singles[name] = None
            if records is None:
                continue
            if len(records) != 1:
                self.add("R4", f"must contain exactly 1 record, found {len(records)}", name)
                continue
            self.singles[name] = records[0]
            for message in self.schemas.errors(entity, records[0]):
                self.add("R4", message, name, 1)
        for short, (name, _) in RECORD_SETS.items():
            records = self._load(name)
            self.tables[short] = records
            if records is None:
                continue
            for number, record in enumerate(records, start=1):
                for message in self.schemas.errors(RECORD_ENTITIES[short], record):
                    self.add("R4", message, name, number)

    # --------------------------------------------------------------- R6, R7
    def r6_keys(self) -> None:
        for short, (name, key) in RECORD_SETS.items():
            records = self.tables.get(short)
            if records is None:
                continue
            seen: set[str] = set()
            previous: bytes | None = None
            unsorted_reported = False
            for number, record in enumerate(records, start=1):
                value = record.get(key)
                if not isinstance(value, str):
                    continue  # reported by R4
                if value in seen:
                    self.add("R6", f"duplicate {key} {value!r}", name, number)
                seen.add(value)
                encoded = value.encode("utf-8")
                if previous is not None and encoded < previous and not unsorted_reported:
                    self.add("R6", f"records are not sorted by {key} in UTF-8 byte order", name, number)
                    unsorted_reported = True
                previous = encoded

    def r7_counts(self) -> None:
        counts = _dict(_dict(self.manifest).get("record_counts"))
        for short, (name, _) in RECORD_SETS.items():
            records = self.tables.get(short)
            if records is not None and counts.get(short) != len(records):
                self.add("R7", f"record_counts.{short} is {counts.get(short)!r}, the file has {len(records)} records", MANIFEST_FILE)

    # ------------------------------------------------------------------ R8
    def r8_integrity(self) -> None:
        try:
            actual = compute_integrity(self.dir)
        except PackageError as exc:
            self.add("R8", f"cannot compute integrity: {exc}")
            return
        manifest = _dict(self.manifest)
        declared_files = _dict(manifest.get("files"))
        for name in DATA_FILES:
            declared = _dict(declared_files.get(name))
            for attribute in ("sha256", "bytes", "records"):
                if declared.get(attribute) != actual["files"][name][attribute]:
                    self.add(
                        "R8",
                        f"files[{name}].{attribute} is {declared.get(attribute)!r}, actual is {actual['files'][name][attribute]!r}",
                        MANIFEST_FILE,
                    )
        if manifest.get("content_hash") != actual["content_hash"]:
            self.add("R8", f"content_hash is {manifest.get('content_hash')!r}, recomputed is {actual['content_hash']!r}", MANIFEST_FILE)

    # ------------------------------------------------------------------ R9
    def r9_identity(self) -> None:
        manifest = _dict(self.manifest)
        exhibition = self.singles.get(EXHIBITION_FILE)
        edition = self.singles.get(EDITION_FILE)
        if exhibition is not None and exhibition.get("exhibition_id") != manifest.get("exhibition_id"):
            self.add("R9", "exhibition_id differs from the manifest", EXHIBITION_FILE)
        if edition is not None:
            if edition.get("edition_id") != manifest.get("edition_id"):
                self.add("R9", "edition_id differs from the manifest", EDITION_FILE)
            if edition.get("exhibition_id") != manifest.get("exhibition_id"):
                self.add("R9", "exhibition_id differs from the manifest", EDITION_FILE)
            if edition.get("year") != manifest.get("edition_year"):
                self.add("R9", "year differs from manifest.edition_year", EDITION_FILE)
        dataset_id, edition_id = manifest.get("dataset_id"), manifest.get("edition_id")
        if not (isinstance(dataset_id, str) and isinstance(edition_id, str) and dataset_id.startswith(edition_id + ".")):
            self.add("R9", "dataset_id must start with '<edition_id>.'", MANIFEST_FILE)

    # ----------------------------------------------------------------- R10
    def _ids(self, short: str) -> set[str] | None:
        records = self.tables.get(short)
        if records is None:
            return None
        key = RECORD_SETS[short][1]
        return {r[key] for r in records if isinstance(r.get(key), str)}

    def r10_references(self) -> None:
        manifest = _dict(self.manifest)
        source_ids, company_ids, run_ids = self._ids("sources"), self._ids("companies"), self._ids("crawl_runs")

        if source_ids is not None and set(_strings(manifest.get("source_snapshot_ids"))) != source_ids:
            self.add("R10", "manifest.source_snapshot_ids differs from the source_id set in sources.jsonl", MANIFEST_FILE)
        if run_ids is not None and set(_strings(manifest.get("crawl_run_ids"))) != run_ids:
            self.add("R10", "manifest.crawl_run_ids differs from the crawl_run_id set in crawl_runs.jsonl", MANIFEST_FILE)

        if source_ids is not None:
            cited: list[tuple[str, int | None, dict[str, Any]]] = []
            for name in (EXHIBITION_FILE, EDITION_FILE):
                if self.singles.get(name) is not None:
                    cited.append((name, 1, self.singles[name]))  # type: ignore[arg-type]
            for short in ("companies", "participations", "changes"):
                for number, record in enumerate(self.tables.get(short) or [], start=1):
                    cited.append((RECORD_SETS[short][0], number, record))
            for name, number, record in cited:
                unknown = sorted(_source_refs(record) - source_ids)
                if unknown:
                    self.add("R10", f"cites source IDs that are not in sources.jsonl: {', '.join(unknown)}", name, number)

        if company_ids is not None:
            for number, record in enumerate(self.tables.get("companies") or [], start=1):
                target = record.get("merged_into")
                if isinstance(target, str) and target not in company_ids:
                    self.add("R10", f"merged_into {target!r} is not in companies.jsonl", RECORD_SETS["companies"][0], number)
            for number, record in enumerate(self.tables.get("participations") or [], start=1):
                company = record.get("company_id")
                if isinstance(company, str) and company not in company_ids:
                    self.add("R10", f"company_id {company!r} is not in companies.jsonl", RECORD_SETS["participations"][0], number)

        for number, record in enumerate(self.tables.get("participations") or [], start=1):
            if record.get("edition_id") != manifest.get("edition_id"):
                self.add("R10", "edition_id differs from the manifest", RECORD_SETS["participations"][0], number)
        for number, record in enumerate(self.tables.get("crawl_runs") or [], start=1):
            if record.get("edition_id") != manifest.get("edition_id"):
                self.add("R10", "edition_id differs from the manifest", RECORD_SETS["crawl_runs"][0], number)
        if run_ids is not None:
            for number, record in enumerate(self.tables.get("sources") or [], start=1):
                run = record.get("crawl_run_id")
                if isinstance(run, str) and run not in run_ids:
                    self.add("R10", f"crawl_run_id {run!r} is not in crawl_runs.jsonl", RECORD_SETS["sources"][0], number)

        changes = self.tables.get("changes") or []
        for number, record in enumerate(changes, start=1):
            for attribute in ("dataset_id", "previous_dataset_id"):
                if record.get(attribute) != manifest.get(attribute):
                    self.add("R10", f"{attribute} differs from the manifest", RECORD_SETS["changes"][0], number)
        if manifest.get("previous_dataset_id") is None and changes:
            self.add("R10", "the first dataset (previous_dataset_id is null) must have an empty changes.jsonl", RECORD_SETS["changes"][0])

    # ----------------------------------------------------------------- R11
    def r11_completeness(self) -> None:
        manifest = _dict(self.manifest)
        completeness = _dict(manifest.get("completeness"))
        participations = self.tables.get("participations")
        source_ids = self._ids("sources")
        listed = None if participations is None else sum(1 for p in participations if p.get("listing_status") == "listed")

        if listed is not None and completeness.get("collected_participation_count") != listed:
            self.add(
                "R11",
                f"collected_participation_count is {completeness.get('collected_participation_count')!r}, listed participations are {listed}",
                MANIFEST_FILE,
            )
        official_count = completeness.get("official_exhibitor_count")
        official_source = completeness.get("official_count_source_id")
        if isinstance(official_source, str) and source_ids is not None and official_source not in source_ids:
            self.add("R11", f"official_count_source_id {official_source!r} is not in sources.jsonl", MANIFEST_FILE)
        if official_count is not None and official_source is None:
            self.add("R11", "official_exhibitor_count needs a source: official_count_source_id is null (contract §9)", MANIFEST_FILE)
        if manifest.get("completeness_status") == "complete" and listed is not None and official_count != listed:
            self.add("R11", f"status is complete but official_exhibitor_count is {official_count!r}, listed participations are {listed}", MANIFEST_FILE)

    def run(self) -> None:
        if not self.r1_files():
            return
        self.r2_r3_manifest()
        self.r4_r5_records()
        self.r6_keys()
        if self.manifest is None:
            return
        self.r7_counts()
        self.r8_integrity()
        self.r9_identity()
        self.r10_references()
        self.r11_completeness()


def validate_package(package_dir: str | Path, *, schema_dir: str | Path | None = None) -> Report:
    """Validate a data package against R1-R11. Raises ``SchemaError`` only if the Schemas cannot be loaded."""
    schemas = SchemaSet(schema_dir)
    run = _Run(Path(package_dir), schemas)
    run.run()
    findings = sorted(set(run.findings), key=Finding.sort_key)
    return Report(package_dir=str(package_dir), schema_version=schemas.version, findings=findings)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.validate", description="Validate an ExhibitIQ data package (rules R1-R11).")
    parser.add_argument("package_dir")
    parser.add_argument("--schemas", help="schema directory (default: schemas/v1 in this repository)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        report = validate_package(args.package_dir, schema_dir=args.schemas)
    except SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) if args.json else report.text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
