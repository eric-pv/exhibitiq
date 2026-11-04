"""A2-08: relationship candidates (skills/exhibitiq/scripts/exhibitiq_tools.py relate)."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import exhibitiq_tools as tools  # noqa: E402

G = ROOT / "data" / "samples" / "golden" / "v1" / "package"


def _pkg(tmp, rows):
    p = tmp / "pkg"; p.mkdir()
    (p / "participations.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def _row(cid, name, cats):
    return {"company_id": cid, "exhibitor_name_as_listed": name, "categories_as_listed": cats, "source_ids": [f"src_{cid}"]}


def test_without_approved_products_no_customer_or_competitor_is_claimed():
    r = tools.relate(G)
    assert r["approved_products"] == 0
    for c in r["companies"].values():
        assert c["relationship_type"] in {"unknown", "channel", "partner"}
        if c["relationship_type"] == "unknown":
            assert c["reason"] and not c["source_ids"]


def test_signals_need_approved_products_and_carry_sources(tmp_path):
    kd = tmp_path / "k"
    shutil.copytree(ROOT / "knowledge", kd)
    pkg = _pkg(tmp_path, [
        _row("co_A", "Alpha Immersive", ["Immersive"]),         # same capability as the product -> competitor
        _row("co_B", "Bravo Defence", ["Defence"]),             # target industry -> potential customer
        _row("co_C", "Charlie Distribution", ["Distributor"]),  # channel keyword
        _row("co_D", "Delta", []),                               # nothing -> unknown
    ])
    draft = {"product_id": "bxr-test", "approval_status": "draft", "capabilities": ["capability.immersive-simulation"], "target_industries": ["industry.defense"]}
    (kd / "bxr-products" / "bxr-test.json").write_text(json.dumps(draft), encoding="utf-8")
    assert {c["relationship_type"] for c in tools.relate(pkg, kd)["companies"].values()} <= {"unknown", "channel", "partner"}  # draft cards are ignored
    (kd / "bxr-products" / "bxr-test.json").write_text(json.dumps({**draft, "approval_status": "approved"}), encoding="utf-8")
    r = tools.relate(pkg, kd)["companies"]
    assert r["co_A"]["relationship_type"] == "competitor"
    assert r["co_C"]["relationship_type"] == "channel" and r["co_C"]["source_ids"] == ["src_co_C"]
    assert r["co_D"]["relationship_type"] == "unknown" and r["co_D"]["confidence"] is None
    for c in r.values():
        if c["relationship_type"] != "unknown":
            assert c["confidence"] == "low" and c["source_ids"] and c["signals"]
    assert r["co_B"]["relationship_type"] == "potential_customer"
