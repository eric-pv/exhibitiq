"""Tests for etl.changes and etl.history (D2-08): carry-forward, change records, cross-year history."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from etl.assemble import assemble_package, dataset_id_for
from etl.build_records import RawListing, build_records
from etl.changes import REMOVED_NOTE, carry_forward, diff_records
from etl.history import HISTORY_VERSION, build_history, latest_package_dirs
from etl.package import read_package
from etl.registry import CompanyRegistry
from etl.schema_registry import SchemaSet
from etl.validate import validate_package
from tests.data.crawl_testkit import fixed_rand
from tests.data.test_assemble import CREATED, pipeline as _pipeline

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"
SCHEMAS = SchemaSet()
S1, S2 = "src_01JCS000000000000000000001", "src_01JCS000000000000000000002"
RUN1, RUN2 = "run_01JCR000000000000000000001", "run_01JCR000000000000000000002"


def part(n, status="listed", **kw):
    base = {"participation_id": f"pt_01JCP00000000000000000000{n}", "company_id": f"co_01JCC00000000000000000000{n}", "edition_id": "example-expo-2026",
            "exhibitor_name_as_listed": f"Company {n}", "participation_type": "exhibitor", "listing_status": status, "first_seen_at": "2026-11-03T06:00:00Z",
            "last_seen_at": "2026-11-03T06:00:00Z", "source_ids": [S1], "verification_status": "unverified"}
    base.update(kw)
    return base


def comp(n, **kw):
    base = {"company_id": f"co_01JCC00000000000000000000{n}", "name": f"Company {n}", "status": "active", "source_ids": [S1], "verification_status": "unverified", "first_seen_at": "2026-11-03T06:00:00Z"}
    base.update(kw)
    return base


def src(sid):
    return {"source_id": sid}


def carry(prev, **new):
    base = dict(companies=[], participations=[], sources=[src(S2)], crawl_runs=[{"crawl_run_id": RUN2}])
    base.update(new)
    return carry_forward(prev, **base)


def pipeline(path):
    path.mkdir(parents=True, exist_ok=True)
    return _pipeline(path)


PREV = {"companies": [comp(1), comp(2)], "participations": [part(1, booth="A1"), part(2)], "sources": [src(S1)], "crawl_runs": [{"crawl_run_id": RUN1}]}


# --- carry_forward --------------------------------------------------------------------------------


def test_missing_participation_is_kept_as_removed():
    result = carry(PREV, companies=[comp(1, source_ids=[S2])], participations=[part(1, source_ids=[S2], booth="A1", first_seen_at="2026-11-04T06:00:00Z")])
    by_id = {p["participation_id"]: p for p in result.participations}
    removed = by_id["pt_01JCP000000000000000000002"]
    assert removed["listing_status"] == "removed" and REMOVED_NOTE in removed["notes"] and removed["last_seen_at"] == "2026-11-03T06:00:00Z" and removed["source_ids"] == [S1]
    assert by_id["pt_01JCP000000000000000000001"]["listing_status"] == "listed"
    assert {c["company_id"] for c in result.companies} == {"co_01JCC000000000000000000001", "co_01JCC000000000000000000002"}  # company 2 is still referenced


def test_already_removed_stays_unchanged_and_relisted_becomes_listed():
    prev = {**PREV, "participations": [part(1, "removed", notes="old"), part(2, "removed")]}
    result = carry(prev, companies=[comp(1)], participations=[part(1, source_ids=[S2])])
    by_id = {p["participation_id"]: p for p in result.participations}
    assert by_id["pt_01JCP000000000000000000001"]["listing_status"] == "listed"
    assert by_id["pt_01JCP000000000000000000002"] == part(2, "removed")


def test_first_seen_stays_the_earliest():
    prev = {**PREV, "participations": [part(1)], "companies": [comp(1)]}
    result = carry(prev, companies=[comp(1, first_seen_at="2026-12-01T00:00:00Z")], participations=[part(1, first_seen_at="2026-12-01T00:00:00Z")])
    assert result.participations[0]["first_seen_at"] == "2026-11-03T06:00:00Z" and result.companies[0]["first_seen_at"] == "2026-11-03T06:00:00Z"


def test_sources_and_runs_accumulate_without_duplicates_and_sorted():
    result = carry(PREV, companies=[comp(1)], participations=[part(1)], sources=[src(S2), src(S1)], crawl_runs=[{"crawl_run_id": RUN2}, {"crawl_run_id": RUN1}])
    assert [s["source_id"] for s in result.sources] == [S1, S2] and [r["crawl_run_id"] for r in result.crawl_runs] == [RUN1, RUN2]


def test_merged_companies_are_not_silently_unmerged():
    merged = comp(2, status="merged", merged_into="co_01JCC000000000000000000001")
    prev = {**PREV, "companies": [comp(1), merged]}
    result = carry(prev, companies=[comp(1), comp(2)], participations=[part(1), part(2)])
    kept = next(c for c in result.companies if c["company_id"].endswith("2"))
    assert kept["status"] == "merged" and kept["merged_into"].endswith("1") and any("is merged" in w for w in result.warnings)


def test_unreferenced_companies_are_dropped_with_a_warning_but_merge_targets_are_kept():
    prev = {**PREV, "companies": [comp(1), comp(2), comp(3), comp(4, status="merged", merged_into="co_01JCC000000000000000000003")], "participations": [part(1), part(4)]}
    result = carry(prev, companies=[comp(1)], participations=[part(1)])
    ids = {c["company_id"][-1] for c in result.companies}
    assert ids == {"1", "3", "4"} and any("company co_01JCC000000000000000000002" in w for w in result.warnings)


def test_inputs_are_not_mutated():
    import copy

    prev, new_parts = copy.deepcopy(PREV), [part(1)]
    before = copy.deepcopy((prev, new_parts))
    carry(prev, companies=[comp(1)], participations=new_parts)
    assert (prev, new_parts) == before


# --- diff_records ----------------------------------------------------------------------------------


def diff(prev, cur):
    return diff_records(prev, cur, dataset_id="example-expo-2026.20261105T000000Z", previous_dataset_id="example-expo-2026.20261104T000000Z", detected_at="2026-11-05T00:00:00Z", rand=fixed_rand, now_ms=1_700_000_000_000)


def test_added_removed_modified_unchanged():
    prev = {"companies": [comp(1), comp(2)], "participations": [part(1, booth="A1"), part(2), part(3)]}
    cur = {"companies": [comp(1), comp(2), comp(4, source_ids=[S2])], "participations": [part(1, booth="B2", last_seen_at="2027-01-01T00:00:00Z", source_ids=[S2]), part(2, "removed"), part(3), part(4, source_ids=[S2])]}
    changes = diff(prev, cur)
    summary = sorted((c["entity_type"], c["change_type"], c["entity_id"][-1]) for c in changes)
    assert summary == [("company", "added", "4"), ("participation", "added", "4"), ("participation", "modified", "1"), ("participation", "removed", "2")]
    modified = next(c for c in changes if c["change_type"] == "modified")
    assert modified["field_changes"] == [{"field": "booth", "before": "A1", "after": "B2"}]  # last_seen_at / source_ids are bookkeeping
    assert modified["source_ids"] == [S2]
    for change in changes:
        assert SCHEMAS.errors("change", change) == [] and change["dataset_id"].endswith("20261105T000000Z") and change["detected_at"] == "2026-11-05T00:00:00Z"


def test_no_changes_means_no_records():
    same = {"companies": [comp(1)], "participations": [part(1)]}
    assert diff(same, same) == []


def test_removed_to_removed_is_not_a_change_but_relisting_is():
    prev = {"participations": [part(1, "removed")]}
    assert diff(prev, {"participations": [part(1, "removed")]}) == []
    relisted = diff(prev, {"participations": [part(1)]})
    assert relisted[0]["change_type"] == "modified" and relisted[0]["field_changes"] == [{"field": "listing_status", "before": "removed", "after": "listed"}]


def test_a_field_that_disappears_is_reported_literally_as_null():
    changes = diff({"participations": [part(1, booth="A1", hall="2")]}, {"participations": [part(1, hall="2")]})
    assert changes[0]["field_changes"] == [{"field": "booth", "before": "A1", "after": None}]


def test_nested_value_changes_are_whole_values():
    changes = diff({"participations": [part(1, categories_as_listed=["a"])]}, {"participations": [part(1, categories_as_listed=["a", "b"])]})
    assert changes[0]["field_changes"] == [{"field": "categories_as_listed", "before": ["a"], "after": ["a", "b"]}]


def test_a_vanished_record_is_a_removal_on_its_own_terms():
    changes = diff({"participations": [part(1)]}, {"participations": []})
    assert [(c["change_type"], c["source_ids"]) for c in changes] == [("removed", [S1])]


def test_changes_come_out_sorted_by_change_id_whatever_the_id_source():
    state = {"n": 100}

    def descending(n: int) -> bytes:
        state["n"] -= 1
        return state["n"].to_bytes(n, "big")

    prev = {"participations": [part(i) for i in range(1, 6)]}
    changes = diff_records(prev, {"participations": []}, dataset_id="example-expo-2026.20261105T000000Z", previous_dataset_id="example-expo-2026.20261104T000000Z", detected_at="2026-11-05T00:00:00Z", rand=descending, now_ms=1)
    ids = [c["change_id"] for c in changes]
    assert ids == sorted(ids) and [c["entity_id"][-1] for c in changes] == ["5", "4", "3", "2", "1"]


def test_change_ids_are_unique_and_valid():
    prev = {"participations": [part(i) for i in range(1, 6)]}
    changes = diff(prev, {"participations": []})
    ids = [c["change_id"] for c in changes]
    assert len(set(ids)) == 5 and ids == sorted(ids)


def test_diff_agrees_with_the_changes_recorded_in_the_sample_package():
    """The D1-06 sample's second package lists its changes by hand; the diff of its two packages must find the same ones."""
    v1 = read_package(sorted((SAMPLES / "sample-fair" / "2026").iterdir())[0])
    v2 = read_package(sorted((SAMPLES / "sample-fair" / "2026").iterdir())[1])
    found = diff_records(v1.records, v2.records, dataset_id=v2.manifest["dataset_id"], previous_dataset_id=v1.manifest["dataset_id"], detected_at="2026-11-04T01:45:00Z", rand=fixed_rand, now_ms=1)
    def key(c):
        fields = [f for f in c.get("field_changes", []) if f["field"] != "notes"]  # the sample's hand-written list leaves out free-text note edits
        return (c["entity_type"], c["entity_id"], c["change_type"], json.dumps(sorted(fields, key=lambda f: f["field"]), sort_keys=True))

    assert sorted(map(key, found)) == sorted(map(key, v2.records["changes"]))
    assert any(f["field"] == "notes" for c in found for f in c.get("field_changes", []))  # ...but a literal diff does see them


