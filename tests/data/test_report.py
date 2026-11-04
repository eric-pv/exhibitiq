"""Tests for etl.report (D2-09): counted, never estimated."""
from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path

import pytest

from etl.assemble import OfficialCount, assemble_package
from etl.report import build_report, main, to_markdown
from tests.data.test_assemble import CREATED, pipeline

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
V2 = SAMPLES / "sample-fair" / "2026" / "sample-fair-2026.20261104T020000Z"


def make(tmp_path, official=None, **over):
    base = tmp_path / "in"
    base.mkdir(exist_ok=True)
    kwargs = {**pipeline(base), **over}
    return assemble_package(tmp_path / "pkg", **kwargs, official_count=official)


def test_sample_report_counts_match_the_package():
    report = build_report(V2)
    assert report["valid"] and report["data_origin"] == "synthetic"
    assert report["completeness"]["status"] == "complete" and report["completeness"]["listed_participations"] == 4
    assert report["counts"]["participations"] == 5 and report["counts"]["listed"] == 4 and report["counts"]["removed"] == 1 and report["counts"]["changes"] == 5
    assert report["counts"]["crawl_runs_by_status"] and report["field_coverage"]["companies"]["country"] == {"present": 5, "missing": 0}
    assert any("Synthetic test data" in g for g in report["gaps"]) and any("not stored" in g for g in report["gaps"])


def test_unknown_completeness_is_stated_not_guessed(tmp_path):
    report = build_report(make(tmp_path).path)
    assert report["completeness"]["status"] == "unknown" and any("cannot be judged" in g for g in report["gaps"])


def test_difference_to_the_official_count_is_a_difference_not_a_guess(tmp_path):
    base = tmp_path / "in"
    base.mkdir()
    kw = pipeline(base)
    sid = kw["sources"][0]["source_id"]
    report = build_report(assemble_package(tmp_path / "pkg", **kw, official_count=OfficialCount(5, sid)).path)
    assert report["completeness"]["status"] == "partial"
    assert any("official count is 5 but 2 listed" in g and "+3" in g for g in report["gaps"])
    full = build_report(assemble_package(tmp_path / "pkg2", **kw, official_count=OfficialCount(2, sid)).path)
    assert not any("official count is" in g for g in full["gaps"])


def test_possible_duplicates_are_flagged_not_merged(tmp_path):
    base = tmp_path / "in"
    base.mkdir()
    kw = pipeline(base)
    twin = dict(kw["companies"][0], company_id="co_01JCC000000000000000000099", name=kw["companies"][0]["name"].replace("Ltd.", "Inc"))
    twin_part = dict(kw["participations"][0], participation_id="pt_01JCP000000000000000000099", company_id=twin["company_id"])
    package = assemble_package(tmp_path / "pkg", **{**kw, "companies": [*kw["companies"], twin], "participations": [*kw["participations"], twin_part]})
    report = build_report(package.path)
    flag = next(f for f in report["quality_flags"] if f["flag"] == "possible_duplicate_companies")
    assert twin["company_id"] in flag["company_ids"] and report["counts"]["companies"] == 3  # nothing was merged


def test_merged_companies_are_not_flagged_as_duplicates_and_empty_values_do_not_count(tmp_path):
    base = tmp_path / "in"
    base.mkdir()
    kw = pipeline(base)
    first, second = kw["companies"][0], kw["companies"][1]
    merged = dict(second, name=first["name"].replace("Ltd.", "Inc"), status="merged", merged_into=first["company_id"])
    from etl.report import _coverage

    assert _coverage([{"booth": ""}, {"booth": None}, {"booth": "A1"}, {}], ["booth"]) == {"booth": {"present": 1, "missing": 3}}
    report = build_report(assemble_package(tmp_path / "pkg", **{**kw, "companies": [first, merged]}).path)
    assert not any(f["flag"] == "possible_duplicate_companies" for f in report["quality_flags"])


def test_failed_runs_and_missing_booths_are_reported(tmp_path):
    base = tmp_path / "in"
    base.mkdir()
    kw = pipeline(base)
    runs = [dict(kw["crawl_runs"][0], status="partial")]
    parts = [{k: v for k, v in p.items() if k != "booth"} for p in kw["participations"]]
    report = build_report(assemble_package(tmp_path / "pkg", **{**kw, "crawl_runs": runs, "participations": parts}).path)
    assert any("did not fully succeed" in g for g in report["gaps"])
    assert any(f["flag"] == "no_booth_information" for f in report["quality_flags"])
    assert any(f["flag"] == "companies_without_website" for f in report["quality_flags"])


def test_invalid_package_is_reported_as_invalid(tmp_path):
    copy = tmp_path / "copy"
    shutil.copytree(V2, copy)
    manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    manifest["content_hash"] = "sha256:" + "0" * 64
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = build_report(copy)
    assert not report["valid"] and report["validation_findings"]
    assert "FAILED" in to_markdown(report)


def test_markdown_and_cli(tmp_path):
    text = to_markdown(build_report(V2))
    assert text.startswith("# Completeness report: sample-fair-2026") and "## Gaps" in text and "| participations | booth | 5 | 0 |" in text
    out = io.StringIO()
    with redirect_stdout(out):
        assert main([str(V2)]) == 0
    assert out.getvalue() == text
    out = io.StringIO()
    with redirect_stdout(out):
        assert main([str(V2), "--json"]) == 0
    assert json.loads(out.getvalue())["dataset_id"].startswith("sample-fair-2026")
    assert main([str(tmp_path / "missing")]) == 2


def test_cli_exit_code_is_one_for_invalid_packages(tmp_path):
    copy = tmp_path / "copy"
    shutil.copytree(V2, copy)
    (copy / "changes.jsonl").write_text('{"x":1}\n', encoding="utf-8")
    out = io.StringIO()
    with redirect_stdout(out):
        assert main([str(copy)]) == 1
