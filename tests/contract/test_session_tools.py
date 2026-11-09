"""Analysis on the owner's Claude subscription (session_tools.prepare / finalize): AI only writes the judgement."""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "exhibitiq" / "scripts"))
import profile_tools as pt  # noqa: E402
import session_tools as st  # noqa: E402

G = ROOT / "data" / "samples" / "golden" / "v1"
TOOLS = ROOT / "skills" / "exhibitiq" / "scripts" / "exhibitiq_tools.py"
NOW = datetime(2026, 11, 9, 3, 0, 0, tzinfo=timezone.utc)


def test_ulid_ids_match_the_contract_and_differ():
    ids = {st.new_analysis_id() for _ in range(50)}
    assert len(ids) == 50 and all(re.fullmatch(r"ana_[0-7][0-9A-HJKMNP-TV-Z]{25}", i) for i in ids)


def test_prepare_fills_every_deterministic_field_and_a_compact_brief(tmp_path):
    r = st.prepare("golden-fair", None, "bxr-opportunity", top=2, index_path=G / "dataset_index.json", out_dir=tmp_path, now=NOW)
    brief = json.loads(Path(r["brief"]).read_text(encoding="utf-8"))
    draft = json.loads(Path(r["draft"]).read_text(encoding="utf-8"))
    m = json.loads((G / "package" / "manifest.json").read_text(encoding="utf-8"))
    assert draft["input_dataset_id"] == m["dataset_id"] and draft["input_hash"] == m["content_hash"] and draft["data_origin"] == "synthetic"
    assert draft["review_status"] == "draft" and draft["generated_at"] == "2026-11-09T03:00:00Z"
    assert draft["analysis_config"] == pt.analysis_config("bxr-opportunity")
    assert draft.get("scores", []) == pt.score(G / "package", "bxr-opportunity")  # deterministic, never re-written by AI
    assert len(brief["companies_in_detail"]) == 2 and len(brief["other_companies"]) == r["companies"] - 2
    cited = {s for c in brief["companies_in_detail"] for p in c["listed_as"] for s in p["source_ids"]}
    assert cited <= set(brief["sources"])  # every source the brief shows is described
    assert r["estimate"]["brief_tokens"] > 0 and r["estimate"]["skill_instructions_tokens"] > 1000


def test_industry_profile_without_score_model_has_no_scores(tmp_path):
    fire = ROOT / "schemas/v1/examples/profile/analysis_profile.industry.example.json"
    r = st.prepare("golden-fair", None, str(fire), index_path=G / "dataset_index.json", out_dir=tmp_path, now=NOW)
    draft = json.loads(Path(r["draft"]).read_text(encoding="utf-8"))
    assert "scores" not in draft and draft["analysis_type"] == "market_trend"


def test_an_unfilled_draft_cannot_be_published(tmp_path):
    r = st.prepare("golden-fair", None, "bxr-opportunity", index_path=G / "dataset_index.json", out_dir=tmp_path, now=NOW)
    f = st.finalize(Path(r["draft"]), G / "package", save=False, report_dir=tmp_path)
    assert f["ok"] is False and f["stage"] == "validate-analysis" and f["errors"]


def test_finalize_valid_analysis_renders_report_and_saves_only_when_asked(tmp_path):
    an = G / "expected/analysis/analysis_result.json"
    f = st.finalize(an, G / "package", save=False, report_dir=tmp_path)
    assert f["ok"] and f["quality_warnings"] == [] and "saved" not in f
    assert Path(f["report"]).read_text(encoding="utf-8").startswith("# ")


def test_cli_prepare_reports_missing_package_clearly():
    bad = subprocess.run([sys.executable, str(TOOLS), "prepare", "sample-fair"], capture_output=True, text=True)
    assert bad.returncode == 2 and "no validated package" in bad.stderr
