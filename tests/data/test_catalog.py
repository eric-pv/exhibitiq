"""Tests for etl.catalog (D3-04): search across packages, an edition's package timeline, and package diffs."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

from etl.catalog import CatalogError, diff_packages, edition_timeline, main, search_companies
from etl.package import COMPUTED_MANIFEST_FIELDS, read_package, write_package
from etl.validate import validate_package

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"
FAIR = SAMPLES / "sample-fair" / "2026"
V1 = FAIR / "sample-fair-2026.20261104T010000Z"
V2 = FAIR / "sample-fair-2026.20261104T020000Z"
DEMO = next((SAMPLES / "demo-trade-show" / "2025").iterdir())


def rewrite(src: Path, dst: Path, edit: Callable[[dict[str, Any]], None]) -> Path:
    """Copy a package through write_package after ``edit`` changed its model (integrity is recomputed)."""
    pkg = read_package(src)
    model = {"manifest": {k: v for k, v in copy.deepcopy(pkg.manifest).items() if k not in COMPUTED_MANIFEST_FIELDS},
             "exhibition": copy.deepcopy(pkg.exhibition), "edition": copy.deepcopy(pkg.edition), "records": copy.deepcopy(pkg.records)}
    edit(model)
    write_package(dst, exhibition=model["exhibition"], edition=model["edition"], records=model["records"], manifest=model["manifest"])
    return dst


def copy_samples(tmp_path: Path) -> Path:
    root = tmp_path / "packages"
    shutil.copytree(SAMPLES, root, ignore=shutil.ignore_patterns("*.py", "__pycache__", "raw"))
    return root


def corrupt(package: Path) -> None:
    """Change one byte of a record so the package stays readable but fails R8 (integrity)."""
    target = package / "companies.jsonl"
    data = target.read_bytes()
    assert b"Sample Mobility Works" in data
    target.write_bytes(data.replace(b"Sample Mobility Works", b"Sample Mobility Workz", 1))


def names(result: dict[str, Any]) -> list[str]:
    return [r["name"] for r in result["results"]]


# ------------------------------------------------------------------------------------------ search


def test_search_without_query_lists_every_company_of_the_latest_valid_packages() -> None:
    result = search_companies(SAMPLES)
    assert result["datasets"] == [DEMO.name, V2.name]  # the older sample-fair package is superseded, not merged
    assert len(result["results"]) == 8 and result["skipped"] == []
    assert names(result) == sorted(names(result), key=str.casefold)
    for hit in result["results"]:
        assert all(p["data_origin"] == "synthetic" and p["source_ids"] for p in hit["participations"])


@pytest.mark.parametrize(
    "query, field",
    [
        ("Synthetic Optics Ltd.", "name"),
        ("synthetic optics", "name"),  # case and the trailing legal form do not matter
        ("ＳＹＮＴＨＥＴＩＣ　ＯＰＴＩＣＳ", "name"),  # full-width letters and space (NFKC)
        ("optics", "name"),  # substring of the exact key
        ("SynOptics", "alias"),
        ("合成光學", "name_zh_hant"),
        ("co_01JFCA00000000000000000001", "company_id"),
        ("www.example.org", "domains"),
        ("example.org", "website"),  # https://www.example.org/synoptics/ : "www." is ignored on both sides
    ],
)
def test_search_matches_names_aliases_ids_and_domains(query: str, field: str) -> None:
    result = search_companies(SAMPLES, query)
    assert names(result) == ["Synthetic Optics Ltd."]
    assert field in {m["field"] for m in result["results"][0]["matched_on"]}


def test_search_ignores_a_legal_form_the_listing_does_not_have() -> None:
    result = search_companies(SAMPLES, "Sample Mobility Works Ltd.")
    assert names(result) == ["Sample Mobility Works"] and result["results"][0]["matched_on"] == [{"field": "name", "value": "Sample Mobility Works"}]


def test_search_misses_return_no_results_and_do_not_guess() -> None:
    assert search_companies(SAMPLES, "Nonexistent Aerospace")["results"] == []
    assert search_companies(SAMPLES, "example.com")["results"] == []  # a host must be equal, not similar
    assert search_companies(SAMPLES, "ample.org")["results"] == []
    with pytest.raises(CatalogError, match="empty"):
        search_companies(SAMPLES, "   ")


def test_search_filters() -> None:
    assert set(names(search_companies(SAMPLES, country="ZZ"))) == {"Synthetic Optics Ltd.", "Sample Mobility Works", "Dummy Sensors Inc.", "Test Harness Labs", "Sample Cyber Range LLC"}
    assert names(search_companies(SAMPLES, exhibition_id="demo-trade-show")) == ["Alpha Demo Co", "Beta Demo Trading", "Gamma Demo Works"]
    assert search_companies(SAMPLES, year=2025)["datasets"] == [DEMO.name]
    assert search_companies(SAMPLES, year=1999)["results"] == []
    removed = search_companies(SAMPLES, listing_status="removed")
    assert [p["listing_status"] for r in removed["results"] for p in r["participations"]] == ["removed"]
    assert len(removed["results"]) == 1


def test_search_copies_participation_facts_and_merge_state() -> None:
    hit = search_companies(SAMPLES, "Dummy Sensors")["results"][0]
    assert hit["status"] == "merged" and hit["merged_into"] == "co_01JFCA00000000000000000001"
    part = hit["participations"][0]
    original = next(p for p in read_package(V2).records["participations"] if p["participation_id"] == part["participation_id"])
    for key in ("listing_status", "exhibitor_name_as_listed", "source_ids"):
        assert part[key] == original[key]
    assert part.get("booth") == original.get("booth")


def test_same_company_in_two_editions_gets_both_participations(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)

    def give_alpha_the_optics_id(m: dict[str, Any]) -> None:
        src = read_package(V2)
        optics = next(c for c in src.records["companies"] if c["company_id"] == "co_01JFCA00000000000000000001")
        old = m["records"]["companies"][0]["company_id"]
        m["records"]["companies"][0] = dict(optics, source_ids=m["records"]["companies"][0]["source_ids"])
        for key in ("aliases", "field_sources", "description", "domains", "website", "name_zh_hant", "first_seen_at", "notes"):
            m["records"]["companies"][0].pop(key, None)
        for part in m["records"]["participations"]:
            if part["company_id"] == old:
                part["company_id"] = optics["company_id"]
        m["records"]["companies"].sort(key=lambda c: c["company_id"].encode())
        m["manifest"]["dataset_id"] = DEMO.name[:-1] + "Z"

    demo_dir = root / "demo-trade-show" / "2025"
    shutil.rmtree(demo_dir)
    rewrite(DEMO, demo_dir / DEMO.name, give_alpha_the_optics_id)
    assert validate_package(demo_dir / DEMO.name).ok, validate_package(demo_dir / DEMO.name).text()
    hit = search_companies(root, "co_01JFCA00000000000000000001")["results"][0]
    assert [p["edition_id"] for p in hit["participations"]] == ["demo-trade-show-2025", "sample-fair-2026"]


def test_invalid_latest_package_is_skipped_with_a_reason(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)
    corrupt(root / "sample-fair" / "2026" / V2.name)
    result = search_companies(root)
    assert result["datasets"] == [DEMO.name] and len(result["skipped"]) == 1
    assert result["skipped"][0]["path"].endswith(V2.name) and "fails validation" in result["skipped"][0]["reason"]
    # the older valid package of that edition is NOT used in its place: "latest" means latest, never a silent fallback
    assert all(p["edition_id"] != "sample-fair-2026" for r in result["results"] for p in r["participations"])


def test_explicit_package_list_and_unreadable_directory(tmp_path: Path) -> None:
    assert search_companies([V1])["datasets"] == [V1.name]
    result = search_companies([tmp_path / "nothing-here"])
    assert result["results"] == [] and len(result["skipped"]) == 1 and "fails validation" in result["skipped"][0]["reason"]
    assert search_companies(tmp_path / "absent")["datasets"] == []


# ---------------------------------------------------------------------------------------- timeline


def test_timeline_of_the_sample_edition() -> None:
    t = edition_timeline(SAMPLES, "sample-fair", 2026)
    assert [p["dataset_id"] for p in t["packages"]] == [V1.name, V2.name] and t["notices"] == []
    assert t["latest_valid_dataset_id"] == V2.name
    first, second = t["packages"]
    assert first["previous_dataset_id"] is None and second["previous_dataset_id"] == V1.name
    assert first["recorded_changes"]["participation"] == {"added": 0, "modified": 0, "removed": 0}
    recorded = read_package(V2).records["changes"]
    assert sum(sum(v.values()) for v in second["recorded_changes"].values()) == len(recorded)
    manifest = read_package(V2).manifest
    assert second["record_counts"] == manifest["record_counts"] and second["completeness_status"] == manifest["completeness_status"]
    assert second["official_exhibitor_count"] == manifest["completeness"]["official_exhibitor_count"]


def test_timeline_reports_chain_breaks(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)
    edition = root / "sample-fair" / "2026"
    third = "sample-fair-2026.20261104T030000Z"
    def edit(m: dict[str, Any]) -> None:
        m["manifest"].update(dataset_id=third, created_at="2026-11-04T03:00:00Z", previous_dataset_id=V1.name)
        for change in m["records"]["changes"]:
            change.update(dataset_id=third, previous_dataset_id=V1.name)

    rewrite(V2, edition / third, edit)
    assert validate_package(edition / third).ok
    notices = edition_timeline(root, "sample-fair", 2026)["notices"]
    assert notices == [f"{third}: previous_dataset_id {V1.name} skips {V2.name}"]


@pytest.mark.parametrize(
    "previous, expected",
    [
        (None, "previous_dataset_id is null although older packages exist"),
        ("sample-fair-2026.20250101T000000Z", "is not a package of this edition"),
    ],
)
def test_timeline_reports_restarts_and_dangling_links(tmp_path: Path, previous: str | None, expected: str) -> None:
    root = copy_samples(tmp_path)
    edition = root / "sample-fair" / "2026"
    third = "sample-fair-2026.20261104T030000Z"

    def edit(m: dict[str, Any]) -> None:
        m["manifest"].update(dataset_id=third, created_at="2026-11-04T03:00:00Z", previous_dataset_id=previous)
        if previous is None:
            m["records"]["changes"] = []
        else:
            for change in m["records"]["changes"]:
                change.update(dataset_id=third, previous_dataset_id=previous)

    rewrite(V2, edition / third, edit)
    assert validate_package(edition / third).ok, validate_package(edition / third).text()
    notices = edition_timeline(root, "sample-fair", 2026)["notices"]
    assert len(notices) == 1 and notices[0].startswith(third) and expected in notices[0]


def test_timeline_marks_invalid_packages_and_never_picks_or_reads_them(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)
    edition = root / "sample-fair" / "2026"
    corrupt(edition / V2.name)
    (edition / "sample-fair-2026.20261104T090000Z").mkdir()  # an empty directory: every file missing (R1)
    t = edition_timeline(root, "sample-fair", 2026)
    status = {p["dataset_id"]: p["validation"] for p in t["packages"]}
    assert status == {V1.name: "passed", V2.name: "failed", "sample-fair-2026.20261104T090000Z": "failed"}
    assert t["latest_valid_dataset_id"] == V1.name
    failed = next(p for p in t["packages"] if p["dataset_id"] == V2.name)
    assert set(failed) == {"dataset_id", "path", "validation", "reason"} and "fails validation" in failed["reason"]
    assert sum("not used in the history" in n for n in t["notices"]) == 2 and len(t["notices"]) == 2


def test_timeline_link_to_an_invalid_package_names_the_reason(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)
    edition = root / "sample-fair" / "2026"
    corrupt(edition / V1.name)
    notices = edition_timeline(root, "sample-fair", 2026)["notices"]
    assert f"{V2.name}: previous_dataset_id {V1.name} fails validation" in notices


def test_timeline_of_a_missing_edition_is_an_input_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="no packages"):
        edition_timeline(SAMPLES, "sample-fair", 1999)


# -------------------------------------------------------------------------------------------- diff


def test_diff_of_the_sample_versions_agrees_with_the_recorded_changes() -> None:
    d = diff_packages(V1, V2)
    recorded = read_package(V2).records["changes"]
    assert {(c["entity_type"], c["entity_id"], c["change_type"]) for c in d["changes"]} == {(c["entity_type"], c["entity_id"], c["change_type"]) for c in recorded}
    assert d["recorded_comparison"] == {"only_recomputed": [], "only_recorded": []}
    assert sum(sum(v.values()) for v in d["summary"].values()) == len(d["changes"]) == len(recorded)
    assert d["older"]["dataset_id"] == V1.name and d["newer"]["dataset_id"] == V2.name and d["newer"]["data_origin"] == "synthetic"
    assert all("change_id" not in c and "detected_at" not in c for c in d["changes"])  # no invented ids or times


def test_diff_is_deterministic_and_identity_is_empty(tmp_path: Path) -> None:
    assert diff_packages(V1, V2) == diff_packages(V1, V2)
    same = rewrite(V1, tmp_path / "sample-fair-2026.20261104T015000Z", lambda m: m["manifest"].update(dataset_id="sample-fair-2026.20261104T015000Z", created_at="2026-11-04T01:50:00Z"))
    d = diff_packages(V1, same)
    assert d["changes"] == [] and "recorded_comparison" not in d  # same doesn't name V1 as previous


def test_diff_reports_disagreement_with_the_recorded_changes(tmp_path: Path) -> None:
    def drop_one(m: dict[str, Any]) -> None:
        m["records"]["changes"] = m["records"]["changes"][1:]
    edited = rewrite(V2, tmp_path / V2.name, drop_one)
    assert validate_package(edited).ok
    dropped = read_package(V2).records["changes"][0]
    comparison = diff_packages(V1, edited)["recorded_comparison"]
    assert comparison["only_recorded"] == []
    assert comparison["only_recomputed"] == [{"entity_type": dropped["entity_type"], "entity_id": dropped["entity_id"], "change_type": dropped["change_type"]}]


def test_diff_input_errors(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="different editions"):
        diff_packages(V1, DEMO)
    with pytest.raises(CatalogError, match="give the older package first"):
        diff_packages(V2, V1)
    with pytest.raises(CatalogError, match="same package"):
        diff_packages(V1, V1)
    broken = tmp_path / V2.name
    shutil.copytree(V2, broken)
    corrupt(broken)
    with pytest.raises(CatalogError, match="fails validation"):
        diff_packages(V1, broken)


# --------------------------------------------------------------------------------------------- CLI


def test_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["search", "--packages", str(SAMPLES), "SynOptics"]) == 0
    assert [r["name"] for r in json.loads(capsys.readouterr().out)["results"]] == ["Synthetic Optics Ltd."]
    assert main(["timeline", "--packages", str(SAMPLES), "sample-fair", "2026"]) == 0
    assert json.loads(capsys.readouterr().out)["latest_valid_dataset_id"] == V2.name
    assert main(["diff", str(V1), str(V2)]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "diff"
    assert main(["diff", str(V2), str(V1)]) == 2
    assert "error:" in capsys.readouterr().err


def test_catalog_never_writes_into_the_packages(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    search_companies(root, "optics")
    edition_timeline(root, "sample-fair", 2026)
    diff_packages(root / "sample-fair" / "2026" / V1.name, root / "sample-fair" / "2026" / V2.name)
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_timeline_reports_a_link_to_a_newer_package(tmp_path: Path) -> None:
    root = copy_samples(tmp_path)
    edition = root / "sample-fair" / "2026"
    middle = "sample-fair-2026.20261104T015000Z"

    def edit(m: dict[str, Any]) -> None:
        m["manifest"].update(dataset_id=middle, created_at="2026-11-04T01:50:00Z", previous_dataset_id=V2.name)
        for change in m["records"]["changes"]:
            change.update(dataset_id=middle, previous_dataset_id=V2.name)

    rewrite(V2, edition / middle, edit)
    assert validate_package(edition / middle).ok
    assert edition_timeline(root, "sample-fair", 2026)["notices"] == [
        f"{middle}: previous_dataset_id {V2.name} is not older",
        f"{V2.name}: previous_dataset_id {V1.name} skips {middle}",
    ]