# --- the whole thing: two acquisitions of one edition ----------------------------------------------------------


def test_second_acquisition_builds_a_valid_package_with_history(tmp_path):
    first = pipeline(tmp_path / "a")
    package1 = assemble_package(tmp_path / "packages", **first)
    prev = read_package(package1.path).records

    # second acquisition: Acme Demo is gone, a new company appears, Synthetic Optics changes booth
    reg = CompanyRegistry(rand=fixed_rand, now_ms=lambda: 1_700_000_000_000)
    for c in prev["companies"]:  # the registry from the first run (same IDs)
        reg.companies[c["company_id"]] = __import__("etl.registry", fromlist=["Entry"]).Entry([__import__("etl.normalize", fromlist=["name_keys"]).name_keys(c["name"]).exact], "x", [], None)
    src2 = "src_01JCS000000000000000000077"
    new_source = dict(first["sources"][0], source_id=src2, retrieved_at="2026-11-05T09:00:00Z", crawl_run_id=RUN2)
    new_run = dict(first["crawl_runs"][0], crawl_run_id=RUN2)
    built = build_records(
        [RawListing({"exhibitor_name_as_listed": "Synthetic Optics Ltd.", "booth": "Z9"}, src2), RawListing({"exhibitor_name_as_listed": "Brand New Co", "booth": "N1"}, src2)],
        edition_id="example-expo-2026", retrieved_at={src2: new_source["retrieved_at"]}, registry=reg,
    )
    # the participation IDs must be the same as before for the unchanged company: take them from the first package
    for p in built.participations:
        old = next((o for o in prev["participations"] if o["company_id"] == p["company_id"]), None)
        if old:
            p["participation_id"] = old["participation_id"]
    carried = carry_forward(prev, companies=built.companies, participations=built.participations, sources=[new_source], crawl_runs=[new_run])
    created2 = CREATED + timedelta(hours=1)
    changes = diff_records(prev, {"companies": carried.companies, "participations": carried.participations}, dataset_id=dataset_id_for("example-expo-2026", created2),
                           previous_dataset_id=package1.manifest["dataset_id"], detected_at="2026-11-05T09:00:00Z", rand=fixed_rand, now_ms=1_700_000_000_000)
    kwargs = {**first, "companies": carried.companies, "participations": carried.participations, "sources": carried.sources, "crawl_runs": carried.crawl_runs, "created_at": created2}
    package2 = assemble_package(tmp_path / "packages", **kwargs, previous_dataset_id=package1.manifest["dataset_id"], changes=changes)
    assert validate_package(package2.path).ok
    records = read_package(package2.path).records
    statuses = {p["exhibitor_name_as_listed"]: p["listing_status"] for p in records["participations"]}
    assert statuses == {"Synthetic Optics Ltd.": "listed", "Acme Demo": "removed", "Brand New Co": "listed"}
    assert sorted((c["entity_type"], c["change_type"]) for c in records["changes"]) == [("company", "added"), ("company", "modified"), ("participation", "added"), ("participation", "modified"), ("participation", "removed")]
    company_change = next(c for c in records["changes"] if c["entity_type"] == "company" and c["change_type"] == "modified")
    assert {f["field"] for f in company_change["field_changes"]} >= {"website"} and all(f["after"] is None for f in company_change["field_changes"] if f["field"] == "website")  # no longer in the latest listing
    assert len(records["sources"]) == 2 and len(records["crawl_runs"]) == 2
    assert package2.manifest["completeness"]["collected_participation_count"] == 2  # removed ones do not count


