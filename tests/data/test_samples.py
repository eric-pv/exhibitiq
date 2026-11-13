"""Tests for the synthetic sample exhibitions (D1-06): data/samples/<exhibition_id>/.

Beyond "the validator accepts them", these tests prove what the validator cannot:
raw snapshots hash to what the sources claim, the two exhibitions really differ in
structure, everything is marked synthetic, and the checked-in files are exactly what
the builder produces (so they cannot be hand-edited or silently drift).
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from etl.hashing import sha256_of_bytes
from etl.package import RECORD_SETS, read_package
from etl.validate import validate_package

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"
BUILDER_PATH = SAMPLES / "build_samples.py"

spec = importlib.util.spec_from_file_location("build_samples", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

RESERVED_SUFFIXES = (".example.com", ".example.org", ".example.net")
RESERVED_HOSTS = {"example.com", "example.org", "example.net"}
FORBIDDEN_NAMES = re.compile(r"\b(mspo|tadte|eurosatory|dsei)\b", re.IGNORECASE)


def sample_packages() -> list[Path]:
    found = []
    for name in builder.EXHIBITIONS:
        found += sorted(p.parent for p in (SAMPLES / name).glob("*/*/manifest.json"))
    return found


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from all_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from all_strings(v)


def package_strings(path: Path):
    pkg = read_package(path)
    yield from all_strings(pkg.manifest)
    yield from all_strings(pkg.exhibition)
    yield from all_strings(pkg.edition)
    for rows in pkg.records.values():
        yield from all_strings(rows)


def snapshot_problems(package: Path, repo_root: Path) -> list[str]:
    """Sources stored in Git: the file must exist and hash to the source's content_sha256."""
    problems = []
    for source in read_package(package).records["sources"]:
        snapshot = source["snapshot"]
        if snapshot["storage"] != "git":
            continue
        file = repo_root / snapshot["locator"]
        if not file.is_file():
            problems.append(f"{source['source_id']}: {snapshot['locator']} does not exist")
        elif sha256_of_bytes(file.read_bytes()) != source["content_sha256"]:
            problems.append(f"{source['source_id']}: {snapshot['locator']} does not match content_sha256")
    return problems


# --------------------------------------------------------------------------- presence and validity


def test_there_are_two_exhibitions_and_three_packages() -> None:
    assert {p.parts[-3] for p in sample_packages()} == set(builder.EXHIBITIONS)
    assert len(sample_packages()) == 3


@pytest.mark.parametrize("package", sample_packages(), ids=lambda p: p.name)
def test_every_sample_package_passes_the_validator(package: Path) -> None:
    report = validate_package(package)
    assert report.ok, report.text()


@pytest.mark.parametrize("package", sample_packages(), ids=lambda p: p.name)
def test_every_sample_package_is_marked_synthetic_everywhere(package: Path) -> None:
    pkg = read_package(package)
    assert pkg.manifest["data_origin"] == "synthetic"
    assert "synthetic" in pkg.manifest["notes"]
    for record in (pkg.exhibition, pkg.edition, *(r for rows in pkg.records.values() for r in rows)):
        assert record.get("country", "ZZ") == "ZZ"
    hosts = {urlsplit(s).hostname for s in package_strings(package) if s.startswith("http")}
    assert hosts and all(h in RESERVED_HOSTS or h.endswith(RESERVED_SUFFIXES) for h in hosts), hosts


def test_no_real_exhibition_name_appears_in_any_sample_file() -> None:
    hits = [str(p.relative_to(ROOT)) for p in SAMPLES.rglob("*") if p.is_file() and "__pycache__" not in p.parts and FORBIDDEN_NAMES.search(p.read_text(encoding="utf-8"))]
    assert hits == []


# --------------------------------------------------------------------------- raw snapshots


@pytest.mark.parametrize("package", sample_packages(), ids=lambda p: p.name)
def test_raw_snapshots_exist_and_hash_to_the_sources(package: Path) -> None:
    assert snapshot_problems(package, ROOT) == []


