"""A2-03: Skill helper scripts."""
from __future__ import annotations

import importlib.util
import json

import pytest

import package_check as pc

spec = importlib.util.spec_from_file_location("exhibitiq_tools", pc.ROOT / "skills" / "exhibitiq" / "scripts" / "exhibitiq_tools.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)
G = pc.ROOT / "data" / "samples" / "golden" / "v1"
EX_INDEX = pc.SCHEMA_DIR / "examples" / "index" / "dataset_index.example.json"


def test_select_latest_validated_package():
    r = tools.select_package(G / "dataset_index.json", "golden-fair")
    assert r["dataset_id"].startswith("golden-fair-2025.") and r["data_origin"] == "synthetic"


def test_select_refuses_exhibition_without_package():
    with pytest.raises(LookupError, match="no validated package"):
        tools.select_package(EX_INDEX, "sample-fair")
    with pytest.raises(LookupError, match="not in the dataset index"):
        tools.select_package(EX_INDEX, "unregistered-fair")


def test_validate_package_and_analysis_on_golden():
    assert tools.validate_package(G / "package")["ok"]
    assert tools.validate_analysis(G / "expected" / "analysis" / "analysis_result.json", G / "package")["ok"]


def test_validate_analysis_rejects_tampered(tmp_path):
    a = json.loads((G / "expected" / "analysis" / "analysis_result.json").read_text(encoding="utf-8"))
    a["scores"][0]["total_points"] = 99
    p = tmp_path / "a.json"
    p.write_text(json.dumps(a), encoding="utf-8")
    assert not tools.validate_analysis(p, G / "package")["ok"]


def test_report_is_built_only_from_analysis():
    a = json.loads((G / "expected" / "analysis" / "analysis_result.json").read_text(encoding="utf-8"))
    md = tools.render_report(G / "expected" / "analysis" / "analysis_result.json", G / "package")
    for c in a["conclusions"]:
        assert c["statement"] in md
    assert "合成資料" in md and "官方公布 未知" in md and "[AI 推論]" in md and "資料不足，不計分" in md
    for sid in a["evidence_source_ids"]:
        assert sid in md


def test_cli_exit_codes():
    assert tools.main(["select", "sample-fair", "--index", str(EX_INDEX)]) == 2
    assert tools.main(["validate-package", str(G / "package")]) == 0


def test_check_all_reports_every_edition():
    rows = tools.check_all(EX_INDEX)
    by = {r["edition_id"]: r for r in rows}
    assert by["example-expo-2026"]["ok"]
    assert by["sample-fair-2026"]["dataset_id"] is None and "no validated package" in by["sample-fair-2026"]["problems"][0]
    assert tools.check_all(G / "dataset_index.json")[0]["ok"]


def test_check_all_detects_hash_mismatch(tmp_path):
    idx = json.loads(EX_INDEX.read_text(encoding="utf-8"))
    idx["exhibitions"][0]["editions"][0]["datasets"][0]["content_hash"] = "sha256:" + "0" * 64
    p = tmp_path / "idx.json"
    p.write_text(json.dumps(idx), encoding="utf-8")
    row = tools.check_all(p)[0]
    assert not row["ok"] and any("content_hash" in x for x in row["problems"])


def test_classify_golden_candidates():
    r = tools.classify(G / "package")
    alpha = next(v for k, v in r.items() if k.endswith("C000000000000000000001"))
    assert {"application.training", "technology.simulation"} <= set(alpha["terms"]) and alpha["source_ids"]
    delta = next(v for k, v in r.items() if k.endswith("C000000000000000000004"))
    assert "technology.sensors" in delta["terms"]


def test_score_is_explainable_and_schema_valid():
    import analysis_check
    scores = tools.score(G / "package")
    assert [s["rank"] for s in scores] == [1, 2, 3]
    for s in scores:
        for f in s["factors"]:
            if f["status"] == "insufficient_data":
                assert f["points"] == 0
            else:
                assert f["evidence_source_ids"]
    # drop the scores into the golden analysis and validate AR1-AR9
    a = json.loads((G / "expected" / "analysis" / "analysis_result.json").read_text(encoding="utf-8"))
    a["scores"] = scores
    for r in a["recommendations"]:
        r["score_ids"] = [scores[0]["score_id"]]
    ev = set()
    for c in a["conclusions"]:
        ev |= set(c.get("evidence_source_ids", []))
    for s in scores:
        for f in s["factors"]:
            ev |= set(f.get("evidence_source_ids", []))
    for k in ("relationships", "recommendations"):
        for r in a[k]:
            ev |= set(r["evidence_source_ids"])
    a["evidence_source_ids"] = sorted(ev)
    assert analysis_check.check_analysis(a, G / "package") == []
    top = scores[0]
    assert top["subject"]["entity_id"].endswith("C000000000000000000001")
    assert next(f for f in top["factors"] if f["factor_id"] == "product_fit")["status"] == "insufficient_data"


ROOT = pc.ROOT


def test_report_follows_template_and_refuses_invalid(tmp_path):
    """A2-12/A2-13: sections follow templates/report-templates.json; invalid analyses are not rendered."""
    import pytest
    tpl = json.loads((ROOT / "skills/exhibitiq/templates/report-templates.json").read_text(encoding="utf-8"))
    ex = ROOT / "schemas/v1/examples"
    md = tools.render_report(ex / "analysis/analysis_result.example.json", ex / "package")
    heads = [l[3:] for l in md.splitlines() if l.startswith("## ")]
    want = [tpl["section_titles"][s] for s in tpl["types"]["opportunity_ranking"]["sections"]]
    assert heads == want
    assert "Synthetic Simulation Systems Ltd." in md and "（AI 推論" in md
    bad = json.loads((ex / "analysis/analysis_result.example.json").read_text(encoding="utf-8"))
    bad["scores"][0]["factors"][0]["evidence_source_ids"] = []
    p = tmp_path / "bad.json"; p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(LookupError):
        tools.render_report(p, ex / "package")
    assert set(tpl["types"]) == set(json.loads((ROOT / "schemas/v1/analysis_result.schema.json").read_text(encoding="utf-8"))["properties"]["analysis_type"]["enum"])


def test_report_analysis_config_section_and_unapproved_products_warning(tmp_path):
    """A2-17: every report shows the analysis settings; draft BXR cards trigger the 產品資料未核定 warning."""
    ex = ROOT / "schemas/v1/examples"
    old = tools.render_report(ex / "analysis/analysis_result.example.json", ex / "package")
    assert "## 分析設定" in old and "沒有記錄分析設定" in old
    a = json.loads((ex / "analysis/analysis_result.with_config.example.json").read_text(encoding="utf-8"))
    md = tools.render_report(ex / "analysis/analysis_result.with_config.example.json", ex / "package")
    assert a["analysis_config"]["profile_hash"] in md and "A. BXR 商機分析" in md and "產品資料未核定" not in md
    a["analysis_config"]["bxr_products_status"] = "draft"
    p = tmp_path / "a.json"; p.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    assert "產品資料未核定" in tools.render_report(p, ex / "package")
