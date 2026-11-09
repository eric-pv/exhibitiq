"""Tests for etl.import_file (D2-02): one file -> evidence -> records -> quality gate -> package, from the command line."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawler.store import verify_run
from etl.import_file import load_info, main
from etl.package import read_package
from etl.validate import validate_package

CONFIG = """\
name = "test-list"
exhibition_id = "example-expo"
edition_id = "example-expo-2026"
source_type = "csv_import"
start_urls = ["https://files.example.com/list.csv"]
allowed_domains = ["example.com"]
adapter = "file-import"

[options.mapping]
format = "csv"
[[options.mapping.columns]]
source = "Company"
field = "exhibitor_name_as_listed"
required = true
[[options.mapping.columns]]
source = "Booth"
field = "booth"
"""
INFO = {"exhibition": {"name": "Example Expo"}, "edition": {"year": 2026, "name": "Example Expo 2026"}}
FULL = "Company,Booth\nAlpha Synthetic Ltd,A1\nBeta Synthetic,B2\nGamma Synthetic,C3\nDelta Synthetic,D4\n"


@pytest.fixture()
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "source.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "info.json").write_text(json.dumps(INFO), encoding="utf-8")
    return tmp_path


def run(work: Path, csv: str, *extra: str) -> int:
    (work / "list.csv").write_text(csv, encoding="utf-8")
    return main(["--config", "source.toml", "--file", "list.csv", "--info", "info.json", "--data-origin", "synthetic", *extra])


def packages(work: Path) -> list[Path]:
    return sorted((work / "data" / "packages" / "example-expo" / "2026").glob("*"))


def test_first_import_writes_evidence_a_valid_package_and_the_registry(work: Path, capsys) -> None:
    assert run(work, FULL, "--official-count", "4", "--official-as-of", "2026-11-09", "--created-at", "2026-11-09T09:00:00Z", "--notes", "how it was obtained") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["published"] and out["dataset_id"] == "example-expo-2026.20261109T090000Z" and out["completeness_status"] == "complete"
    [package] = packages(work)
    assert validate_package(package).ok
    pkg = read_package(package)
    assert pkg.manifest["notes"] == "how it was obtained" and pkg.manifest["data_origin"] == "synthetic"
    assert pkg.exhibition["name"] == "Example Expo" and pkg.exhibition["source_ids"] == [pkg.records["sources"][0]["source_id"]]
    assert pkg.edition["verification_status"] == "unverified" and len(pkg.records["participations"]) == 4
    assert verify_run(work / out["run_dir"]) == []
    assert pkg.records["sources"][0]["snapshot"]["locator"].startswith("data/raw/example-expo/example-expo-2026/")
    assert (work / "data" / "registry" / "companies.json").is_file()


def test_second_import_carries_forward_and_records_changes(work: Path, capsys) -> None:
    assert run(work, FULL, "--created-at", "2026-11-09T09:00:00Z") == 0
    capsys.readouterr()
    assert run(work, FULL.replace("Delta Synthetic,D4\n", "Delta Synthetic,D5\n"), "--created-at", "2026-11-09T10:00:00Z") == 0
    out = json.loads(capsys.readouterr().out)
    first, second = packages(work)
    assert out["previous_dataset_id"] == first.name
    pkg = read_package(second)
    assert pkg.manifest["previous_dataset_id"] == first.name and validate_package(second).ok
    assert [(c["change_type"], c["field_changes"]) for c in pkg.records["changes"]] == [("modified", [{"field": "booth", "before": "D4", "after": "D5"}])]
    ids = lambda p: sorted(c["company_id"] for c in read_package(p).records["companies"])  # noqa: E731
    assert ids(first) == ids(second)  # the registry keeps company ids stable
    assert len(pkg.records["sources"]) == 2  # evidence accumulates


def test_the_quality_gate_stops_a_near_empty_list_keeps_evidence_and_publishes_nothing(work: Path, capsys) -> None:
    assert run(work, FULL, "--created-at", "2026-11-09T09:00:00Z") == 0
    registry_before = (work / "data" / "registry" / "companies.json").read_bytes()
    capsys.readouterr()
    assert run(work, "Company,Booth\nAlpha Synthetic Ltd,A1\n", "--created-at", "2026-11-09T10:00:00Z") == 1
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert not out["published"] and [q["code"] for q in out["quality"] if q["level"] == "block"] == ["Q3"]
    assert "nothing was published" in captured.err
    assert len(packages(work)) == 1
    assert verify_run(work / out["run_dir"]) == []  # the evidence of the attempt is kept
    assert (work / "data" / "registry" / "companies.json").read_bytes() == registry_before
    # a person who checked the source accepts the drop
    assert run(work, "Company,Booth\nAlpha Synthetic Ltd,A1\n", "--created-at", "2026-11-09T11:00:00Z", "--accept", "Q3") == 0
    latest = read_package(packages(work)[-1])
    assert sum(p["listing_status"] == "removed" for p in latest.records["participations"]) == 3


def test_header_only_file_is_blocked(work: Path, capsys) -> None:
    assert run(work, "Company,Booth\n") == 1
    assert [q["code"] for q in json.loads(capsys.readouterr().out)["quality"]] == ["Q2"]
    assert packages(work) == []


@pytest.mark.parametrize("info, message", [
    ({"exhibition": {}}, "expected"),
    ({"exhibition": {"name": "x"}, "edition": {"name": "y"}}, "edition.year"),
    ({"exhibition": {"name": "x", "source_ids": ["s"]}, "edition": {"year": 2026}}, "must not set source_ids"),
])
def test_bad_info_is_refused(tmp_path: Path, info, message) -> None:
    path = tmp_path / "info.json"
    path.write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_info(path)


def test_bad_input_exits_2_before_anything_is_written(work: Path, capsys) -> None:
    assert main(["--config", "source.toml", "--file", "missing.csv", "--info", "info.json"]) == 2
    (work / "bad.toml").write_text("name = 1\n", encoding="utf-8")
    assert main(["--config", "bad.toml", "--file", "source.toml", "--info", "info.json"]) == 2
    assert not (work / "data").exists()