def test_the_snapshot_check_detects_a_changed_or_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(SAMPLES, root / "data" / "samples")
    package = root / "data" / "samples" / "demo-trade-show" / "2025" / "demo-trade-show-2025.20261104T030000Z"
    assert snapshot_problems(package, root) == []
    csv = root / "data" / "samples" / "demo-trade-show" / "raw" / "exhibitors.csv"
    csv.write_bytes(csv.read_bytes() + b"extra,exhibitor,ZZ\n")
    assert any("does not match" in p for p in snapshot_problems(package, root))
    csv.unlink()
    assert any("does not exist" in p for p in snapshot_problems(package, root))


def test_snapshot_contents_agree_with_the_packages() -> None:
    """The raw lists say what the manifests claim: names, total, and number of rows."""
    fair = {p.name: p for p in sample_packages() if p.parts[-3] == "sample-fair"}
    for dataset, raw_name in (("sample-fair-2026.20261104T010000Z", "exhibitors-v1.html"), ("sample-fair-2026.20261104T020000Z", "exhibitors-v2.html")):
        html = (SAMPLES / "sample-fair" / "raw" / raw_name).read_text(encoding="utf-8")
        pkg = read_package(fair[dataset])
        total = int(re.search(r"Total exhibitors: (\d+)", html).group(1))
        assert total == pkg.manifest["completeness"]["official_exhibitor_count"]
        rows = re.findall(r"<tr><td>([^<]+)</td>", html)
        assert len(rows) == pkg.manifest["completeness"]["collected_participation_count"]
        listed = {p["exhibitor_name_as_listed"] for p in pkg.records["participations"] if p["listing_status"] == "listed"}
        assert set(rows) == listed  # exhibitor_name_as_listed keeps the source text exactly (contract §4)
    csv_lines = (SAMPLES / "demo-trade-show" / "raw" / "exhibitors.csv").read_text(encoding="utf-8").splitlines()[1:]
    demo = next(p for p in sample_packages() if p.parts[-3] == "demo-trade-show")
    assert len(csv_lines) == read_package(demo).manifest["completeness"]["collected_participation_count"]


# --------------------------------------------------------------------------- the two really differ


def fields_used(package: Path) -> set[str]:
    pkg = read_package(package)
    fields = set()
    for record in (pkg.exhibition, pkg.edition, *(r for rows in pkg.records.values() for r in rows)):
        fields |= set(record)
    return fields


def describe(exhibition: str) -> dict:
    packages = [p for p in sample_packages() if p.parts[-3] == exhibition]
    pkgs = [read_package(p) for p in packages]
    return {
        "packages": len(packages),
        "fields": set().union(*(fields_used(p) for p in packages)),
        "source_types": {s["source_type"] for pkg in pkgs for s in pkg.records["sources"]},
        "completeness": [pkg.manifest["completeness_status"] for pkg in pkgs],
        "verification": {r["verification_status"] for pkg in pkgs for rows in pkg.records.values() for r in rows if "verification_status" in r},
        "raw_suffixes": {p.suffix for p in (SAMPLES / exhibition / "raw").iterdir()},
        "has_changes": any(pkg.records["changes"] for pkg in pkgs),
        "has_failed_run": any(r["status"] == "failed" for pkg in pkgs for r in pkg.records["crawl_runs"]),
        "has_merged_company": any(c["status"] == "merged" for pkg in pkgs for c in pkg.records["companies"]),
        "has_removed_listing": any(p["listing_status"] == "removed" for pkg in pkgs for p in pkg.records["participations"]),
        "edition_years": {pkg.edition["year"] for pkg in pkgs},
    }


