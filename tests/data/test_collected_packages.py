"""Every committed data package under data/packages/ (D2-02): valid, evidence intact, reproducible, and equal to what
its source config reads from the stored snapshot today. Generic: no exhibition is named here."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import crawler.file_import  # noqa: F401
import crawler.pdf_layout_table  # noqa: F401
import crawler.printed_listing  # noqa: F401
from crawler.adapters import default_registry, resolve_adapter
from crawler.models import Request, Response
from crawler.source_config import load_source_config
from etl.integrity import check_regenerable, verify_snapshots
from etl.normalize import clean_text, name_keys
from etl.package import read_package
from etl.validate import validate_package

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = sorted(p for p in (ROOT / "data" / "packages").glob("*/*/*") if (p / "manifest.json").is_file())
CONFIGS = {load_source_config(p).edition_id: load_source_config(p) for p in (ROOT / "data" / "sources").glob("*/*.toml")}


def test_there_is_at_least_one_collected_package() -> None:
    assert PACKAGES and all(read_package(p).manifest["data_origin"] == "collected" for p in PACKAGES)


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_valid_with_evidence_and_reproducible(package: Path) -> None:
    assert validate_package(package).ok, validate_package(package).text()
    snapshots = verify_snapshots(package, ROOT)
    assert snapshots["problems"] == [] and snapshots["verified"]
    assert check_regenerable(package) == []


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_the_source_config_reads_the_same_list_from_the_snapshot(package: Path) -> None:
    pkg = read_package(package)
    config = CONFIGS.get(pkg.manifest["edition_id"])
    if config is None:
        pytest.skip("no source config for this edition in data/sources/")
    adapter = resolve_adapter(config, default_registry)
    listed = [p for p in pkg.records["participations"] if p["listing_status"] == "listed"]
    found_names: set[str] = set()
    found_booths: set[str] = set()
    exact_names: set[str] = set()
    list_sources = [s for s in pkg.records["sources"] if s["source_type"] == config.source_type and s.get("url") in config.start_urls]
    assert list_sources, "no source of the list's own config in the package"
    for source in list_sources:  # other sources (e.g. exhibitors' websites added by etl.enrich) are not the list
        data = (ROOT / source["snapshot"]["locator"]).read_bytes()
        response = Response(source["url"], source["url"], 200, {}, data, source.get("media_type"))
        parsed = adapter.parse(response, Request(source["url"]), config)
        assert parsed.warnings == []
        # build_records stores names cleaned with etl.normalize.clean_text (NFKC: "™" -> "TM", full-width -> ASCII)
        found_names |= {name_keys(r["exhibitor_name_as_listed"]).exact for r in parsed.records}
        exact_names |= {clean_text(r["exhibitor_name_as_listed"]) for r in parsed.records}
        found_booths |= {clean_text(r["booth"]) for r in parsed.records if r.get("booth")}
    # rows listed under the same name key are one participation (the other spellings and booths go to notes/aliases)
    assert found_names == {name_keys(p["exhibitor_name_as_listed"]).exact for p in listed}
    # (the same name with different countries stays separate companies, so there can be more participations than keys)
    # every spelling read today is in the package, exactly (spaces included): as the listed name or as an alias
    spellings = {p["exhibitor_name_as_listed"] for p in listed} | {a["name"] for c in pkg.records["companies"] for a in c.get("aliases", [])}
    assert exact_names <= spellings, sorted(exact_names - spellings)[:10]
    kept = " | ".join(f"{p.get('booth', '')} {p.get('notes', '')}" for p in listed)
    assert all(booth in kept for booth in found_booths)
    expected = found_names
    completeness = pkg.manifest["completeness"]
    if completeness["official_exhibitor_count"] is not None:
        assert pkg.manifest["completeness_status"] == ("complete" if completeness["official_exhibitor_count"] == len(expected) else "partial")


def test_the_index_points_at_the_latest_valid_package() -> None:
    index = json.loads((ROOT / "data" / "index" / "datasets.json").read_text(encoding="utf-8"))
    latest = {ed["latest_dataset_id"] for ex in index["exhibitions"] for ed in ex["editions"]}
    newest = {}
    for p in PACKAGES:
        newest[p.parent] = max(newest.get(p.parent, ""), p.name)
    assert latest == set(newest.values())
