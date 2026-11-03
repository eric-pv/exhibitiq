"""Contract tests for the core data schemas v1 (P1-AI-04, Issue #7)."""
from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import package_check as pc

EXAMPLES = pc.SCHEMA_DIR / "examples"
PKG = EXAMPLES / "package"
ENTITIES = ["exhibition", "edition", "company", "participation", "source", "crawl_run", "manifest", "change"]


# ------------------------------------------------------------------ schema files
def test_version_file():
    assert re.fullmatch(r"1\.0\.0-draft\.[1-9][0-9]*", pc.VERSION)
    assert pc.load_schemas()["manifest"]["properties"]["schema_version"]["const"] == pc.VERSION


def test_all_core_entities_present():
    # Core data entities (A1-05) + analysis result (A1-06) + shared defs.
    assert set(ENTITIES) | {"common", "analysis_result"} == set(pc.load_schemas())


@pytest.mark.parametrize("name", sorted(pc.load_schemas()))
def test_schema_conventions(name):
    s = pc.load_schemas()[name]
    Draft202012Validator.check_schema(s)
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert s["$id"] == f"https://exhibitiq.invalid/schemas/v1/{name}.schema.json"
    if name != "common":
        assert s["type"] == "object"
        assert s["additionalProperties"] is False


def test_no_remote_refs():
    for name, s in pc.load_schemas().items():
        for ref in re.findall(r'"\$ref":\s*"([^"]+)"', json.dumps(s)):
            assert not ref.startswith("http"), f"{name}: remote $ref {ref}"


def test_manifest_has_spec_required_fields():
    # docs/ExhibitIQ_專案總規範.md §6
    required = set(pc.load_schemas()["manifest"]["required"])
    for f in ["schema_version", "dataset_id", "exhibition_id", "edition_year", "created_at",
              "source_snapshot_ids", "record_counts", "content_hash", "completeness_status"]:
        assert f in required


def test_core_records_cannot_be_ai_inferred():
    enum = pc.load_schemas()["common"]["$defs"]["fact_verification_status"]["enum"]
    assert "ai_inferred" not in enum


# ------------------------------------------------------------------ positive
def test_example_package_is_valid():
    assert pc.check_package(PKG) == []


def test_change_example_is_valid():
    rec = json.loads((EXAMPLES / "change.example.json").read_text(encoding="utf-8"))
    assert list(pc.validator("change").iter_errors(rec)) == []


def test_content_hash_matches_sha256sum_listing():
    import hashlib
    listing = "".join(
        f"{hashlib.sha256((PKG / n).read_bytes()).hexdigest()}  {n}\n"
        for n in sorted(pc.DATA_FILES, key=str.encode)
    )
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["content_hash"] == "sha256:" + hashlib.sha256(listing.encode()).hexdigest()


def test_empty_jsonl_hash_is_sha256_of_empty():
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["changes.jsonl"] == {
        "sha256": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "bytes": 0, "records": 0,
    }


# ------------------------------------------------------------------ negative: records
def _first(file: str) -> dict:
    return json.loads((PKG / file).read_text(encoding="utf-8").splitlines()[0])


def _base(entity: str) -> dict:
    return {
        "exhibition": lambda: _first("exhibition.json"),
        "edition": lambda: _first("edition.json"),
        "company": lambda: _first("companies.jsonl"),
        "participation": lambda: _first("participations.jsonl"),
        "source": lambda: _first("sources.jsonl"),
        "crawl_run": lambda: _first("crawl_runs.jsonl"),
        "manifest": lambda: json.loads((PKG / "manifest.json").read_text(encoding="utf-8")),
        "change": lambda: json.loads((EXAMPLES / "change.example.json").read_text(encoding="utf-8")),
    }[entity]()


def _set(path: str, value):
    def f(r):
        *parents, last = path.split(".")
        for p in parents:
            r = r[int(p)] if p.isdigit() else r[p]
        if value is _DEL:
            del r[last]
        else:
            r[last] = value
    return f


_DEL = object()

