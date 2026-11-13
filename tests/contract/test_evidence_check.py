"""A2-11: evidence rules EV1-EV7 (skills/exhibitiq/scripts/evidence_check.py)."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import evidence_check as ev  # noqa: E402

PKG = ROOT / "schemas" / "v1" / "examples" / "package"
BASE = json.loads((ROOT / "schemas/v1/examples/analysis/analysis_result.example.json").read_text(encoding="utf-8"))
G = ROOT / "data" / "golden" / "v1"


def claim(a, t):
    return next(c for c in a["conclusions"] if c["claim_type"] == t)


def test_examples_pass():
    assert ev.validate(BASE, PKG) == []
    assert ev.validate(json.loads((G / "expected/analysis/analysis_result.json").read_text(encoding="utf-8")), G / "package") == []


def _fact_too_strong(a): claim(a, "fact")["verification_status"] = "verified"
def _fact_conf(a): claim(a, "fact")["confidence"] = "high"
def _inf_vs(a): claim(a, "inference")["verification_status"] = "verified"
def _unk_conf(a): claim(a, "unknown")["confidence"] = "low"
def _scored_on_unknown(a):
    f = a["scores"][0]["factors"][0]; f["claim_ids"] = [claim(a, "unknown")["claim_id"]]
def _unscored_points(a):
    f = next(f for s in a["scores"] for f in s["factors"] if f["status"] == "insufficient_data"); f["points"] = 5
def _rel_no_conf(a): a["relationships"][0].pop("confidence")
def _rec_no_unc(a): a["recommendations"][0].pop("uncertainty_ids")


@pytest.mark.parametrize("mutate,rule", [
    (_fact_too_strong, "EV1"), (_fact_conf, "EV1"), (_inf_vs, "EV2"), (_unk_conf, "EV3"),
    (_scored_on_unknown, "EV4"), (_unscored_points, "EV4"), (_rel_no_conf, "EV5"), (_rec_no_unc, "EV6"),
])
def test_each_rule_rejects(mutate, rule):
    a = copy.deepcopy(BASE)
    mutate(a)
    errs = ev.validate(a, PKG)
    assert any(e.startswith(rule) or e.startswith("AR1") for e in errs), errs
    assert errs, "must not be publishable"


@pytest.mark.parametrize("text", ["建議投入 NT$300,000 參展", "預算約 50 萬元", "Budget of USD 10k"])
def test_ev8_no_money_in_recommendations(text):
    a = copy.deepcopy(BASE)
    a["recommendations"][0]["statement"] = text
    assert any(e.startswith("EV8") for e in ev.validate(a, PKG))


def test_ev8_participation_decision_needs_basis():
    a = copy.deepcopy(BASE)
    r = a["recommendations"][0]
    r["recommendation_type"] = "participation_decision"
    r["based_on_claim_ids"], r["score_ids"] = [], []
    assert any(e.startswith("EV8") or e.startswith("AR") for e in ev.validate(a, PKG))
