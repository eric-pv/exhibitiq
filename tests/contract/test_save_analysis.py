"""A2-14: versioned, validated, immutable save of analysis results."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import exhibitiq_tools as tools  # noqa: E402

PKG = ROOT / "schemas" / "v1" / "examples" / "package"
EX = ROOT / "schemas" / "v1" / "examples" / "analysis" / "analysis_result.example.json"


def _write(tmp, a, name="a.json"):
    p = tmp / name
    p.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    return p


def test_save_creates_versioned_path_then_is_idempotent(tmp_path):
    out = tmp_path / "out"
    r = tools.save_analysis(EX, PKG, out)
    a = json.loads(EX.read_text(encoding="utf-8"))
    assert r["ok"] and r["action"] == "created"
    assert Path(r["path"]) == out / a["input_dataset_id"] / f"{a['analysis_id']}.json"
    assert tools.save_analysis(EX, PKG, out)["action"] == "unchanged"


def test_saved_analysis_is_immutable_except_review(tmp_path):
    out = tmp_path / "out"
    tools.save_analysis(EX, PKG, out)
    a = json.loads(EX.read_text(encoding="utf-8"))
    changed = copy.deepcopy(a); changed["title"] = "changed"
    r = tools.save_analysis(_write(tmp_path, changed), PKG, out)
    assert not r["ok"] and "immutable" in r["errors"][0]
    reviewed = copy.deepcopy(a)
    reviewed.update(review_status="human_reviewed", reviewed_by="Eric", reviewed_at="2026-11-05T00:00:00Z")
    r = tools.save_analysis(_write(tmp_path, reviewed), PKG, out)
    assert r["ok"] and r["action"] == "review_updated", r


def test_invalid_or_non_draft_analysis_is_not_saved(tmp_path):
    out = tmp_path / "out"
    a = json.loads(EX.read_text(encoding="utf-8"))
    bad = copy.deepcopy(a); bad["scores"][0]["factors"][0]["evidence_source_ids"] = []
    r = tools.save_analysis(_write(tmp_path, bad), PKG, out)
    assert not r["ok"] and r["action"] == "rejected" and not out.exists()
    nd = copy.deepcopy(a); nd.update(review_status="human_reviewed", reviewed_by="Eric", reviewed_at="2026-11-05T00:00:00Z")
    r = tools.save_analysis(_write(tmp_path, nd), PKG, out)
    assert not r["ok"] and "draft" in r["errors"][0]


def test_cli_exit_codes(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "ANALYSIS_ROOT", tmp_path / "out")
    assert tools.main(["save-analysis", str(EX), str(PKG)]) == 0
