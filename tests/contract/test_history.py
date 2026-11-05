"""A3-04: multi-year history of one exhibition (profile_tools.history, `exhibitiq_tools.py trend`)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import profile_tools as pt  # noqa: E402

G = ROOT / "data" / "samples" / "golden" / "v1" / "package"
EX = ROOT / "schemas" / "v1" / "examples" / "package"
TOOLS = ROOT / "skills" / "exhibitiq" / "scripts" / "exhibitiq_tools.py"


def _year(tmp, year, complete, drop=0, src=G):
    d = tmp / f"y{year}"
    shutil.copytree(src, d)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m.update(edition_year=year, dataset_id=f"{m['dataset_id']}-{year}", completeness_status="complete" if complete else "partial")
    (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    if drop:  # this year's list misses the first `drop` companies
        lines = (d / "participations.jsonl").read_text(encoding="utf-8").splitlines()
        (d / "participations.jsonl").write_text("\n".join(lines[drop:]) + "\n", encoding="utf-8")
    return d


def test_one_year_is_insufficient_never_a_trend():
    r = pt.history([G])
    assert r["status"] == "insufficient" and "資料不足" in r["status_note"] and r["year_over_year"] == []


def test_complete_years_give_returning_new_and_not_seen_again(tmp_path):
    a, b = _year(tmp_path, 2024, True), _year(tmp_path, 2025, True, drop=1)
    r = pt.history([b, a])  # any order -> oldest first
    assert r["status"] == "ok" and [y["year"] for y in r["years"]] == [2024, 2025]
    step = r["year_over_year"][0]
    n24, n25 = r["years"][0]["collected_company_count"], r["years"][1]["collected_company_count"]
    assert step["returning"]["count"] == n25 and step["not_seen_again"]["count"] == n24 - n25 == 1
    assert step["new"]["count"] == 0 and step["notes"] == []


def test_incomplete_years_never_claim_new_or_dropped(tmp_path):
    a, b = _year(tmp_path, 2024, False), _year(tmp_path, 2025, False, drop=1)
    step = pt.history([a, b])["year_over_year"][0]
    assert step["returning"]["count"] >= 1  # seen in both packages: a fact
    assert step["new"] is None and step["not_seen_again"] is None and len(step["notes"]) == 2
    assert all("資料不完整" in n for n in step["notes"])
    assert all(x["share"] is None for s in pt.history([a, b])["keyword_series"].values() for x in s)


def test_rejects_mixed_exhibitions_and_duplicate_years(tmp_path):
    with pytest.raises(ValueError):
        pt.history([G, EX])
    with pytest.raises(ValueError):
        (tmp_path / "x").mkdir()
        pt.history([_year(tmp_path, 2024, True), _year(tmp_path / "x", 2024, True)])


def test_works_without_bxr_profile(tmp_path):
    fire = json.loads((ROOT / "schemas/v1/examples/profile/analysis_profile.industry.example.json").read_text(encoding="utf-8"))
    r = pt.history([_year(tmp_path, 2024, True), _year(tmp_path, 2025, True)], fire)
    assert r["mode"] == "industry_research" and set(r["keyword_series"]) == {k["term_id"] for k in fire["keywords"] if k["enabled"]}


def test_cli_trend_reads_the_index_and_reports_no_package_clearly():
    out = subprocess.run([sys.executable, str(TOOLS), "trend", "example-expo"], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout)["status"] == "insufficient"
    bad = subprocess.run([sys.executable, str(TOOLS), "trend", "sample-fair"], capture_output=True, text=True)
    assert bad.returncode == 2 and "no validated package" in bad.stderr