def test_the_two_exhibitions_differ_in_structure() -> None:
    a, b = describe("sample-fair"), describe("demo-trade-show")
    assert a["raw_suffixes"] == {".html"} and b["raw_suffixes"] == {".csv"}
    assert (a["packages"], b["packages"]) == (2, 1)
    assert a["completeness"] == ["partial", "complete"] and b["completeness"] == ["complete"]
    assert a["edition_years"] != b["edition_years"]
    # Each one uses fields the other never does.
    assert a["fields"] - b["fields"] >= {"booth", "hall", "aliases", "domains", "products_as_listed", "merged_into", "field_sources"}
    assert b["fields"] - a["fields"] >= {"error_samples"}
    assert a["source_types"] != b["source_types"] and {"manual_entry", "csv_import"} <= b["source_types"]
    # Features only one of them demonstrates.
    assert (a["has_changes"], a["has_merged_company"], a["has_removed_listing"], a["has_failed_run"]) == (True, True, True, False)
    assert (b["has_changes"], b["has_merged_company"], b["has_removed_listing"], b["has_failed_run"]) == (False, False, False, True)
    assert len(a["fields"] ^ b["fields"]) >= 10
    assert a["verification"] != b["verification"] and "human_confirmed" in b["verification"] and "verified" in a["verification"]


def test_the_failed_run_is_recorded_without_blocking_the_dataset() -> None:
    """V2.3: a failed acquisition is recorded, and the dataset is still valid and complete."""
    demo = next(p for p in sample_packages() if p.parts[-3] == "demo-trade-show")
    pkg = read_package(demo)
    failed = [r for r in pkg.records["crawl_runs"] if r["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["error_samples"][0]["code"] == "access_blocked"
    assert pkg.manifest["completeness_status"] == "complete" and validate_package(demo).ok


def test_sample_fair_v2_chains_to_v1_and_records_what_changed() -> None:
    v1, v2 = (read_package(p) for p in sample_packages() if p.parts[-3] == "sample-fair")
    assert v1.manifest["previous_dataset_id"] is None and v1.records["changes"] == []
    assert v2.manifest["previous_dataset_id"] == v1.manifest["dataset_id"]
    kinds = sorted((c["entity_type"], c["change_type"]) for c in v2.records["changes"])
    assert kinds == sorted([("participation", "modified"), ("participation", "removed"), ("company", "modified"), ("company", "added"), ("participation", "added")])
    merged = next(c for c in v2.records["companies"] if c["status"] == "merged")
    assert merged["merged_into"] in {c["company_id"] for c in v2.records["companies"]}


# --------------------------------------------------------------------------- reproducibility


def tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and p.name != "build_samples.py"}


def test_checked_in_samples_are_exactly_what_the_builder_produces(tmp_path: Path) -> None:
    out = tmp_path / "samples"
    out.mkdir()
    builder.build_all(out)
    expected = tree(out)
    actual = {k: v for k, v in tree(SAMPLES).items() if k.split("/")[0] in builder.EXHIBITIONS}
    assert set(actual) == set(expected)
    assert [k for k in expected if actual[k] != expected[k]] == []


def test_the_builder_is_deterministic(tmp_path: Path) -> None:
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    builder.build_all(one)
    builder.build_all(two)
    assert tree(one) == tree(two)


def test_the_builder_refuses_to_overwrite_a_package(tmp_path: Path) -> None:
    builder.build_all(tmp_path)
    with pytest.raises(ValueError, match="immutable"):
        builder.build_all(tmp_path)


def test_the_builder_uses_the_current_schema_version(tmp_path: Path) -> None:
    builder.build_all(tmp_path, schema_version="9.9.9")
    manifests = [json.loads(p.read_text(encoding="utf-8")) for p in tmp_path.rglob("manifest.json")]
    assert manifests and {m["schema_version"] for m in manifests} == {"9.9.9"}
    default = builder.SCHEMA_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert {read_package(p).manifest["schema_version"] for p in sample_packages()} == {default}


def test_every_record_kind_is_exercised() -> None:
    kinds = {short for p in sample_packages() for short, rows in read_package(p).records.items() if rows}
    assert kinds == set(RECORD_SETS)