NEGATIVE = [
    # (id, entity, mutation)
    ("exhibition-missing-name", "exhibition", _set("name", _DEL)),
    ("exhibition-uppercase-id", "exhibition", _set("exhibition_id", "MSPO")),
    ("exhibition-unknown-field", "exhibition", _set("exhibitor_count", 10)),
    ("exhibition-empty-source_ids", "exhibition", _set("source_ids", [])),
    ("exhibition-ai-inferred", "exhibition", _set("verification_status", "ai_inferred")),
    ("edition-bad-id", "edition", _set("edition_id", "example-expo_2026")),
    ("edition-bad-date", "edition", _set("start_date", "2026/09/01")),
    ("edition-lowercase-country", "edition", _set("country", "zz")),
    ("company-name-based-id", "company", _set("company_id", "co_synthetic-simulation")),
    ("company-ai-inferred", "company", _set("verification_status", "ai_inferred")),
    ("company-merged-without-target", "company", _set("status", "merged")),
    ("company-active-with-merged_into", "company", _set("merged_into", "co_01JCC000000000000000000002")),
    ("company-whitespace-name", "company", _set("name", "   ")),
    ("company-domain-with-scheme", "company", _set("domains", ["https://example.org"])),
    ("company-bad-field_sources-key", "company", _set("field_sources", {"Website": ["src_01JCS000000000000000000001"]})),
    ("participation-missing-company", "participation", _set("company_id", _DEL)),
    ("participation-bad-type", "participation", _set("participation_type", "visitor")),
    ("participation-local-time", "participation", _set("first_seen_at", "2026-11-03T07:10:00+08:00")),
    ("participation-bad-source-id", "participation", _set("source_ids", ["SA"])),
    ("source-missing-hash", "source", _set("content_sha256", _DEL)),
    ("source-bare-hex-hash", "source", _set("content_sha256", "a" * 64)),
    ("source-missing-url", "source", _set("url", _DEL)),
    ("source-stored-without-locator", "source", _set("snapshot", {"storage": "git"})),
    ("source-unknown-type", "source", _set("source_type", "rumour")),
    ("crawl_run-missing-finished", "crawl_run", _set("finished_at", _DEL)),
    ("crawl_run-negative-count", "crawl_run", _set("stats.error_count", -1)),
    ("crawl_run-short-commit", "crawl_run", _set("code_commit", "abc1234")),
    ("manifest-wrong-version", "manifest", _set("schema_version", "1.0.0")),
    ("manifest-missing-content_hash", "manifest", _set("content_hash", _DEL)),
    ("manifest-bad-dataset_id", "manifest", _set("dataset_id", "example-expo-2026")),
    ("manifest-missing-file-entry", "manifest", lambda r: r["files"].pop("changes.jsonl")),
    ("manifest-unknown-origin", "manifest", _set("data_origin", "mixed")),
    ("manifest-complete-without-official-count", "manifest",
     lambda r: (r.update(completeness_status="complete"), r["completeness"].update(official_exhibitor_count=None))),
    ("manifest-complete-without-count-source", "manifest",
     lambda r: (r.update(completeness_status="complete"), r["completeness"].update(official_count_source_id=None))),
    ("manifest-empty-sources", "manifest", _set("source_snapshot_ids", [])),
    ("change-modified-without-fields", "change", _set("field_changes", _DEL)),
    ("change-null-previous", "change", _set("previous_dataset_id", None)),
    ("change-bad-entity_type", "change", _set("entity_type", "source")),
]


@pytest.mark.parametrize("case_id,entity,mutation", NEGATIVE, ids=[n[0] for n in NEGATIVE])
def test_invalid_records_rejected(case_id, entity, mutation):
    rec = copy.deepcopy(_base(entity))
    assert list(pc.validator(entity).iter_errors(rec)) == [], "base example must be valid"
    mutation(rec)
    assert list(pc.validator(entity).iter_errors(rec)), f"{case_id} was not rejected"


