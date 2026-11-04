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