# --- history ------------------------------------------------------------------------------------------------


def test_history_over_the_sample_packages():
    history = build_history(latest_package_dirs(SAMPLES))
    assert history.skipped == [] and len(history.packages) == 2
    data = history.to_dict()
    assert data["version"] == HISTORY_VERSION and len(data["companies"]) == 8
    assert all(p["data_origin"] == "synthetic" for e in data["companies"].values() for p in e["participations"])
    ids = list(data["companies"])
    assert ids == sorted(ids)
    merged = [p for e in data["companies"].values() for p in e["participations"] if "canonical_company_id" in p]
    assert merged and all(p["canonical_company_id"] != "" for p in merged)


def test_only_the_latest_package_of_each_edition_is_used():
    dirs = latest_package_dirs(SAMPLES)
    names = sorted(p.name for p in dirs)
    assert names == ["demo-trade-show-2025.20261104T030000Z", "sample-fair-2026.20261104T020000Z"]  # not ...T010000Z


def test_company_in_two_editions_gets_both_participations(tmp_path):
    first = pipeline(tmp_path / "a")
    p1 = assemble_package(tmp_path / "packages", **first)
    # the same company next year: same company_id, new edition
    ed2 = dict(first["edition"], edition_id="example-expo-2027", year=2027)
    parts2 = [dict(p, edition_id="example-expo-2027", participation_id=p["participation_id"][:-2] + "9" + p["participation_id"][-1]) for p in first["participations"]]
    runs2 = [dict(r, edition_id="example-expo-2027") for r in first["crawl_runs"]]
    p2 = assemble_package(tmp_path / "packages", **{**first, "edition": ed2, "participations": parts2, "crawl_runs": runs2, "created_at": CREATED + timedelta(days=365)})
    history = build_history(latest_package_dirs(tmp_path / "packages"))
    assert len(history.packages) == 2 and history.skipped == []
    for entry in history.to_dict()["companies"].values():
        assert [p["edition_year"] for p in entry["participations"]] == [2026, 2027]
    assert p1.manifest["dataset_id"] != p2.manifest["dataset_id"]
    reversed_input = build_history(list(reversed(latest_package_dirs(tmp_path / "packages"))))
    for entry in reversed_input.to_dict()["companies"].values():
        assert [p["edition_year"] for p in entry["participations"]] == [2026, 2027]  # sorted whatever order the packages were read in


