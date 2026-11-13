"""Tests for etl.dataset_index (D2-12): the index the Dashboard reads, with failures and bad packages included."""
from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from etl.assemble import assemble_package
from etl.dataset_index import build_index, validate_index, write_index
from etl.schema_registry import SchemaSet
from tests.data.test_assemble import CREATED, pipeline

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
NOW = datetime(2026, 11, 4, 9, 0, 0, tzinfo=timezone.utc)
GEN = {"name": "exhibitiq-etl", "version": "1.0.0"}
ASSESS = {"example-expo": {"method": "file_import", "status": "feasible", "assessed_at": "2026-11-04T00:00:00Z", "report_path": "docs/data-platform/example-expo-source-assessment.md", "name": "Example Expo"}}


def index_for(root, **kw):
    return build_index(root, generated_at=NOW, generator=GEN, **kw)


def packages(tmp_path, *, runs_status="succeeded"):
    base = tmp_path / "in"
    base.mkdir(exist_ok=True)
    kw = pipeline(base)
    kw["crawl_runs"] = [dict(kw["crawl_runs"][0], status=runs_status)]
    return assemble_package(tmp_path / "pkg", **kw), kw


# --- the samples ---------------------------------------------------------------------------------


def test_index_over_the_sample_packages_is_valid_and_complete():
    index = index_for(SAMPLES, locator_prefix="data/samples")
    assert validate_index(index, packages_root=SAMPLES) == []
    by_ex = {e["exhibition_id"]: e for e in index["exhibitions"]}
    assert set(by_ex) == {"sample-fair", "demo-trade-show"} and index["schema_version"] == SchemaSet().version
    fair = by_ex["sample-fair"]["editions"][0]
    assert [d["dataset_id"][-16:] for d in fair["datasets"]] == ["20261104T010000Z", "20261104T020000Z"]  # both versions listed, oldest first
    assert fair["latest_dataset_id"].endswith("T020000Z") and fair["datasets"][1]["location"]["locator"].startswith("data/samples/sample-fair/2026/")
    assert by_ex["sample-fair"]["acquisition"] == {"method": "undetermined", "status": "not_assessed"}  # no assessment given: not invented


def test_summary_numbers_equal_the_manifest():
    index = index_for(SAMPLES)
    for ex in index["exhibitions"]:
        for ed in ex["editions"]:
            for d in ed["datasets"]:
                manifest = json.loads(next(SAMPLES.rglob(d["dataset_id"] + "/manifest.json")).read_text(encoding="utf-8"))
                assert d["content_hash"] == manifest["content_hash"] and d["record_counts"]["companies"] == manifest["record_counts"]["companies"]


# --- built packages, assessments, failures --------------------------------------------------------------


def test_assessment_and_last_acquisition_come_from_the_records(tmp_path):
    package, kw = packages(tmp_path)
    index = index_for(tmp_path / "pkg", assessments=ASSESS)
    assert validate_index(index, packages_root=tmp_path / "pkg") == []
    ex = index["exhibitions"][0]
    assert ex["acquisition"]["method"] == "file_import" and ex["acquisition"]["status"] == "feasible" and "name" not in ex["acquisition"]
    last = ex["editions"][0]["last_acquisition"]
    run = kw["crawl_runs"][0]
    assert (last["method"], last["status"], last["crawl_run_id"], last["dataset_id"]) == ("file_import", "succeeded", run["crawl_run_id"], package.manifest["dataset_id"])
    assert last["records_extracted"] == run["stats"]["records_extracted"] and "notes" not in last


