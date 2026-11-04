"""Reference checks for the v1 data-package contract (P1-AI-04, Issue #7).

This module exists so the contract tests can prove that the examples in
``schemas/v1/examples/`` satisfy every rule in
``docs/specs/data-package-contract.md``. It is NOT the project's data
validator: the production validator is owned by data engineering under
``etl/`` (see docs/architecture/module-boundaries.md). Once that validator
exists, these tests should call it instead.

Dependencies: Python standard library + jsonschema (with referencing).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "v1"
VERSION = (SCHEMA_DIR / "VERSION").read_text(encoding="utf-8").strip()
# Versions whose data is still valid (schemas/v1/COMPATIBILITY.json; draft.6 is additive over draft.5).
ACCEPTED = set(json.loads((SCHEMA_DIR / "COMPATIBILITY.json").read_text(encoding="utf-8"))["accepted"])

# Data files in a package, and the schema each record must satisfy.
SINGLE_FILES = {"exhibition.json": "exhibition", "edition.json": "edition"}
JSONL_FILES = {
    "companies.jsonl": ("company", "company_id", "companies"),
    "participations.jsonl": ("participation", "participation_id", "participations"),
    "sources.jsonl": ("source", "source_id", "sources"),
    "crawl_runs.jsonl": ("crawl_run", "crawl_run_id", "crawl_runs"),
    "changes.jsonl": ("change", "change_id", "changes"),
}
DATA_FILES = sorted([*SINGLE_FILES, *JSONL_FILES], key=lambda s: s.encode("utf-8"))


# ---------------------------------------------------------------- schemas
def load_schemas() -> dict[str, dict]:
    return {
        p.name.removesuffix(".schema.json"): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }


def registry() -> Registry:
    """Local-only registry: every $id resolves to a file in schemas/v1/."""
    return Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in load_schemas().values()
    )


def validator(entity: str) -> Draft202012Validator:
    schemas = load_schemas()
    return Draft202012Validator(
        schemas[entity], registry=registry(), format_checker=FormatChecker()
    )


# ---------------------------------------------------------- serialization
def canonical_line(record: dict) -> str:
    """Canonical serialization of one record (contract §5)."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_entry(path: Path) -> dict:
    data = path.read_bytes()
    if path.suffix == ".jsonl":
        records = len(data.decode("utf-8").splitlines())
    else:
        records = 1
    return {"sha256": sha256_bytes(data), "bytes": len(data), "records": records}


def content_hash(pkg: Path) -> str:
    """Contract §6: sha256 over sha256sum-style lines sorted by file name."""
    lines = []
    for name in DATA_FILES:
        hexdigest = hashlib.sha256((pkg / name).read_bytes()).hexdigest()
        lines.append(f"{hexdigest}  {name}\n")
    return sha256_bytes("".join(lines).encode("utf-8"))


# ------------------------------------------------------------ package rules
def _read_jsonl(path: Path, errors: list[str]) -> list[dict]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"{path.name}: UTF-8 BOM not allowed")
    text = raw.decode("utf-8")
    if text and not text.endswith("\n"):
        errors.append(f"{path.name}: file must end with a newline")
    if "\r" in text:
        errors.append(f"{path.name}: CR characters not allowed (use LF)")
    records = []
    for i, line in enumerate(text.splitlines(), 1):
        rec = json.loads(line)
        if canonical_line(rec) != line + "\n":
            errors.append(f"{path.name}:{i}: not canonical serialization")
        records.append(rec)
    return records


