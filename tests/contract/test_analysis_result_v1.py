"""Contract tests for the analysis-result schema v1 (A1-06)."""
from __future__ import annotations

import copy
import json

import pytest

import analysis_check as ac
import package_check as pc

EXAMPLE = pc.SCHEMA_DIR / "examples" / "analysis" / "analysis_result.example.json"
PKG = pc.SCHEMA_DIR / "examples" / "package"
SA, SB = "src_01JCS000000000000000000001", "src_01JCS000000000000000000002"


def base() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def claim(r, cid):
    return next(c for c in r["conclusions"] if c["claim_id"] == cid)


def schema_errors(r) -> list:
    return list(pc.validator("analysis_result").iter_errors(r))


# ------------------------------------------------------------------ positive
def test_example_is_valid_against_schema_and_rules():
    assert ac.check_analysis(base(), PKG) == []


def test_spec_required_fields():
    # docs/ExhibitIQ_專案總規範.md §6
    required = set(pc.load_schemas()["analysis_result"]["required"])
    for f in ["analysis_id", "input_dataset_id", "input_hash", "skill_version", "generated_at",
              "evidence_source_ids", "conclusions", "uncertainties", "recommendations", "review_status"]:
        assert f in required


def test_schema_version_matches_version_file():
    s = pc.load_schemas()["analysis_result"]
    assert pc.VERSION in s["properties"]["schema_version"]["enum"] and set(s["properties"]["schema_version"]["enum"]) == pc.ACCEPTED


def test_example_covers_all_claim_types_and_factor_statuses():
    r = base()
    assert {c["claim_type"] for c in r["conclusions"]} == {"fact", "inference", "unknown"}
    assert {f["status"] for s in r["scores"] for f in s["factors"]} == {"scored", "insufficient_data"}


# ------------------------------------------------------------------ negative: schema
def _del(path):
    def f(r):
        *parents, last = path
        for p in parents:
            r = r[p]
        del r[last]
    return f


def _set(path, value):
    def f(r):
        *parents, last = path
        for p in parents:
            r = r[p]
        r[last] = value
    return f


C = ["conclusions"]
F0 = ["scores", 0, "factors", 0]  # scored factor
F2 = ["scores", 0, "factors", 2]  # insufficient_data factor
REL = ["relationships", 0]
REC = ["recommendations", 0]

SCHEMA_NEGATIVE = [
    ("fact-without-evidence", _del(C + [0, "evidence_source_ids"])),
    ("fact-empty-evidence", _set(C + [0, "evidence_source_ids"], [])),
    ("fact-insufficient-status", _set(C + [0, "verification_status"], "insufficient_data")),
    ("fact-ai-inferred-status", _set(C + [0, "verification_status"], "ai_inferred")),
    ("inference-without-evidence", _del(C + [1, "evidence_source_ids"])),
    ("inference-without-confidence", _del(C + [1, "confidence"])),
    ("inference-numeric-confidence", _set(C + [1, "confidence"], 0.8)),
    ("inference-without-rationale", _del(C + [1, "rationale"])),
    ("inference-without-uncertainty", _set(C + [1, "uncertainty_ids"], [])),
    ("unknown-without-missing-data", _del(C + [2, "missing_data"])),
    ("unknown-with-confidence", _set(C + [2, "confidence"], "high")),
    ("bad-claim-type", _set(C + [0, "claim_type"], "opinion")),
    ("bad-claim-id", _set(C + [0, "claim_id"], "claim1")),
    ("scored-factor-without-evidence", _del(F0 + ["evidence_source_ids"])),
    ("insufficient-factor-with-points", _set(F2 + ["points"], 5)),
    ("negative-points", _set(F0 + ["points"], -1)),
    ("bad-score-model-id", _set(["scores", 0, "score_model_id"], "opportunity")),
    ("relationship-without-uncertainty", _set(REL + ["uncertainty_ids"], [])),
    ("relationship-without-evidence", _set(REL + ["evidence_source_ids"], [])),
    ("relationship-bad-type", _set(REL + ["relationship_type"], "friend")),
    ("recommendation-without-claims", _set(REC + ["based_on_claim_ids"], [])),
    ("recommendation-without-evidence", _del(REC + ["evidence_source_ids"])),
    ("recommendation-bad-product-id", _set(REC + ["product_ids"], ["Police Box"])),
    ("approved-without-reviewer", _set(["review_status"], "approved")),
    ("bad-analysis-id", _set(["analysis_id"], "analysis-1")),
    ("bare-input-hash", _set(["input_hash"], "a" * 64)),
    ("wrong-schema-version", _set(["schema_version"], "1.0.0-draft.1")),
    ("unknown-top-level-field", _set(["confidence_score"], 0.93)),
    ("missing-uncertainties", _del(["uncertainties"])),
]


