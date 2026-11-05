"""Profile-driven analysis helpers (A2-16). Deterministic; no AI. Keyword hits are candidates, never facts.

Every function takes an analysis profile (knowledge/analysis-profiles/<id>.json, analysis_profile.schema.json),
so changing topics or keywords never needs a code change.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "contract"))
import profile_check  # noqa: E402

PROFILES = ROOT / "knowledge" / "analysis-profiles"
REL_TYPES = ("potential_customer", "competitor", "partner", "channel")
# keyword categories that signal a relationship by themselves (multi-label; candidates only)
CATEGORY_SIGNALS = {"competitor": "competitor"}


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def load_profile(profile: str | Path | dict | None = None) -> dict:
    if isinstance(profile, dict):
        return profile
    p = Path(profile) if profile and Path(profile).suffix == ".json" else PROFILES / f"{profile or 'default-library'}.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    errors = profile_check.check_profile(doc)
    if errors:
        raise LookupError(f"invalid profile {p.name}: {errors}")
    return doc


def _hit(word: str, text: str) -> bool:
    # whole-word for Latin text (plural s/es allowed), substring for CJK
    if re.search(r"[A-Za-z0-9]", word):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(word)}(?:e?s)?(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return word in text


def _texts(package_dir: Path) -> dict[str, list[tuple[str, list[str]]]]:
    out: dict[str, list[tuple[str, list[str]]]] = {}
    for p in _jsonl(Path(package_dir) / "participations.jsonl"):
        text = " ".join([p["exhibitor_name_as_listed"], *p.get("categories_as_listed", []), *p.get("products_as_listed", [])])
        out.setdefault(p["company_id"], []).append((text, p["source_ids"]))
    return out


def match(package_dir: Path, profile=None) -> dict:
    """Enabled keywords (label, English label, synonyms) found in each company's source text."""
    prof = load_profile(profile)
    kws = [k for k in prof["keywords"] if k["enabled"]]
    out = {}
    for cid, rows in sorted(_texts(package_dir).items()):
        terms, cats, sids = set(), {}, set()
        for text, s in rows:
            for k in kws:
                if any(_hit(w, text) for w in [k["label"], k.get("label_en", ""), *k.get("synonyms", [])] if w):
                    terms.add(k["term_id"]); cats[k["term_id"]] = k["category"]; sids |= set(s)
        out[cid] = {"terms": sorted(terms), "categories": {t: cats[t] for t in sorted(terms)}, "source_ids": sorted(sids)}
    return out


def bxr_status(prof: dict, knowledge_dir: Path | None = None) -> str:
    if prof["mode"] != "bxr_opportunity" or not prof.get("targets", {}).get("bxr_product_ids"):
        return "not_used"
    kd = knowledge_dir or ROOT / "knowledge"
    st = {json.loads((kd / "bxr-products" / f"{i}.json").read_text(encoding="utf-8"))["approval_status"] for i in prof["targets"]["bxr_product_ids"]}
    return "approved" if st == {"approved"} else "draft" if "approved" not in st else "mixed"


def relate(package_dir: Path, profile=None, knowledge_dir: Path | None = None) -> dict:
    """Multi-label relationship candidates. A company may get several types; none -> one "unknown" entry.

    Signals: profile.relationship_signals words; keywords in category "competitor"; in mode A, keywords in
    category "product" (BXR product positioning) make a company a competitor candidate (similar offering)
    and keywords in categories application/industry/need/problem matching the product's use make it a
    potential-customer candidate. Every candidate carries signals, sources and sufficiency="signal_only".
    """
    prof = load_profile(profile)
    m = match(package_dir, prof)
    texts = _texts(package_dir)
    mode_a = prof["mode"] == "bxr_opportunity"
    out = {}
    for cid in sorted(texts):
        found: dict[str, dict] = {}

        def add(rel, signal, sids):
            f = found.setdefault(rel, {"signals": set(), "source_ids": set()})
            f["signals"].add(signal); f["source_ids"] |= set(sids)

        for rel, words in prof.get("relationship_signals", {}).items():
            for text, sids in texts[cid]:
                for w in words:
                    if _hit(w, text):
                        add(rel, w, sids)
        for term, cat in m[cid]["categories"].items():
            if cat == "competitor" or (mode_a and cat == "product"):
                add("competitor", term, m[cid]["source_ids"])
            elif mode_a and cat in {"application", "industry", "need", "problem"}:
                add("potential_customer", term, m[cid]["source_ids"])
        if found:
            out[cid] = [{"relationship_type": r, "confidence": "low", "sufficiency": "signal_only",
                         "signals": sorted(found[r]["signals"]), "source_ids": sorted(found[r]["source_ids"]),
                         "rationale": "關鍵字命中，只是候選訊號，需閱讀來源確認：" + "、".join(sorted(found[r]["signals"]))}
                        for r in REL_TYPES if r in found]
        else:
            out[cid] = [{"relationship_type": "unknown", "confidence": None, "sufficiency": "none", "signals": [], "source_ids": [],
                         "rationale": "來源中沒有符合此分析設定的關係訊號，待判斷。"}]
    return {"profile_id": prof["profile_id"], "profile_version": prof["version"], "mode": prof["mode"],
            "bxr_products_status": bxr_status(prof, knowledge_dir), "companies": out}