def test_manual_entry_source_needs_notes_not_url():
    rec = _base("source")
    rec.update(source_type="manual_entry")
    del rec["url"]
    rec.pop("notes", None)
    assert list(pc.validator("source").iter_errors(rec)), "manual_entry without notes accepted"
    rec["notes"] = "專案負責人依展商名片手動輸入。"
    assert list(pc.validator("source").iter_errors(rec)) == []


def test_complete_with_official_count_is_schema_valid():
    rec = _base("manifest")
    rec["completeness_status"] = "complete"
    assert list(pc.validator("manifest").iter_errors(rec)) == []


# ------------------------------------------------------------------ negative: package
@pytest.fixture
def pkg(tmp_path: Path) -> Path:
    dst = tmp_path / "package"
    shutil.copytree(PKG, dst)
    return dst


def _manifest(p: Path) -> dict:
    return json.loads((p / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(p: Path, m: dict) -> None:
    (p / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rehash(p: Path) -> None:
    m = _manifest(p)
    m["files"] = {n: pc.file_entry(p / n) for n in pc.DATA_FILES}
    m["content_hash"] = pc.content_hash(p)
    _write_manifest(p, m)


def _rules(errors: list[str]) -> set[str]:
    return {e.split()[0] for e in errors}


def test_tampered_file_detected(pkg):
    path = pkg / "companies.jsonl"
    path.write_bytes(path.read_bytes().replace(b"Synthetic Simulation", b"Synthetic Simulatiom"))
    assert "R8" in _rules(pc.check_package(pkg))


def test_missing_file_detected(pkg):
    (pkg / "changes.jsonl").unlink()
    assert _rules(pc.check_package(pkg)) == {"R1"}


def test_dangling_company_reference_detected(pkg):
    path = pkg / "participations.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "co_01JCC000000000000000000002", "co_01JCC000000000000000000009"), encoding="utf-8")
    _rehash(pkg)
    assert _rules(pc.check_package(pkg)) == {"R10"}


def test_dangling_source_reference_detected(pkg):
    path = pkg / "edition.json"
    path.write_text(path.read_text(encoding="utf-8").replace(
        '"start_date":["src_01JCS000000000000000000001"]', '"start_date":["src_01JCS000000000000000000009"]'), encoding="utf-8")
    _rehash(pkg)
    assert _rules(pc.check_package(pkg)) == {"R10"}


def test_record_count_mismatch_detected(pkg):
    m = _manifest(pkg)
    m["record_counts"]["companies"] = 3
    _write_manifest(pkg, m)
    assert _rules(pc.check_package(pkg)) == {"R7"}


def test_unsorted_records_detected(pkg):
    path = pkg / "companies.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(reversed(lines)), encoding="utf-8")
    _rehash(pkg)
    assert _rules(pc.check_package(pkg)) == {"R6"}


def test_non_canonical_serialization_detected(pkg):
    path = pkg / "crawl_runs.jsonl"
    rec = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(rec, indent=None) + "\n", encoding="utf-8")  # ", " separators
    _rehash(pkg)
    assert any("not canonical" in e for e in pc.check_package(pkg))


def test_complete_with_wrong_count_detected(pkg):
    m = _manifest(pkg)
    m["completeness_status"] = "complete"  # official 3, collected 2
    _write_manifest(pkg, m)
    assert _rules(pc.check_package(pkg)) == {"R11"}


def test_first_dataset_with_changes_detected(pkg):
    rec = json.loads((EXAMPLES / "change.example.json").read_text(encoding="utf-8"))
    m = _manifest(pkg)
    rec["dataset_id"] = m["dataset_id"]
    rec["source_ids"] = ["src_01JCS000000000000000000001"]
    (pkg / "changes.jsonl").write_text(pc.canonical_line(rec), encoding="utf-8")
    m["record_counts"]["changes"] = 1
    _write_manifest(pkg, m)
    _rehash(pkg)
    assert "R10" in _rules(pc.check_package(pkg))


def test_schema_version_mismatch_detected(pkg):
    m = _manifest(pkg)
    m["schema_version"] = "1.0.0-draft.0"
    _write_manifest(pkg, m)
    assert {"R2", "R3"} <= _rules(pc.check_package(pkg))