@pytest.mark.parametrize("case_id,mutation", SCHEMA_NEGATIVE, ids=[c[0] for c in SCHEMA_NEGATIVE])
def test_schema_rejects(case_id, mutation):
    r = base()
    assert schema_errors(r) == []
    mutation(r)
    assert schema_errors(r), f"{case_id} was not rejected"


def test_approved_with_reviewer_is_valid():
    r = base()
    r.update(review_status="approved", reviewed_by="Eric", reviewed_at="2026-11-04T01:00:00Z")
    assert schema_errors(r) == []


# ------------------------------------------------------------------ negative: rules
def _rules(errors):
    return {e.split()[0] for e in errors}


def test_duplicate_claim_id_detected():
    r = base()
    claim(r, "cl-003")["claim_id"] = "cl-001"
    for f in r["scores"][1]["factors"]:
        f.pop("claim_ids", None)
    assert "AR3" in _rules(ac.check_analysis(r, PKG))


def test_dangling_uncertainty_detected():
    r = base()
    claim(r, "cl-002")["uncertainty_ids"] = ["un-999"]
    assert _rules(ac.check_analysis(r, PKG)) == {"AR4"}


def test_recommendation_on_unknown_only_detected():
    r = base()
    r["recommendations"][0]["based_on_claim_ids"] = ["cl-003"]
    assert _rules(ac.check_analysis(r, PKG)) == {"AR4"}


def test_top_level_evidence_must_be_union():
    r = base()
    r["evidence_source_ids"] = [SA]
    assert _rules(ac.check_analysis(r, PKG)) == {"AR5"}


def test_score_total_mismatch_detected():
    r = base()
    r["scores"][0]["total_points"] = 55
    assert _rules(ac.check_analysis(r, PKG)) == {"AR6"}


def test_points_above_max_detected():
    r = base()
    f = r["scores"][0]["factors"][1]
    f["points"] = 15
    r["scores"][0]["total_points"] = 45
    assert _rules(ac.check_analysis(r, PKG)) == {"AR6"}


def test_rank_order_detected():
    r = base()
    r["scores"][0]["rank"], r["scores"][1]["rank"] = 2, 1
    assert _rules(ac.check_analysis(r, PKG)) == {"AR6"}


def test_inconsistent_factor_set_detected():
    r = base()
    r["scores"][1]["factors"].pop()
    r["scores"][1]["max_total_points"] = 50
    assert _rules(ac.check_analysis(r, PKG)) == {"AR6"}


def test_input_hash_mismatch_detected():
    r = base()
    r["input_hash"] = "sha256:" + "0" * 64
    assert _rules(ac.check_analysis(r, PKG)) == {"AR7"}


def test_evidence_outside_package_detected():
    r = base()
    ghost = "src_01JCS000000000000000000099"
    claim(r, "cl-001")["evidence_source_ids"] = [ghost]
    r["evidence_source_ids"] = [SA, SB, ghost]
    assert _rules(ac.check_analysis(r, PKG)) == {"AR8"}


def test_unknown_company_subject_detected():
    r = base()
    r["recommendations"][0]["subjects"] = [{"entity_type": "company", "entity_id": "co_01JCC000000000000000000099"}]
    assert _rules(ac.check_analysis(r, PKG)) == {"AR8"}


def test_collected_label_on_synthetic_input_detected():
    r = base()
    r["data_origin"] = "collected"
    assert _rules(ac.check_analysis(r, PKG)) == {"AR9"}