def score(package_dir: Path, profile=None) -> list[dict]:
    """Scores only when the profile sets a score model; weights come from the profile. No evidence -> 0 points."""
    prof = load_profile(profile)
    sm = prof.get("score_model")
    if not sm:
        return []
    model = json.loads((ROOT / "knowledge" / "scoring" / f"{sm['score_model_id']}.json").read_text(encoding="utf-8"))
    m = match(package_dir, prof)
    parts = _jsonl(Path(package_dir) / "participations.jsonl")
    scores = []
    for cid in sorted({p["company_id"] for p in parts}):
        listed = [p for p in parts if p["company_id"] == cid and p["listing_status"] == "listed"]
        cats = m.get(cid, {}).get("categories", {})
        sids = m.get(cid, {}).get("source_ids", [])
        factors = []
        for f in model["factors"]:
            fid, mx = f["factor_id"], sm["weights"].get(f["factor_id"], f.get("default_max_points", f.get("max_points", 0)))
            hits = sorted(cats) if fid == "keyword_fit" else sorted(t for t, c in cats.items() if c == "product") if fid == "product_fit" and prof["mode"] == "bxr_opportunity" else []
            if fid in {"keyword_fit", "product_fit"} and hits:
                factors.append({"factor_id": fid, "label": f["label"], "status": "scored", "points": min(mx, 10 * len(hits)), "max_points": mx,
                                "evidence_source_ids": sids, "rationale": "命中關鍵字：" + "、".join(hits)})
            elif fid == "presence" and listed:
                factors.append({"factor_id": fid, "label": f["label"], "status": "scored", "points": mx, "max_points": mx,
                                "evidence_source_ids": sorted({s for p in listed for s in p["source_ids"]}), "rationale": "目前列於參展名單。"})
            else:
                factors.append({"factor_id": fid, "label": f["label"], "status": "insufficient_data", "points": 0, "max_points": mx,
                                "rationale": "沒有足夠證據，不計分。"})
        scores.append({"subject": {"entity_type": "company", "entity_id": cid}, "score_model_id": model["score_model_id"], "factors": factors,
                       "total_points": sum(x["points"] for x in factors), "max_total_points": sum(x["max_points"] for x in factors)})
    scores.sort(key=lambda s: (-s["total_points"], s["subject"]["entity_id"]))
    for i, s in enumerate(scores, 1):
        s["rank"], s["score_id"] = i, f"sc-{i:03d}"
    return scores


def analysis_config(profile=None, knowledge_dir: Path | None = None) -> dict:
    """The analysis_config block (AR11) to put into an analysis result produced with this profile."""
    prof = load_profile(profile)
    cfg = {"profile_id": prof["profile_id"], "profile_version": prof["version"], "profile_hash": profile_check.profile_hash(prof),
           "mode": prof["mode"], "keywords_snapshot": [k for k in prof["keywords"] if k["enabled"]]}
    if prof.get("score_model"):
        cfg["score_model_id"] = prof["score_model"]["score_model_id"]
    cfg["bxr_products_status"] = bxr_status(prof, knowledge_dir)
    return cfg


