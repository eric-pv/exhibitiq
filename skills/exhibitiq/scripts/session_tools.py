"""Analysis in a Claude Code session on the owner's Claude subscription (Eric 2026-11-09: no API billing).

To spend as little of the subscription as possible, everything that needs no AI runs here first:
  prepare  -> select + validate the package, analysis_config, classify/relate/score/value, and a compact BRIEF
              (top-N companies with their source text, candidates and score breakdown; the rest as one line each)
              plus a DRAFT analysis_result with every deterministic field already filled (metadata, config,
              scores). Claude reads the brief and writes only conclusions, uncertainties, relationships,
              recommendations, summary.
  finalize -> validate-analysis (EV1-EV8) + quality (QC1-QC9) + save-analysis + Markdown report.
Outputs of prepare go to .work/ (not committed). Token figures are estimates (characters, not a tokenizer).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / ".work"
SKILL_FILES = [HERE.parent / "SKILL.md", *sorted((HERE.parent / "references").glob("*.md"))]
TYPE_BY_MODE = {"bxr_opportunity": "opportunity_ranking", "industry_research": "market_trend", "competitor_research": "competitive_landscape"}
B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def estimate_tokens(text: str) -> int:
    """Rough: one token per CJK character, ~3.5 characters per token otherwise. Real counts differ (±30%)."""
    cjk = len(re.findall(r"[　-鿿＀-￯]", text))
    return int(cjk + (len(text) - cjk) / 3.5)


def new_analysis_id(now_ms: int | None = None) -> str:
    """ana_ + ULID (48-bit time + 80 random bits, Crockford base32)."""
    n = ((now_ms if now_ms is not None else int(time.time() * 1000)) << 80) | secrets.randbits(80)
    return "ana_" + "".join(B32[(n >> (5 * i)) & 31] for i in reversed(range(26)))


def _skill_version() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        return f"exhibitiq-skill@{sha}"
    except Exception:
        return "exhibitiq-skill@unknown"


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def prepare(exhibition_id: str, year: int | None = None, profile: str | None = None, top: int = 40,
            index_path: Path | None = None, out_dir: Path | None = None, now: datetime | None = None) -> dict:
    import exhibitiq_tools as t
    import profile_tools as pt
    idx = index_path or t.default_index()
    sel = t.select_package(idx, exhibition_id, year)
    pkg = Path(sel["package_dir"])
    v = t.validate_package(pkg)
    if not v["ok"]:
        raise LookupError(f"package failed validation; do not analyse: {v['errors'][:5]}")
    prof = pt.load_profile(profile)
    cfg = pt.analysis_config(prof["profile_id"] if profile is None or not str(profile).endswith(".json") else profile)
    m = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    companies = {c["company_id"]: c for c in _jsonl(pkg / "companies.jsonl")}
    parts = _jsonl(pkg / "participations.jsonl")
    sources = {s["source_id"]: s for s in _jsonl(pkg / "sources.jsonl")}
    hits = pt.match(pkg, prof)
    rel = pt.relate(pkg, prof)["companies"]
    scores = pt.score(pkg, prof)
    value = pt.exhibition_value(pkg, prof)
    by_score = {s["subject"]["entity_id"]: s for s in scores}
    order = sorted(companies, key=lambda c: (-(by_score[c]["total_points"] if c in by_score else 0), -len(hits.get(c, {}).get("terms", [])), c))
    detail, rest = order[:top], order[top:]

    def card(cid):
        c = companies[cid]
        ps = [p for p in parts if p["company_id"] == cid]
        return {"company_id": cid, "name": c["name"], "country": c.get("country"), "website": c.get("website"),
                "verification_status": c["verification_status"],
                "listed_as": [{"name": p["exhibitor_name_as_listed"], "listing_status": p["listing_status"], "booth": p.get("booth"),
                               "categories": p.get("categories_as_listed", []), "products": p.get("products_as_listed", []),
                               "source_ids": p["source_ids"]} for p in ps],
                "keyword_hits": hits.get(cid, {}).get("terms", []),
                "relationship_candidates": [{k: x[k] for k in ("relationship_type", "signals", "source_ids")} for x in rel.get(cid, []) if x["relationship_type"] != "unknown"],
                "score": ({"score_id": by_score[cid]["score_id"], "rank": by_score[cid]["rank"], "total": by_score[cid]["total_points"],
                           "max": by_score[cid]["max_total_points"]} if cid in by_score else None)}

    used = sorted({s for cid in detail for p in parts if p["company_id"] == cid for s in p["source_ids"]} |
                  {s for cid in detail for s in companies[cid]["source_ids"]})
    brief = {
        "dataset": {"dataset_id": m["dataset_id"], "exhibition_id": m["exhibition_id"], "edition_id": m["edition_id"], "year": m.get("edition_year"),
                    "content_hash": sel["content_hash"], "data_origin": m["data_origin"], "completeness_status": m["completeness_status"],
                    "official_exhibitor_count": m["completeness"]["official_exhibitor_count"], "collected_companies": len(companies)},
        "profile": {"profile_id": prof["profile_id"], "version": prof["version"], "mode": prof["mode"],
                    "keywords": [k["label"] for k in prof["keywords"] if k["enabled"]]},
        "value_signals": {k: value[k] for k in ("topic_matched_companies", "relationship_candidates", "visit_candidates", "bxr_products_status", "notes")},
        "companies_in_detail": [card(c) for c in detail],
        "other_companies": [f"{c} | {companies[c]['name']} | hits={len(hits.get(c, {}).get('terms', []))}" for c in rest],
        "sources": {s: {k: sources[s].get(k) for k in ("source_type", "url", "title", "retrieved_at")} for s in used if s in sources},
        "rules": "Every claim cites source_ids from this brief. Keyword hits and relationship candidates are signals, not facts. "
                 "Scores in the draft are deterministic: keep them unchanged. No budget or money. Incomplete data -> uncertainties cited by every recommendation.",
    }
    now = now or datetime.now(timezone.utc)
    draft = {
        "schema_version": (ROOT / "schemas" / "v1" / "VERSION").read_text(encoding="utf-8").strip(),
        "analysis_id": new_analysis_id(int(now.timestamp() * 1000)),
        "analysis_type": TYPE_BY_MODE[prof["mode"]] if (prof["mode"] != "bxr_opportunity" or scores) else "company_intelligence",
        "title": "TODO", "summary": "TODO",
        "input_dataset_id": m["dataset_id"], "input_hash": sel["content_hash"], "data_origin": m["data_origin"],
        "skill_version": _skill_version(), "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "review_status": "draft",
        "evidence_source_ids": [], "conclusions": [], "uncertainties": [], "scores": scores, "relationships": [], "recommendations": [],
        "analysis_config": cfg,
    }
    if not scores:
        draft.pop("scores")
    out = Path(out_dir or WORK / m["dataset_id"] / prof["profile_id"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    skill_tokens = sum(estimate_tokens(p.read_text(encoding="utf-8")) for p in SKILL_FILES)
    brief_tokens = estimate_tokens(json.dumps(brief, ensure_ascii=False))
    return {
        "brief": str(out / "brief.json"), "draft": str(out / "draft.json"), "package_dir": str(pkg),
        "dataset_id": m["dataset_id"], "completeness_status": m["completeness_status"], "data_origin": m["data_origin"],
        "companies": len(companies), "companies_in_detail": len(detail), "scored": len(scores),
        "estimate": {"skill_instructions_tokens": skill_tokens, "brief_tokens": brief_tokens,
                     "expected_output_tokens": "約 5,000～20,000（含思考；依建議數量而定）",
                     "note": "以字元估算（±30%）；Claude Code 工作階段每一輪都會重讀對話內容，實際用量通常是讀入量的數倍。"},
        "next": f"Claude 讀 {out / 'brief.json'}，在 {out / 'draft.json'} 填入 title、summary、conclusions、uncertainties、relationships、recommendations、evidence_source_ids，"
                f"然後執行 finalize {out / 'draft.json'} {pkg}",
    }


def finalize(analysis_path: Path, package_dir: Path, save: bool = True, report_dir: Path | None = None) -> dict:
    import exhibitiq_tools as t
    import quality_check
    v = t.validate_analysis(analysis_path, package_dir)
    if not v["ok"]:
        return {"ok": False, "stage": "validate-analysis", "errors": v["errors"]}
    q = quality_check.quality_report(analysis_path, package_dir)
    result = {"ok": True, "stage": "done", "errors": [], "quality_warnings": q["warnings"]}
    if save:
        s = t.save_analysis(analysis_path, package_dir)
        if not s["ok"]:
            return {"ok": False, "stage": "save-analysis", "errors": s["errors"], "quality_warnings": q["warnings"]}
        result["saved"] = s["path"]
    a = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    rd = Path(report_dir or WORK / "reports")
    rd.mkdir(parents=True, exist_ok=True)
    (rd / f"{a['analysis_id']}.md").write_text(t.render_report(analysis_path, package_dir), encoding="utf-8")
    result["report"] = str(rd / f"{a['analysis_id']}.md")
    return result
