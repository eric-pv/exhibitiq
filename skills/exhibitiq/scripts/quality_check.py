"""A3-03: quality checks for opportunity, relationship, product-fit and strategy recommendations.

evidence_check.py (EV1-EV8) decides whether an analysis MAY be published (errors block it). This module looks
for weaknesses that still pass those rules: recommendations nobody can act on, priorities that the scores do
not support, over-confident inferences on incomplete data, duplicates. Findings are warnings (QC1-QC9): the
Skill fixes them or explains them in the analysis (uncertainties / rationale) before asking for review.
See references/evidence-rules.md "品質檢查（A3-03）". Deterministic; no AI here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RANK = {"high": 3, "medium": 2, "low": 1}


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", (s or "").casefold())


def check_quality(a: dict, manifest: dict | None = None) -> list[dict]:
    out: list[dict] = []
    warn = lambda rule, where, msg: out.append({"rule": rule, "id": where, "message": msg})
    complete = (manifest or {}).get("completeness_status") == "complete"
    claims = {c["claim_id"]: c for c in a.get("conclusions", [])}
    scores = {s["score_id"]: s for s in a.get("scores", [])}
    recs = a.get("recommendations", [])

    for r in recs:
        rid, typ = r["recommendation_id"], r["recommendation_type"]
        companies = [s for s in r.get("subjects", []) if s["entity_type"] == "company"]
        if typ in {"visit_priority", "partnership"} and not companies:  # QC1
            warn("QC1", rid, f"{typ} 建議沒有指定企業（subjects），無法執行")
        if typ == "exhibit_product" and not r.get("product_ids"):  # QC2
            warn("QC2", rid, "產品建議沒有指定產品（product_ids）")
        if typ == "visit_priority" and r["priority"] == "high" and scores and not r.get("score_ids"):  # QC3
            warn("QC3", rid, "高優先度拜訪建議沒有引用評分（score_ids），優先度缺乏依據")
        for sid in r.get("score_ids", []):  # QC4
            s = scores.get(sid)
            if s and r["priority"] == "high":
                insufficient = sum(f["status"] == "insufficient_data" for f in s["factors"])
                if insufficient * 2 > len(s["factors"]):
                    warn("QC4", rid, f"高優先度建議依據的評分 {sid} 有 {insufficient}／{len(s['factors'])} 個因子資料不足")
        based = [claims[c] for c in r.get("based_on_claim_ids", []) if c in claims]
        if based and all(c["claim_type"] == "unknown" for c in based):  # QC9
            warn("QC9", rid, "建議只依據「未知」結論，沒有事實或推論支持")

    # QC5: priority inversion among score-backed visit recommendations (higher priority but lower score)
    backed = []
    for r in recs:
        pts = [scores[s]["total_points"] / scores[s]["max_total_points"] for s in r.get("score_ids", []) if s in scores and scores[s]["max_total_points"]]
        if r["recommendation_type"] == "visit_priority" and pts:
            backed.append((r, max(pts)))
    for r1, p1 in backed:
        for r2, p2 in backed:
            if RANK[r1["priority"]] > RANK[r2["priority"]] and p1 < p2:
                warn("QC5", r1["recommendation_id"], f"優先度高於 {r2['recommendation_id']}，但引用的評分較低（{p1:.0%} < {p2:.0%}）；請說明理由或調整")

    seen: dict[str, str] = {}
    for r in recs:  # QC6
        k = _norm(r["statement"])
        if k in seen:
            warn("QC6", r["recommendation_id"], f"與 {seen[k]} 內容重複")
        seen.setdefault(k, r["recommendation_id"])

    if manifest is not None and not complete:  # QC7
        for c in a.get("conclusions", []):
            if c["claim_type"] == "inference" and c.get("confidence") == "high":
                warn("QC7", c["claim_id"], "輸入資料不完整，推論不應標示高信心")
    for rel in a.get("relationships", []):  # QC8
        if rel.get("confidence") == "high" and len(set(rel.get("evidence_source_ids", []))) < 2:
            warn("QC8", rel["relationship_id"], "只有一個來源的關係判斷不應標示高信心")
    return out


def quality_report(analysis_path: Path, package_dir: Path | None = None) -> dict:
    a = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    m = json.loads((Path(package_dir) / "manifest.json").read_text(encoding="utf-8")) if package_dir else None
    w = check_quality(a, m)
    by_rule: dict[str, int] = {}
    for x in w:
        by_rule[x["rule"]] = by_rule.get(x["rule"], 0) + 1
    return {"analysis_id": a["analysis_id"], "warnings": w, "by_rule": by_rule,
            "note": "品質警告不阻止發布（發布條件是 validate-analysis 的 EV1–EV8）；請修正，或在不確定性／理由中說明後再送審。"}
