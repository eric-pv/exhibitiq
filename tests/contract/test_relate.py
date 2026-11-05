"""A2-16 (supersedes the A2-08 single-label tests): profile-driven match / relate / score / analysis_config."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import profile_tools as pt  # noqa: E402
import profile_check as pf  # noqa: E402
import analysis_check as ac  # noqa: E402

G = ROOT / "data" / "samples" / "golden" / "v1"
FIRE = json.loads((ROOT / "schemas/v1/examples/profile/analysis_profile.industry.example.json").read_text(encoding="utf-8"))


def _pkg(tmp, rows):
    p = tmp / "pkg"; p.mkdir()
    (p / "participations.jsonl").write_text("\n".join(json.dumps(
        {"company_id": c, "exhibitor_name_as_listed": n, "categories_as_listed": cats, "listing_status": "listed", "source_ids": [f"src_{c}"]})
        for c, n, cats in rows) + "\n", encoding="utf-8")
    return p


def test_default_profile_reproduces_previous_classification():
    r = pt.match(G / "package")
    alpha = next(v for k, v in r.items() if k.endswith("1"))
    assert {"application.training", "technology.simulation"} <= set(alpha["terms"])


def test_multi_label_and_never_fact(tmp_path):
    pkg = _pkg(tmp_path, [("co_A", "Alpha Thermal Camera Distributor", ["Fire Rescue"]), ("co_B", "Bravo", [])])
    r = pt.relate(pkg, FIRE)
    a = {x["relationship_type"] for x in r["companies"]["co_A"]}
    assert {"competitor", "channel"} <= a  # one company, several relationships
    for x in r["companies"]["co_A"]:
        assert x["confidence"] == "low" and x["sufficiency"] == "signal_only" and x["source_ids"] and "候選" in x["rationale"]
    assert [x["relationship_type"] for x in r["companies"]["co_B"]] == ["unknown"]
    assert r["bxr_products_status"] == "not_used"  # mode B never touches BXR cards


def test_mode_b_runs_without_any_bxr_cards(tmp_path):
    kd = tmp_path / "k"; (kd / "bxr-products").mkdir(parents=True)
    pkg = _pkg(tmp_path, [("co_A", "Alpha", ["Firefighting", "Thermal Imaging"])])
    assert pt.match(pkg, FIRE)["co_A"]["terms"] == ["custom.firefighting", "custom.thermal-imaging"]
    assert pt.relate(pkg, FIRE, kd)["bxr_products_status"] == "not_used"
    assert pt.score(pkg, FIRE) == []  # no score model in the profile -> no scores


def test_keywords_change_without_code_change(tmp_path):
    pkg = _pkg(tmp_path, [("co_A", "Alpha Laser Optics", [])])
    prof = copy.deepcopy(FIRE)
    assert pt.match(pkg, prof)["co_A"]["terms"] == []
    prof["keywords"].append({"term_id": "custom.laser-optics", "category": "technology", "label": "雷射光學", "label_en": "Laser Optics", "enabled": True})
    assert pt.match(pkg, prof)["co_A"]["terms"] == ["custom.laser-optics"]
    prof["keywords"][-1]["enabled"] = False
    assert pt.match(pkg, prof)["co_A"]["terms"] == []


def test_mode_a_reports_product_card_status():
    r = pt.relate(G / "package", "bxr-opportunity")
    assert r["mode"] == "bxr_opportunity" and r["bxr_products_status"] == "approved"  # Eric approved the 8 cards 2026-11-05


def test_score_uses_profile_weights_and_has_no_booth_factor(tmp_path):
    prof = json.loads((ROOT / "knowledge/analysis-profiles/bxr-opportunity.json").read_text(encoding="utf-8"))
    prof["score_model"] = {"score_model_id": "opportunity@2", "weights": {"keyword_fit": 50, "presence": 5}}
    pkg = _pkg(tmp_path, [("co_A", "Alpha Drone Wargame", ["Counter Drone"]), ("co_B", "Bravo", [])])
    s = pt.score(pkg, prof)
    ids = {f["factor_id"] for f in s[0]["factors"]}
    assert "booth_known" not in ids and {"keyword_fit", "product_fit", "presence", "contact_signal"} == ids
    kf = next(f for f in s[0]["factors"] if f["factor_id"] == "keyword_fit")
    assert kf["max_points"] == 50 and kf["status"] == "scored" and kf["evidence_source_ids"]
    assert s[0]["subject"]["entity_id"] == "co_A" and s[0]["rank"] == 1
    for x in s:
        for f in x["factors"]:
            if f["status"] == "insufficient_data":
                assert f["points"] == 0


@pytest.mark.parametrize("profile_id", ["default-library", "bxr-opportunity"])
def test_analysis_config_passes_ar11(profile_id):
    cfg = pt.analysis_config(profile_id)
    prof = pt.load_profile(profile_id)
    assert cfg["profile_hash"] == pf.profile_hash(prof)
    result = {"analysis_config": cfg, "scores": [], "recommendations": []}
    assert pf.check_analysis_config(result) == []
