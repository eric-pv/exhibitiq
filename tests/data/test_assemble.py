"""Tests for etl.assemble (D2-11), including the whole chain import -> store -> build -> assemble -> validate."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from crawler.adapters import AdapterRegistry
from crawler.file_import import ADAPTER_NAME, FileImportAdapter, import_files
from crawler.store import RunStore
from etl.assemble import AssembleError, OfficialCount, assemble_package, compute_completeness, dataset_id_for, load_run
from etl.build_records import RawListing, build_records
from etl.package import read_package
from etl.registry import CompanyRegistry
from etl.validate import validate_package
from tests.data.crawl_testkit import FakeClock, fixed_rand, make_config

CREATED = datetime(2026, 11, 4, 8, 0, 0, tzinfo=timezone.utc)
ORIGIN = "https://files.example.com/list.csv"
CSV = "Company,Booth,Country,Site\nSynthetic Optics Ltd.,A1,Exampleland,www.synthetic-optics.example.com\nAcme Demo,B2,Exampleland,\nSYNTHETIC OPTICS LTD,C3,,\n"
COLUMNS = [{"source": "Company", "field": "exhibitor_name_as_listed", "required": True}, {"source": "Booth", "field": "booth"}, {"source": "Country", "field": "country"}, {"source": "Site", "field": "website"}]
PRODUCER = {"name": "exhibitiq-etl", "version": "0.1.0"}


def pipeline(tmp_path, csv=CSV):
    """Import a CSV, store the evidence, build records. Returns everything assemble needs."""
    path = tmp_path / "list.csv"
    path.write_text(csv, encoding="utf-8")
    config = make_config(name="imp", adapter=ADAPTER_NAME, start_urls=(ORIGIN,), source_type="csv_import", options={"mapping": {"format": "csv", "columns": COLUMNS}})
    registry = AdapterRegistry()
    registry.register(FileImportAdapter)
    store = RunStore(tmp_path / "raw", config)
    result = import_files(config, {ORIGIN: path}, adapters=registry, clock=FakeClock(), rand=fixed_rand, sink=store)
    run_dir = store.finalize(result)
    sources, crawl_run = load_run(run_dir)
    listings = [RawListing(r.data, r.source_id) for r in result.records]
    stamps = {s["source_id"]: s["retrieved_at"] for s in sources}
    built = build_records(listings, edition_id="example-expo-2026", retrieved_at=stamps, registry=CompanyRegistry(rand=fixed_rand, now_ms=lambda: 1_700_000_000_000), country_aliases={"exampleland": "ZZ"})
    source_id = sources[0]["source_id"]
    return dict(
        exhibition={"exhibition_id": "example-expo", "name": "Example Expo", "source_ids": [source_id], "verification_status": "unverified"},
        edition={"edition_id": "example-expo-2026", "exhibition_id": "example-expo", "year": 2026, "source_ids": [source_id], "verification_status": "unverified"},
        companies=built.companies, participations=built.participations, sources=sources, crawl_runs=[crawl_run],
        data_origin="synthetic", producer=PRODUCER, created_at=CREATED,
    )


def assemble(tmp_path, **overrides):
    kwargs = {**pipeline(tmp_path), **overrides}
    return assemble_package(tmp_path / "packages", **kwargs), kwargs


# --- whole chain ---------------------------------------------------------------------------------


def test_the_whole_chain_produces_a_package_the_validator_accepts(tmp_path):
    package, kwargs = assemble(tmp_path)
    assert package.path == tmp_path / "packages" / "example-expo" / "2026" / "example-expo-2026.20261104T080000Z"
    report = validate_package(package.path)
    assert report.ok, report.text()
    manifest = package.manifest
    assert manifest["dataset_id"] == "example-expo-2026.20261104T080000Z" and manifest["created_at"] == "2026-11-04T08:00:00Z"
    assert manifest["data_origin"] == "synthetic" and manifest["previous_dataset_id"] is None and manifest["producer"] == PRODUCER
    assert manifest["record_counts"]["companies"] == 2 and manifest["record_counts"]["participations"] == 2  # the duplicate row merged
    assert manifest["source_snapshot_ids"] == [s["source_id"] for s in kwargs["sources"]] and manifest["crawl_run_ids"] == [kwargs["crawl_runs"][0]["crawl_run_id"]]
    assert manifest["completeness_status"] == "unknown" and manifest["completeness"] == {"official_exhibitor_count": None, "official_count_source_id": None, "collected_participation_count": 2}
    assert manifest["content_hash"].startswith("sha256:")


def test_package_content_is_readable_and_traceable(tmp_path):
    package, kwargs = assemble(tmp_path)
    read = read_package(package.path, require_canonical=True)
    source_ids = {s["source_id"] for s in read.records["sources"]}
    assert source_ids and all(set(c["source_ids"]) <= source_ids for c in read.records["companies"])
    assert all(set(p["source_ids"]) <= source_ids for p in read.records["participations"])
    assert read.records["changes"] == [] and read.records["sources"][0]["snapshot"]["storage"] == "git"


def test_same_inputs_give_the_same_content_hash(tmp_path):
    first, kwargs = assemble(tmp_path)
    again = assemble_package(tmp_path / "other", **kwargs)
    assert again.manifest["content_hash"] == first.manifest["content_hash"]


# --- completeness ---------------------------------------------------------------------------------


def listed(n, status="listed"):
    return [{"listing_status": status} for _ in range(n)]


def test_completeness_rules():
    sources = {"src_01JCS000000000000000000001"}
    sid = next(iter(sources))
    assert compute_completeness(listed(3), None, sources)[0] == "unknown"
    assert compute_completeness(listed(3), OfficialCount(3, sid), sources) == ("complete", {"official_exhibitor_count": 3, "official_count_source_id": sid, "collected_participation_count": 3})
    assert compute_completeness(listed(2), OfficialCount(3, sid), sources)[0] == "partial"
    assert compute_completeness(listed(4), OfficialCount(3, sid), sources)[0] == "partial"
    assert compute_completeness(listed(2) + listed(5, "removed"), OfficialCount(2, sid), sources)[0] == "complete"  # removed listings do not count
    assert compute_completeness([], OfficialCount(0, sid), sources)[0] == "complete"
    status, completeness = compute_completeness(listed(1), OfficialCount(1, sid, date(2026, 10, 1)), sources)
    assert completeness["official_count_as_of"] == "2026-10-01"


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_bad_official_counts_are_refused(count):
    sid = "src_01JCS000000000000000000001"
    with pytest.raises(AssembleError, match="non-negative integer"):
        compute_completeness(listed(1), OfficialCount(count, sid), {sid})  # type: ignore[arg-type]


def test_official_count_needs_a_source_in_the_package():
    with pytest.raises(AssembleError, match="not among the package's sources"):
        compute_completeness(listed(1), OfficialCount(1, "src_01JCS000000000000000000009"), {"src_01JCS000000000000000000001"})


def test_complete_and_partial_packages_validate(tmp_path):
    kwargs = pipeline(tmp_path)
    sid = kwargs["sources"][0]["source_id"]
    complete = assemble_package(tmp_path / "p1", **kwargs, official_count=OfficialCount(2, sid, date(2026, 11, 1)))
    assert complete.manifest["completeness_status"] == "complete" and validate_package(complete.path).ok
    partial = assemble_package(tmp_path / "p2", **kwargs, official_count=OfficialCount(5, sid))
    assert partial.manifest["completeness_status"] == "partial" and partial.manifest["completeness"]["official_exhibitor_count"] == 5 and validate_package(partial.path).ok


# --- refusing bad input -----------------------------------------------------------------------------


def leftovers(root: Path):
    return [p for p in root.rglob("*") if p.name.startswith(".")] if root.exists() else []


def test_invalid_records_publish_nothing_and_report_findings(tmp_path):
    kwargs = pipeline(tmp_path)
    broken = [dict(p, source_ids=["src_01JCS000000000000000000009"]) for p in kwargs["participations"]]  # references a source that is not in sources.jsonl
    with pytest.raises(AssembleError) as caught:
        assemble_package(tmp_path / "packages", **{**kwargs, "participations": broken})
    assert "nothing was published" in str(caught.value) and "R10" in {f.rule for f in caught.value.findings}
    assert list((tmp_path / "packages").rglob("manifest.json")) == [] and leftovers(tmp_path / "packages") == []


def test_changes_without_a_previous_package_are_refused_for_that_reason(tmp_path):
    kwargs = pipeline(tmp_path)
    dataset_id = dataset_id_for("example-expo-2026", CREATED)
    pid, sid = kwargs["participations"][0]["participation_id"], kwargs["sources"][0]["source_id"]
    change = {
        "change_id": "chg_01JCH000000000000000000001", "dataset_id": dataset_id, "previous_dataset_id": "example-expo-2026.20261103T000000Z",
        "entity_type": "participation", "entity_id": pid, "change_type": "modified", "field_changes": [{"field": "booth", "before": None, "after": "Z9"}],
        "detected_at": "2026-11-04T08:00:00Z", "source_ids": [sid],
    }
    with pytest.raises(AssembleError) as caught:
        assemble_package(tmp_path / "packages", **{**kwargs, "changes": [change]})
    assert any("empty changes.jsonl" in f.message or "differs from the manifest" in f.message for f in caught.value.findings)
    assert list((tmp_path / "packages").rglob("manifest.json")) == []


def test_existing_package_is_never_overwritten(tmp_path):
    package, kwargs = assemble(tmp_path)
    before = (package.path / "manifest.json").read_bytes()
    with pytest.raises(AssembleError, match="immutable"):
        assemble_package(tmp_path / "packages", **kwargs)
    assert (package.path / "manifest.json").read_bytes() == before
    later = assemble_package(tmp_path / "packages", **{**kwargs, "created_at": CREATED + timedelta(seconds=1), "previous_dataset_id": package.manifest["dataset_id"]})
    assert later.manifest["previous_dataset_id"] == package.manifest["dataset_id"]


def test_existing_package_is_detected_before_any_work_is_done(tmp_path, monkeypatch):
    package, kwargs = assemble(tmp_path)
    import etl.assemble as module

    monkeypatch.setattr(module, "write_package", lambda *a, **k: pytest.fail("must not write when the package exists"))
    with pytest.raises(AssembleError, match="immutable"):
        assemble_package(tmp_path / "packages", **kwargs)


def test_a_package_that_appears_during_assembly_is_not_overwritten(tmp_path, monkeypatch):
    kwargs = pipeline(tmp_path)
    import etl.assemble as module

    real = module.validate_package
    final = tmp_path / "packages" / "example-expo" / "2026" / "example-expo-2026.20261104T080000Z"

    def racing_validate(path, **kw):
        final.mkdir(parents=True)  # someone else published the same dataset_id meanwhile
        (final / "marker").write_text("theirs", encoding="utf-8")
        return real(path, **kw)

    monkeypatch.setattr(module, "validate_package", racing_validate)
    with pytest.raises(AssembleError, match="immutable"):
        assemble_package(tmp_path / "packages", **kwargs)
    assert (final / "marker").read_text(encoding="utf-8") == "theirs" and leftovers(tmp_path / "packages") == []


def test_participation_of_another_edition_is_refused(tmp_path):
    kwargs = pipeline(tmp_path)
    other = [dict(p, edition_id="example-expo-2027") for p in kwargs["participations"]]
    with pytest.raises(AssembleError, match="another edition"):
        assemble_package(tmp_path / "packages", **{**kwargs, "participations": other})


def test_naive_created_at_and_incomplete_edition_are_refused(tmp_path):
    kwargs = pipeline(tmp_path)
    with pytest.raises(AssembleError, match="timezone-aware"):
        assemble_package(tmp_path / "packages", **{**kwargs, "created_at": datetime(2026, 11, 4, 8, 0, 0)})
    with pytest.raises(AssembleError, match="edition must carry"):
        assemble_package(tmp_path / "packages", **{**kwargs, "edition": {"edition_id": "example-expo-2026"}})


def test_leftover_from_a_crashed_attempt_is_cleaned_up(tmp_path):
    kwargs = pipeline(tmp_path)
    hidden = tmp_path / "packages" / "example-expo" / "2026" / ".assembling-example-expo-2026.20261104T080000Z"
    hidden.mkdir(parents=True)
    (hidden / "junk").write_text("x", encoding="utf-8")
    package = assemble_package(tmp_path / "packages", **kwargs)
    assert validate_package(package.path).ok and leftovers(tmp_path / "packages") == []


def test_timezone_is_converted_to_utc(tmp_path):
    taipei = timezone(timedelta(hours=8))
    package, _ = assemble(tmp_path, created_at=datetime(2026, 11, 4, 16, 0, 0, tzinfo=taipei))
    assert package.manifest["dataset_id"].endswith(".20261104T080000Z") and package.manifest["created_at"] == "2026-11-04T08:00:00Z"
    assert dataset_id_for("example-expo-2026", datetime(2026, 11, 4, 16, 0, 0, tzinfo=taipei)) == "example-expo-2026.20261104T080000Z"


def test_notes_are_kept_and_sources_without_records_stay_in_the_index(tmp_path):
    kwargs = pipeline(tmp_path)
    extra = dict(kwargs["sources"][0], source_id="src_01JCS000000000000000000077", url="https://files.example.com/other.csv")
    package = assemble_package(tmp_path / "packages", **{**kwargs, "sources": [*kwargs["sources"], extra]}, notes="synthetic test package")
    assert package.manifest["notes"] == "synthetic test package" and extra["source_id"] in package.manifest["source_snapshot_ids"]
    assert validate_package(package.path).ok


def test_load_run_errors(tmp_path):
    with pytest.raises(AssembleError, match="cannot read run"):
        load_run(tmp_path / "missing")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "crawl_run.json").write_text("{", encoding="utf-8")
    (tmp_path / "bad" / "sources.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(AssembleError, match="cannot read run"):
        load_run(tmp_path / "bad")


def test_manifest_schema_version_follows_the_repository_version(tmp_path):
    package, _ = assemble(tmp_path)
    version = (Path(__file__).resolve().parents[2] / "schemas" / "v1" / "VERSION").read_text(encoding="utf-8").strip()
    assert package.manifest["schema_version"] == version
    assert json.loads((package.path / "manifest.json").read_text(encoding="utf-8"))["schema_version"] == version