def test_failed_acquisition_without_a_package_is_recorded_with_a_note_and_no_dataset(tmp_path):
    failed = {"crawl_run_id": "run_01JCR000000000000000000042", "exhibition_id": "other-expo", "edition_id": "other-expo-2026", "status": "failed", "finished_at": "2026-11-04T05:00:00Z",
              "stats": {"requests_attempted": 2, "requests_succeeded": 0, "records_extracted": 0, "error_count": 1}, "error_samples": [{"code": "access_blocked", "message": "HTTP 403 for https://x.example.com/", "occurred_at": "2026-11-04T05:00:00Z"}]}
    (tmp_path / "pkg").mkdir()
    index = index_for(tmp_path / "pkg", extra_runs=[failed], assessments={"other-expo": {"method": "automatic", "status": "not_feasible", "assessed_at": "2026-11-04T00:00:00Z", "report_path": "docs/x.md", "notes": "403", "name": "Other Expo"}})
    assert validate_index(index) == []
    edition = index["exhibitions"][0]["editions"][0]
    assert edition["latest_dataset_id"] is None and edition["datasets"] == [] and "dataset_id" not in edition["last_acquisition"]
    assert edition["last_acquisition"]["status"] == "failed" and "403" in edition["last_acquisition"]["notes"]
    assert index["exhibitions"][0]["name"] == "Other Expo" and any(n["level"] == "warning" and "failed" in n["message"] for n in index["notices"])


def test_a_later_failed_run_is_the_last_acquisition_but_the_good_package_stays_latest(tmp_path):
    package, kw = packages(tmp_path)
    later = {"crawl_run_id": "run_01JCR000000000000000000043", "exhibition_id": "example-expo", "edition_id": "example-expo-2026", "status": "failed", "finished_at": "2099-01-01T00:00:00Z",
             "stats": {"requests_attempted": 1, "requests_succeeded": 0, "records_extracted": 0, "error_count": 1}, "notes": "site was down"}
    index = index_for(tmp_path / "pkg", extra_runs=[later])
    edition = index["exhibitions"][0]["editions"][0]
    assert edition["last_acquisition"]["status"] == "failed" and edition["last_acquisition"]["notes"].endswith("site was down")
    assert edition["latest_dataset_id"] == package.manifest["dataset_id"] and validate_index(index) == []


def test_a_failed_run_recorded_inside_a_package_still_has_no_dataset_id(tmp_path):
    packages(tmp_path, runs_status="failed")
    last = index_for(tmp_path / "pkg")["exhibitions"][0]["editions"][0]["last_acquisition"]
    assert last["status"] == "failed" and "dataset_id" not in last and last["notes"].startswith("failed:")


def test_partial_run_gets_a_note_and_the_dataset(tmp_path):
    package, _ = packages(tmp_path, runs_status="partial")
    last = index_for(tmp_path / "pkg")["exhibitions"][0]["editions"][0]["last_acquisition"]
    assert last["status"] == "partial" and last["dataset_id"] == package.manifest["dataset_id"] and last["notes"].startswith("partial:")


def test_completeness_notices(tmp_path):
    packages(tmp_path)
    notices = index_for(tmp_path / "pkg")["notices"]
    assert any(n["level"] == "info" and "completeness is unknown" in n["message"] and "no official count" in n["message"] for n in notices)


