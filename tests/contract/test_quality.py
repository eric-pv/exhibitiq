"""A3-03: recommendation quality checks (QC1-QC9) — warnings on analyses that already pass EV1-EV8."""
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import quality_check as qc  # noqa: E402

G = ROOT / "data" / "samples" / "golden" / "v1"
A = json.loads((G / "expected" / "analysis" / "analysis_result.json").read_text(encoding="utf-8"))
M = json.loads((G / "package" / "manifest.json").read_text(encoding="utf-8"))
TOOLS = ROOT / "skills" / "exhibitiq" / "scripts" / "exhibitiq_tools.py"
CO = {"entity_type": "company", "entity_id": "co_01JDC000000000000000000002"}


def rules(a, m=M):
    return sorted({w["rule"] for w in qc.check_quality(a, m)})


def rec(**kw):
    r = {"recommendation_id": "rec-x", "recommendation_type": "visit_priority", "statement": "另一個建議", "rationale": "r",
         "priority": "low", "based_on_claim_ids": ["cl-002"], "evidence_source_ids": ["src_01JDS000000000000000000001"], "subjects": [CO]}
    r.update(kw)
    return r


def test_shipped_samples_have_no_quality_warnings():
    for an, pkg in [(G / "expected/analysis/analysis_result.json", G / "package"),
                    (ROOT / "schemas/v1/examples/analysis/analysis_result.with_config.example.json", ROOT / "schemas/v1/examples/package")]:
        assert qc.quality_report(an, pkg)["warnings"] == []


def test_each_rule_fires_on_its_weakness():
    a = copy.deepcopy(A)
    a["recommendations"] += [
        rec(recommendation_id="rec-q1", subjects=[]),                                              # QC1
        rec(recommendation_id="rec-q2", recommendation_type="exhibit_product", statement="展示產品"),  # QC2
        rec(recommendation_id="rec-q3", priority="high", statement="高優先度但沒有評分"),             # QC3
        rec(recommendation_id="rec-q4", priority="high", score_ids=["sc-003"], statement="依據資料不足的評分"),  # QC4
        rec(recommendation_id="rec-q6", statement=A["recommendations"][0]["statement"] + " "),     # QC6
        rec(recommendation_id="rec-q9", based_on_claim_ids=["cl-004"], statement="只依據未知"),     # QC9
    ]
    a["conclusions"][1]["confidence"] = "high"                                                    # QC7 (package incomplete)
    a["relationships"][0].update(confidence="high", evidence_source_ids=["src_01JDS000000000000000000001"])  # QC8
    ws = qc.check_quality(a, M)
    got = {(w["rule"], w["id"]) for w in ws}
    for want in [("QC1", "rec-q1"), ("QC2", "rec-q2"), ("QC3", "rec-q3"), ("QC4", "rec-q4"),
                 ("QC6", "rec-q6"), ("QC7", "cl-002"), ("QC8", "rel-001"), ("QC9", "rec-q9")]:
        assert want in got, want


def test_priority_inversion_only_when_scores_disagree():
    a = copy.deepcopy(A)
    a["recommendations"].append(rec(recommendation_id="rec-low", priority="low", score_ids=["sc-002"], statement="低分低優先"))
    assert rules(a) == []  # high on 60% vs low on 20%: consistent
    a["recommendations"][-1]["priority"] = "high"
    a["recommendations"][0]["priority"] = "low"
    assert "QC5" in rules(a)


def test_confidence_rule_depends_on_completeness():
    a = copy.deepcopy(A)
    a["conclusions"][1]["confidence"] = "high"
    assert "QC7" in rules(a)
    assert "QC7" not in rules(a, dict(M, completeness_status="complete"))


def test_cli_reports_warnings_without_blocking():
    out = subprocess.run([sys.executable, str(TOOLS), "quality", str(G / "expected/analysis/analysis_result.json"), str(G / "package")],
                         capture_output=True, text=True, check=True)
    r = json.loads(out.stdout)
    assert r["warnings"] == [] and "不阻止發布" in r["note"]