def check_package(pkg: Path) -> list[str]:
    """Return a list of rule violations (empty list = package is valid)."""
    errors: list[str] = []

    # R1 all files present
    missing = [f for f in ["manifest.json", *DATA_FILES] if not (pkg / f).is_file()]
    if missing:
        return [f"R1 missing files: {missing}"]

    # R2 manifest validates
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    for e in validator("manifest").iter_errors(manifest):
        errors.append(f"R2 manifest.json: {e.message}")

    # R3 schema version matches VERSION exactly (draft period)
    if manifest.get("schema_version") not in ACCEPTED:
        errors.append(f"R3 schema_version {manifest.get('schema_version')!r} not in accepted {sorted(ACCEPTED)}")

    # R4 records validate, R5 canonical form, R6 unique and sorted IDs
    singles: dict[str, dict] = {}
    for name, entity in SINGLE_FILES.items():
        recs = _read_jsonl(pkg / name, errors)
        if len(recs) != 1:
            errors.append(f"R4 {name}: must contain exactly one record")
            continue
        singles[entity] = recs[0]
        for e in validator(entity).iter_errors(recs[0]):
            errors.append(f"R4 {name}: {e.message}")

    tables: dict[str, list[dict]] = {}
    for name, (entity, id_field, count_key) in JSONL_FILES.items():
        recs = _read_jsonl(pkg / name, errors)
        tables[entity] = recs
        v = validator(entity)
        for i, rec in enumerate(recs, 1):
            for e in v.iter_errors(rec):
                errors.append(f"R4 {name}:{i}: {e.message}")
        ids = [r.get(id_field) for r in recs]
        if len(set(ids)) != len(ids):
            errors.append(f"R6 {name}: duplicate {id_field}")
        if ids != sorted(ids, key=lambda s: str(s).encode("utf-8")):
            errors.append(f"R6 {name}: records not sorted by {id_field}")
        # R7 record_counts
        if manifest.get("record_counts", {}).get(count_key) != len(recs):
            errors.append(f"R7 record_counts.{count_key} != {len(recs)}")

    # R8 file entries and content_hash
    files = manifest.get("files", {})
    for name in DATA_FILES:
        if files.get(name) != file_entry(pkg / name):
            errors.append(f"R8 files[{name}] does not match actual file")
    if manifest.get("content_hash") != content_hash(pkg):
        errors.append("R8 content_hash does not match")

    # R9 identity consistency
    ex, ed = singles.get("exhibition", {}), singles.get("edition", {})
    if ex.get("exhibition_id") != manifest.get("exhibition_id"):
        errors.append("R9 exhibition.json exhibition_id != manifest")
    if ed.get("edition_id") != manifest.get("edition_id"):
        errors.append("R9 edition.json edition_id != manifest")
    if ed.get("exhibition_id") != manifest.get("exhibition_id"):
        errors.append("R9 edition.json exhibition_id != manifest")
    if ed.get("year") != manifest.get("edition_year"):
        errors.append("R9 edition.json year != manifest.edition_year")
    if not str(manifest.get("dataset_id", "")).startswith(f"{manifest.get('edition_id')}."):
        errors.append("R9 dataset_id must start with '<edition_id>.'")

    # R10 referential integrity
    company_ids = {r.get("company_id") for r in tables["company"]}
    source_ids = {r.get("source_id") for r in tables["source"]}
    run_ids = {r.get("crawl_run_id") for r in tables["crawl_run"]}
    if set(manifest.get("source_snapshot_ids", [])) != source_ids:
        errors.append("R10 manifest.source_snapshot_ids != sources.jsonl source_id set")
    if set(manifest.get("crawl_run_ids", [])) != run_ids:
        errors.append("R10 manifest.crawl_run_ids != crawl_runs.jsonl crawl_run_id set")

    def refs(rec: dict) -> set[str]:
        out = set(rec.get("source_ids", []))
        for ids in rec.get("field_sources", {}).values():
            out |= set(ids)
        for alias in rec.get("aliases", []):
            out |= set(alias.get("source_ids", []))
        return out

    for label, rec in [("exhibition.json", ex), ("edition.json", ed)] + [
        (f"{e}:{r.get(JSONL_FILES[f][1])}", r)
        for f, (e, *_rest) in JSONL_FILES.items()
        for r in tables[e]
    ]:
        dangling = refs(rec) - source_ids
        if dangling:
            errors.append(f"R10 {label}: unknown source_ids {sorted(dangling)}")
    for c in tables["company"]:
        if c.get("merged_into") and c["merged_into"] not in company_ids:
            errors.append(f"R10 {c.get('company_id')}: merged_into not in companies.jsonl")
    for p in tables["participation"]:
        if p.get("company_id") not in company_ids:
            errors.append(f"R10 {p.get('participation_id')}: company_id not in companies.jsonl")
        if p.get("edition_id") != manifest.get("edition_id"):
            errors.append(f"R10 {p.get('participation_id')}: edition_id != manifest")
    for s in tables["source"]:
        if s.get("crawl_run_id") and s["crawl_run_id"] not in run_ids:
            errors.append(f"R10 {s.get('source_id')}: crawl_run_id not in crawl_runs.jsonl")
    for r in tables["crawl_run"]:
        if r.get("edition_id") != manifest.get("edition_id"):
            errors.append(f"R10 {r.get('crawl_run_id')}: edition_id != manifest")
    for ch in tables["change"]:
        if ch.get("dataset_id") != manifest.get("dataset_id"):
            errors.append(f"R10 {ch.get('change_id')}: dataset_id != manifest")
        if ch.get("previous_dataset_id") != manifest.get("previous_dataset_id"):
            errors.append(f"R10 {ch.get('change_id')}: previous_dataset_id != manifest")
    if manifest.get("previous_dataset_id") is None and tables["change"]:
        errors.append("R10 first dataset (previous_dataset_id=null) must have empty changes.jsonl")

    # R11 completeness
    comp = manifest.get("completeness", {})
    listed = sum(1 for p in tables["participation"] if p.get("listing_status") == "listed")
    if comp.get("collected_participation_count") != listed:
        errors.append("R11 collected_participation_count != listed participations")
    if comp.get("official_count_source_id") and comp["official_count_source_id"] not in source_ids:
        errors.append("R11 official_count_source_id not in sources.jsonl")
    if manifest.get("completeness_status") == "complete" and comp.get("official_exhibitor_count") != listed:
        errors.append("R11 complete requires official_exhibitor_count == listed participations")

    return errors
