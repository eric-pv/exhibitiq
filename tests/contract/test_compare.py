"""A2-09: cross-package comparison and keyword trends (profile_tools.compare)."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import profile_tools as pt  # noqa: E402

EX = ROOT / "schemas" / "v1" / "examples" / "package"
G = ROOT / "data" / "samples" / "golden" / "v1" / "package"


def test_two_different_exhibitions_compare_without_trend_claim():
    r = pt.compare([EX, G])
    assert len(r["packages"]) == 2 and r["trend_note"]  # different exhibitions -> no time trend
    for p in r["packages"]:
        assert p["completeness_status"] != "complete"
        for k in p["keywords"].values():
            assert k["share"] is None  # incomplete data -> no ratio, never estimated
            assert k["count"] == len(k["company_ids"])
            if k["count"]:
                assert k["source_ids"]


def _year_copy(tmp, src, year, complete):
    d = tmp / f"y{year}"
    shutil.copytree(src, d)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m.update(edition_year=year, dataset_id=f"{m['dataset_id']}-{year}", completeness_status="complete" if complete else "partial")
    (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return d


def test_same_exhibition_two_years_gives_series_shared_companies_and_shares(tmp_path):
    a, b = _year_copy(tmp_path, G, 2024, True), _year_copy(tmp_path, G, 2025, True)
    r = pt.compare([b, a])
    assert r["trend_note"] is None and [p["year"] for p in r["packages"]] == [2024, 2025]
    assert r["shared_companies"]  # the same company_ids appear in both years
    s = r["keyword_series"]["application.training"]
    assert [x["year"] for x in s] == [2024, 2025] and all(x["share"] is not None for x in s)


def test_works_for_any_profile_without_bxr(tmp_path):
    fire = json.loads((ROOT / "schemas/v1/examples/profile/analysis_profile.industry.example.json").read_text(encoding="utf-8"))
    r = pt.compare([G], fire)
    assert r["mode"] == "industry_research" and set(r["keyword_series"]) == {k["term_id"] for k in fire["keywords"] if k["enabled"]}