def compare(package_dirs: list[Path], profile=None) -> dict:
    """A2-09: deterministic cross-package comparison and keyword trends for one profile.

    Per package: identity (exhibition, edition/year, dataset), completeness, collected companies, and for every
    enabled keyword the companies whose source text matches it (with source ids). Across packages: companies that
    appear in several packages and per-keyword series ordered by year. Shares are only given when the package is
    complete; otherwise they are null with the reason (never estimated). Changes (changes.jsonl) are counted as given.
    """
    prof = load_profile(profile)
    kws = [k for k in prof["keywords"] if k["enabled"]]
    packages = []
    for d in package_dirs:
        d = Path(d)
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        hits = match(d, prof)
        companies = sorted(hits)
        complete = m["completeness_status"] == "complete"
        per_kw = {}
        for k in kws:
            cos = [c for c in companies if k["term_id"] in hits[c]["terms"]]
            per_kw[k["term_id"]] = {
                "label": k["label"], "category": k["category"], "company_ids": cos, "count": len(cos),
                "share": round(len(cos) / len(companies), 4) if complete and companies else None,
                "source_ids": sorted({s for c in cos for s in hits[c]["source_ids"]}),
            }
        changes = _jsonl(d / "changes.jsonl")
        packages.append({
            "dataset_id": m["dataset_id"], "exhibition_id": m["exhibition_id"], "edition_id": m["edition_id"],
            "year": m.get("edition_year"), "data_origin": m["data_origin"], "completeness_status": m["completeness_status"],
            "official_exhibitor_count": m["completeness"]["official_exhibitor_count"],
            "collected_company_count": len(companies), "company_ids": companies, "keywords": per_kw,
            "share_note": None if complete else "資料不完整，不計算比例（只列實際取得的家數）",
            "changes": {t: sum(1 for c in changes if c["change_type"] == t and c["entity_type"] in {"company", "participation"})
                        for t in ("added", "removed", "modified")} if changes else None,
        })
    order = sorted(packages, key=lambda p: ((p["year"] or 0), p["exhibition_id"]))
    seen: dict[str, list[str]] = {}
    for p in order:
        for c in p["company_ids"]:
            seen.setdefault(c, []).append(p["dataset_id"])
    series = {k["term_id"]: [{"dataset_id": p["dataset_id"], "exhibition_id": p["exhibition_id"], "year": p["year"],
                              "count": p["keywords"][k["term_id"]]["count"], "share": p["keywords"][k["term_id"]]["share"],
                              "completeness_status": p["completeness_status"]} for p in order] for k in kws}
    years = {(p["exhibition_id"], p["year"]) for p in order}
    return {
        "profile_id": prof["profile_id"], "profile_version": prof["version"], "mode": prof["mode"],
        "packages": order, "keyword_series": series,
        "shared_companies": {c: ds for c, ds in sorted(seen.items()) if len(ds) > 1},
        "trend_note": None if len({e for e, _ in years}) < len(years) else "沒有同一展覽的多個年度，只能做跨展覽比較，不能判斷時間趨勢（資料不足）",
        "incomplete_packages": [p["dataset_id"] for p in order if p["completeness_status"] != "complete"],
    }


def exhibition_value(package_dir: Path, profile=None, top: int = 10) -> dict:
    """A2-10: deterministic inputs for the exhibition's business value and visit suggestions (Eric 2026-11-05: business
    value only — no budget or money). Everything here is a signal for the Skill; the recommendation it writes is inference.
    """
    prof = load_profile(profile)
    d = Path(package_dir)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    rel = relate(d, prof)
    scores = score(d, prof)
    hits = match(d, prof)
    by_type: dict[str, list[str]] = {t: [] for t in REL_TYPES}
    for cid, items in rel["companies"].items():
        for x in items:
            if x["relationship_type"] in by_type:
                by_type[x["relationship_type"]].append(cid)
    matched = sorted(c for c, v in hits.items() if v["terms"])
    complete = m["completeness_status"] == "complete"
    return {
        "dataset_id": m["dataset_id"], "exhibition_id": m["exhibition_id"], "edition_id": m["edition_id"],
        "profile_id": prof["profile_id"], "profile_version": prof["version"], "mode": prof["mode"],
        "completeness_status": m["completeness_status"], "official_exhibitor_count": m["completeness"]["official_exhibitor_count"],
        "collected_company_count": len(hits),
        "topic_matched_companies": {"count": len(matched), "share": round(len(matched) / len(hits), 4) if complete and hits else None, "company_ids": matched},
        "relationship_candidates": {t: {"count": len(v), "company_ids": sorted(v)} for t, v in by_type.items()},
        "visit_candidates": [{"rank": s["rank"], "company_id": s["subject"]["entity_id"], "score_id": s["score_id"],
                              "total_points": s["total_points"], "max_total_points": s["max_total_points"]}
                             for s in scores if s["total_points"] > 0][:top],
        "bxr_products_status": rel["bxr_products_status"],
        "notes": [n for n in [
            None if complete else "資料不完整：家數只代表實際取得的部分，不計算比例；建議中必須列出不確定性",
            None if scores else "這個主題沒有設定評分模型：拜訪建議只能依關係候選與結論，不能依排名",
            "不評估預算或金額（Eric 2026-11-05）",
        ] if n],
    }