def test_invalid_or_unreadable_packages_are_reported_not_used(tmp_path):
    first = pipeline(tmp_path / "a")
    good = assemble_package(tmp_path / "packages", **first)
    bad = tmp_path / "packages" / "other-expo" / "2026" / "other-expo-2026.20261104T000000Z"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text("{}", encoding="utf-8")
    corrupt = tmp_path / "packages" / "third-expo" / "2026" / "third-expo-2026.20261104T000000Z"
    corrupt.mkdir(parents=True)
    history = build_history(latest_package_dirs(tmp_path / "packages"))
    assert history.packages == [good.manifest["dataset_id"]] and len(history.skipped) == 2
    assert all(s["reason"] for s in history.skipped)


def test_a_readable_but_invalid_package_is_skipped(tmp_path):
    import shutil

    first = pipeline(tmp_path / "a")
    good = assemble_package(tmp_path / "packages", **first)
    broken = tmp_path / "packages" / "copy-expo" / "2026" / "copy-expo-2026.20261104T080000Z"
    shutil.copytree(good.path, broken)
    manifest = json.loads((broken / "manifest.json").read_text(encoding="utf-8"))
    manifest["content_hash"] = "sha256:" + "0" * 64  # still well-formed, no longer true
    (broken / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert read_package(broken)  # readable...
    history = build_history(latest_package_dirs(tmp_path / "packages"))
    assert history.packages == [good.manifest["dataset_id"]] and "fails validation" in history.skipped[0]["reason"]  # ...but not used


def test_merge_chains_are_followed_and_cycles_do_not_hang():
    from etl.history import _canonical

    assert _canonical("a", {"a": "b", "b": "c"}) == "c" and _canonical("x", {}) == "x"
    assert _canonical("a", {"a": "b", "b": "a"}) == "a"  # a cycle stops at the starting entry instead of looping


def test_history_save_is_atomic_and_stable(tmp_path):
    history = build_history(latest_package_dirs(SAMPLES))
    path = tmp_path / "out" / "history.json"
    history.save(path)
    assert path.read_text(encoding="utf-8") == history.dumps() and not list(path.parent.glob("*.tmp"))
    assert json.loads(history.dumps())["datasets"] == sorted(history.packages)


def test_empty_root():
    assert latest_package_dirs("/nonexistent/dir") == [] and build_history([]).to_dict()["companies"] == {}
