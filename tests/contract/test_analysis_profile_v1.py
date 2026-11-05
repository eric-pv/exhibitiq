"""A2-15: analysis profile contract, analysis_config (AR11) and draft.5 -> draft.6 compatibility."""
import copy
import json
from pathlib import Path

import pytest

import analysis_check as ac
import package_check as pc
import profile_check as pf

EX = pc.ROOT / "schemas" / "v1" / "examples"
PA = json.loads((EX / "profile" / "analysis_profile.example.json").read_text(encoding="utf-8"))
PB = json.loads((EX / "profile" / "analysis_profile.industry.example.json").read_text(encoding="utf-8"))
WITH = json.loads((EX / "analysis" / "analysis_result.with_config.example.json").read_text(encoding="utf-8"))
OLD = json.loads((EX / "analysis" / "analysis_result.example.json").read_text(encoding="utf-8"))
PROFILES = {PA["profile_id"]: PA, PB["profile_id"]: PB}


def test_versions():
    assert pc.VERSION == "1.0.0-draft.7" and pc.ACCEPTED == {"1.0.0-draft.5", "1.0.0-draft.6", "1.0.0-draft.7"}


@pytest.mark.parametrize("p", sorted((pc.ROOT / "knowledge" / "analysis-profiles").glob("*.json")), ids=lambda p: p.name)
def test_stored_profiles_valid(p):
    assert pf.check_profile(json.loads(p.read_text(encoding="utf-8")), p.name) == []


def test_example_profiles_valid_and_mode_b_has_no_bxr_or_score():
    assert pf.check_profile(PA) == [] and pf.check_profile(PB) == []
    assert PB["mode"] == "industry_research" and "score_model" not in PB and not PB.get("targets", {}).get("bxr_product_ids")


def test_old_draft5_data_still_valid():
    assert OLD["schema_version"] == "1.0.0-draft.5" and "analysis_config" not in OLD
    assert ac.check_analysis(OLD, EX / "package") == []
    assert pc.check_package(EX / "package") == [] if hasattr(pc, "check_package") else True


def test_draft6_analysis_with_config_valid():
    assert pf.check_analysis_config(WITH, PROFILES) == []
    assert ac.check_analysis(WITH, EX / "package") == []


def test_hash_is_canonical_and_order_independent():
    shuffled = json.loads(json.dumps(PA), object_pairs_hook=lambda kv: dict(reversed(kv)))
    assert pf.profile_hash(shuffled) == pf.profile_hash(PA)
    changed = copy.deepcopy(PA); changed["keywords"][0]["label"] = "改"
    assert pf.profile_hash(changed) != pf.profile_hash(PA)


def _cfg(mut):
    r = copy.deepcopy(WITH); mut(r); return pf.check_analysis_config(r, PROFILES)


@pytest.mark.parametrize("name,mut", [
    ("hash-mismatch", lambda r: r["analysis_config"].update(profile_hash="sha256:" + "0" * 64)),
    ("disabled-in-snapshot", lambda r: r["analysis_config"]["keywords_snapshot"].append(dict(PA["keywords"][2]))),
    ("snapshot-differs", lambda r: r["analysis_config"]["keywords_snapshot"].pop()),
    ("scores-without-model", lambda r: r["analysis_config"].pop("score_model_id")),
    ("mode-b-uses-bxr", lambda r: r["analysis_config"].update(mode="industry_research", bxr_products_status="draft")),
    ("mode-a-no-bxr-status", lambda r: r["analysis_config"].pop("bxr_products_status")),
])
def test_ar11_rejects(name, mut):
    assert any(e.startswith("AR11") for e in _cfg(mut)), name


@pytest.mark.parametrize("name,mut,rule", [
    ("dup-term", lambda d: d["keywords"].append(dict(d["keywords"][0])), "PF3"),
    ("bad-focus", lambda d: d.setdefault("targets", {}).update(focus_term_ids=["nope"]), "PF4"),
    ("b-with-bxr", lambda d: d.setdefault("targets", {}).update(bxr_product_ids=["bxr-x"]), "PF5"),
    ("bad-mode", lambda d: d.update(mode="military_only"), "PF1"),
    ("float-weight", lambda d: d.update(score_model={"score_model_id": "x", "weights": {"a": 1.5}}), "PF1"),
])
def test_profile_rules_reject(name, mut, rule):
    d = copy.deepcopy(PB); mut(d)
    assert any(e.startswith(rule) for e in pf.check_profile(d)), name


def test_any_domain_and_category_allowed():
    d = copy.deepcopy(PB)
    d["keywords"].append({"term_id": "custom.anything", "category": "my-own-category", "label": "任何領域", "enabled": True})
    assert pf.check_profile(d) == []
