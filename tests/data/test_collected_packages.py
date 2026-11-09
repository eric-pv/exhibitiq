"""Every committed data package under data/packages/ (D2-02): valid, evidence intact, reproducible, and equal to what
its source config reads from the stored snapshot today. Generic: no exhibition is named here."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import crawler.file_import  # noqa: F401
import crawler.printed_listing  # noqa: F401
from crawler.adapters import default_registry, resolve_adapter
from crawler.models import Request, Response
from crawler.source_config import load_source_config
from etl.integrity import check_regenerable, verify_snapshots
from etl.normalize import clean_text
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
    expected = {(p["exhibitor_name_as_listed"], p.get("booth")) for p in pkg.records["participations"] if p["listing_status"] == "listed"}
    found: set[tuple[str, str | None]] = set()
    for source in pkg.records["sources"]:
        data = (ROOT / source["snapshot"]["locator"]).read_bytes()
        response = Response(source["url"], source["url"], 200, {}, data, source.get("media_type"))
        parsed = adapter.parse(response, Request(source["url"]), config)
        # build_records stores names cleaned with etl.normalize.clean_text (NFKC: "™" -> "TM", full-width -> ASCII)
        found |= {(clean_text(r["exhibitor_name_as_listed"]), clean_text(r["booth"]) if r.get("booth") else None) for r in parsed.records}
        assert parsed.warnings == []
    assert found == expected
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