def test_invalid_package_is_listed_with_findings_and_never_latest(tmp_path):
    package, _ = packages(tmp_path)
    broken = tmp_path / "pkg" / "example-expo" / "2026" / "example-expo-2026.20261105T080000Z"
    shutil.copytree(package.path, broken)
    manifest = json.loads((broken / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(dataset_id="example-expo-2026.20261105T080000Z", created_at="2026-11-05T08:00:00Z")
    (broken / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (broken / "changes.jsonl").write_text('{"x":1}\n' * 60, encoding="utf-8")  # the first package must have no changes, and these records are not changes
    index = index_for(tmp_path / "pkg")
    edition = index["exhibitions"][0]["editions"][0]
    bad = next(d for d in edition["datasets"] if d["dataset_id"].endswith("T080000Z") and d["created_at"].startswith("2026-11-05"))
    assert bad["validation"]["status"] == "failed" and len(bad["validation"]["messages"]) == 20 and bad["validation"]["error_count"] > 20
    assert edition["latest_dataset_id"] == package.manifest["dataset_id"]  # the newer but invalid package is not the latest
    assert any(n["level"] == "error" and "failed validation" in n["message"] for n in index["notices"])
    assert validate_index(index, packages_root=tmp_path / "pkg") == []


def test_datasets_are_ordered_by_created_at_not_by_directory_name(tmp_path):
    package, _ = packages(tmp_path)
    later = tmp_path / "pkg" / "example-expo" / "2026" / "example-expo-2026.20260101T000000Z"  # sorts first by name...
    shutil.copytree(package.path, later)
    manifest = json.loads((later / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(dataset_id="example-expo-2026.20260101T000000Z", created_at="2026-12-01T00:00:00Z")  # ...but was created last
    (later / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    edition = index_for(tmp_path / "pkg")["exhibitions"][0]["editions"][0]
    assert [d["created_at"][:7] for d in edition["datasets"]] == ["2026-11", "2026-12"] and edition["latest_dataset_id"].endswith("20260101T000000Z")


def test_unreadable_package_dir_is_reported_not_crashing(tmp_path):
    packages(tmp_path)
    junk = tmp_path / "pkg" / "junk-expo" / "2026" / "junk-expo-2026.20261104T000000Z"
    junk.mkdir(parents=True)
    index = index_for(tmp_path / "pkg")
    assert [e["exhibition_id"] for e in index["exhibitions"]] == ["example-expo"] and any("cannot be read" in n["message"] for n in index["notices"])


def test_empty_root_gives_a_valid_empty_index(tmp_path):
    index = index_for(tmp_path / "nothing")
    assert index["exhibitions"] == [] and validate_index(index) == []


def test_naive_generated_at_is_refused(tmp_path):
    with pytest.raises(ValueError):
        build_index(tmp_path, generated_at=datetime(2026, 11, 4), generator=GEN)


def test_output_is_deterministic(tmp_path):
    packages(tmp_path)
    assert index_for(tmp_path / "pkg") == index_for(tmp_path / "pkg")


# --- validate_index (IR1-IR7) ------------------------------------------------------------------------------


@pytest.fixture
def good(tmp_path):
    packages(tmp_path)
    return index_for(tmp_path / "pkg"), tmp_path / "pkg"


def mutated(index, fn):
    copy_ = copy.deepcopy(index)
    fn(copy_)
    return copy_


@pytest.mark.parametrize(
    "rule,fn",
    [
        ("IR1", lambda i: i.pop("notices")),
        ("IR1", lambda i: i.update(schema_version="0.0.1")),  # IR2: the Schema pins the draft version
        ("IR3", lambda i: i["exhibitions"].append(copy.deepcopy(i["exhibitions"][0]))),
        ("IR3", lambda i: i["exhibitions"][0]["editions"][0].update(edition_id="unrelated-2026")),
        ("IR3", lambda i: i["exhibitions"][0]["editions"][0].update(year=2027)),
        ("IR3", lambda i: i["exhibitions"][0]["editions"][0]["datasets"].append(copy.deepcopy(i["exhibitions"][0]["editions"][0]["datasets"][0]))),
        ("IR4", lambda i: i["exhibitions"][0]["editions"][0].update(latest_dataset_id=None)),
        ("IR5", lambda i: i["exhibitions"][0]["editions"][0]["last_acquisition"].update(dataset_id="example-expo-2026.20200101T000000Z")),
        ("IR7", lambda i: i["notices"].append({"level": "info", "message": "x", "occurred_at": "2026-11-04T00:00:00Z", "exhibition_id": "ghost"})),
        ("IR7", lambda i: i["notices"].append({"level": "info", "message": "x", "occurred_at": "2026-11-04T00:00:00Z", "exhibition_id": "example-expo", "dataset_id": "example-expo-2026.20200101T000000Z"})),
    ],
)
def test_each_rule_is_enforced(good, rule, fn):
    index, root = good
    problems = validate_index(mutated(index, fn), packages_root=root)
    assert any(p.startswith(rule) for p in problems), problems


@pytest.mark.parametrize("key,value", [("content_hash", "sha256:" + "1" * 64), ("completeness_status", "partial"), ("collected_participation_count", 99), ("data_origin", "collected")])
def test_summary_must_match_the_manifest_ir6(good, key, value):
    index, root = good
    problems = validate_index(mutated(index, lambda i: i["exhibitions"][0]["editions"][0]["datasets"][0].update({key: value})), packages_root=root)
    assert any(p.startswith("IR6") and key in p for p in problems), problems


def test_record_counts_and_missing_package_ir6(good):
    index, root = good
    assert any("record_counts" in p for p in validate_index(mutated(index, lambda i: i["exhibitions"][0]["editions"][0]["datasets"][0]["record_counts"].update(companies=99)), packages_root=root))
    assert any("cannot be read" in p for p in validate_index(index, packages_root=root / "elsewhere"))


def test_passed_but_actually_failing_package_ir6(tmp_path):
    package, _ = packages(tmp_path)
    index = index_for(tmp_path / "pkg")
    (package.path / "changes.jsonl").write_text('{"x":1}\n', encoding="utf-8")  # damage it after the index was built
    assert any("marked passed but the package fails" in p for p in validate_index(index, packages_root=tmp_path / "pkg"))


# --- write_index ---------------------------------------------------------------------------------------------


def test_write_index_is_atomic_and_refuses_invalid(tmp_path, good):
    index, root = good
    path = tmp_path / "out" / "index" / "datasets.json"
    write_index(index, path, packages_root=root)
    assert json.loads(path.read_text(encoding="utf-8")) == index and not list(path.parent.glob("*.tmp"))
    before = path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="nothing was written"):
        write_index(mutated(index, lambda i: i.update(schema_version="9")), path, packages_root=root)
    assert path.read_text(encoding="utf-8") == before


def test_failed_write_keeps_the_old_file(tmp_path, good, monkeypatch):
    import os

    index, root = good
    path = tmp_path / "datasets.json"
    write_index(index, path)
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        write_index(index, path)
    assert path.read_text(encoding="utf-8") == before and not list(tmp_path.glob("*.tmp"))


# --- command line ----------------------------------------------------------------------------------------------


def test_cli_writes_a_valid_index_with_assessments_and_unpackaged_runs(tmp_path):
    from etl.build_index import main

    package, kw = packages(tmp_path)
    (tmp_path / "idx").mkdir()
    (tmp_path / "idx" / "assessments.json").write_text(json.dumps(ASSESS), encoding="utf-8")
    raw = tmp_path / "raw" / "example-expo" / "example-expo-2026"
    in_pkg, orphan = kw["crawl_runs"][0], dict(kw["crawl_runs"][0], crawl_run_id="run_01JCR000000000000000000055", status="failed", finished_at="2099-01-01T00:00:00Z", notes="down")
    for run in (in_pkg, orphan):
        (raw / run["crawl_run_id"]).mkdir(parents=True)
        (raw / run["crawl_run_id"] / "crawl_run.json").write_text(json.dumps(run), encoding="utf-8")
    out = tmp_path / "idx" / "datasets.json"
    argv = ["--packages", str(tmp_path / "pkg"), "--out", str(out), "--assessments", str(tmp_path / "idx" / "assessments.json"), "--runs-dir", str(tmp_path / "raw")]
    assert main(argv, now=NOW) == 0
    index = json.loads(out.read_text(encoding="utf-8"))
    edition = index["exhibitions"][0]["editions"][0]
    assert validate_index(index, packages_root=tmp_path / "pkg") == [] and index["exhibitions"][0]["acquisition"]["method"] == "file_import"
    assert edition["last_acquisition"]["crawl_run_id"] == orphan["crawl_run_id"] and edition["latest_dataset_id"] == package.manifest["dataset_id"]


def test_cli_rejects_bad_inputs_and_writes_nothing(tmp_path, capsys):
    from etl.build_index import main

    packages(tmp_path)
    (tmp_path / "bad.json").write_text("[1]", encoding="utf-8")
    out = tmp_path / "o" / "datasets.json"
    assert main(["--packages", str(tmp_path / "pkg"), "--out", str(out), "--assessments", str(tmp_path / "bad.json")], now=NOW) == 2
    assert not out.exists() and "error:" in capsys.readouterr().err
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert main(["--packages", str(tmp_path / "pkg"), "--out", str(out), "--assessments", str(tmp_path / "bad.json")], now=NOW) == 2 and not out.exists()


def test_cli_with_no_packages_writes_an_empty_valid_index(tmp_path):
    from etl.build_index import main

    out = tmp_path / "datasets.json"
    assert main(["--packages", str(tmp_path / "none"), "--out", str(out), "--assessments", str(tmp_path / "none.json"), "--runs-dir", str(tmp_path / "none")], now=NOW) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["exhibitions"] == []
