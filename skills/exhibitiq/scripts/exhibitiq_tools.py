"""ExhibitIQ Skill helper (A2-03). Deterministic I/O around the analysis; no AI here.

Usage (from the repo root):
  python skills/exhibitiq/scripts/exhibitiq_tools.py list   [--index PATH]
  python skills/exhibitiq/scripts/exhibitiq_tools.py select  EXHIBITION_ID [YEAR] [--index PATH]
  python skills/exhibitiq/scripts/exhibitiq_tools.py check-all [--index PATH]
  python skills/exhibitiq/scripts/exhibitiq_tools.py validate-package PACKAGE_DIR
  python skills/exhibitiq/scripts/exhibitiq_tools.py validate-analysis ANALYSIS_JSON PACKAGE_DIR
  python skills/exhibitiq/scripts/exhibitiq_tools.py save-analysis ANALYSIS_JSON PACKAGE_DIR
  python skills/exhibitiq/scripts/exhibitiq_tools.py report ANALYSIS_JSON PACKAGE_DIR > report.md

Package validation uses data engineering's `etl.validate` when it is importable
(after phase integration). Until then it falls back to the contract reference
checks in tests/contract and says so in its output. Analysis validation uses
evidence_check.py (A2-11): contract rules AR1-AR9 plus evidence rules EV1-EV7.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "contract"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REAL_INDEX = ROOT / "data" / "index" / "datasets.json"
EXAMPLE_INDEX = ROOT / "schemas" / "v1" / "examples" / "index" / "dataset_index.example.json"


def default_index() -> Path:
    return REAL_INDEX if REAL_INDEX.exists() else EXAMPLE_INDEX


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def list_exhibitions(index_path: Path) -> list[dict]:
    idx = load(index_path)
    return [{"exhibition_id": e["exhibition_id"], "name": e.get("name_zh_hant") or e["name"],
             "acquisition": e["acquisition"]["status"],
             "editions": [{"year": ed["year"], "latest_dataset_id": ed["latest_dataset_id"]} for ed in e["editions"]]}
            for e in idx["exhibitions"]]


def select_package(index_path: Path, exhibition_id: str, year: int | None = None) -> dict:
    """Latest validated package for an exhibition (and year). Raises with a clear reason otherwise."""
    idx = load(index_path)
    ex = next((e for e in idx["exhibitions"] if e["exhibition_id"] == exhibition_id), None)
    if ex is None:
        raise LookupError(f"{exhibition_id} is not in the dataset index (not registered/accepted)")
    eds = [ed for ed in ex["editions"] if year is None or ed["year"] == year]
    eds = [ed for ed in sorted(eds, key=lambda e: e["year"], reverse=True) if ed["latest_dataset_id"]]
    if not eds:
        why = ex["acquisition"].get("notes") or ex["acquisition"]["status"]
        raise LookupError(f"{exhibition_id}: no validated package available ({why})")
    ed = eds[0]
    ds = next(d for d in ed["datasets"] if d["dataset_id"] == ed["latest_dataset_id"])
    if ds["location"]["storage"] != "git":
        raise LookupError(f"{ds['dataset_id']}: storage {ds['location']['storage']} is not readable here")
    return {"dataset_id": ds["dataset_id"], "edition_id": ed["edition_id"], "package_dir": str(ROOT / ds["location"]["locator"]),
            "content_hash": ds["content_hash"], "data_origin": ds["data_origin"], "completeness_status": ds["completeness_status"]}


def validate_package(package_dir: Path) -> dict:
    try:
        from etl.validate import validate_package as production  # data engineering (D1-05)
    except ImportError:
        import package_check
        errors = package_check.check_package(Path(package_dir))
        return {"validator": "tests/contract/package_check (fallback: etl.validate not available on this branch)",
                "ok": not errors, "errors": errors}
    report = production(Path(package_dir))  # etl.validate.Report: .ok, .findings (str(finding) = "Rn ...: message")
    return {"validator": "etl.validate", "ok": report.ok, "errors": [str(f) for f in report.findings]}


def check_all(index_path: Path) -> list[dict]:
    """A2-04: batch-check every latest package in the index: availability, schema version, hash, validation."""
    accepted = set(load(ROOT / "schemas" / "v1" / "COMPATIBILITY.json")["accepted"])
    rows = []
    for e in load(index_path)["exhibitions"]:
        for ed in e["editions"]:
            row = {"edition_id": ed["edition_id"], "dataset_id": ed["latest_dataset_id"], "ok": False, "problems": []}
            if not ed["latest_dataset_id"]:
                la = ed.get("last_acquisition") or {}
                row["problems"].append(f"no validated package (last acquisition: {la.get('status', 'none')})")
                rows.append(row)
                continue
            try:
                sel = select_package(index_path, e["exhibition_id"], ed["year"])
            except LookupError as err:
                row["problems"].append(str(err)); rows.append(row); continue
            m = load(Path(sel["package_dir"]) / "manifest.json")
            if m.get("schema_version") not in accepted:
                row["problems"].append(f"schema_version {m.get('schema_version')} not in accepted {sorted(accepted)}")
            if m.get("content_hash") != sel["content_hash"]:
                row["problems"].append("content_hash differs from the dataset index")
            v = validate_package(Path(sel["package_dir"]))
            row["problems"] += v["errors"]
            row["validator"] = v["validator"]
            row["ok"] = not row["problems"]
            rows.append(row)
    return rows


def classify(package_dir: Path, profile=None) -> dict:
    """A2-06/A2-16: keyword candidates per company from an analysis profile (default: default-library)."""
    import profile_tools
    return {k: {"terms": v["terms"], "source_ids": v["source_ids"]} for k, v in profile_tools.match(package_dir, profile).items()}


def relate(package_dir: Path, profile=None, knowledge_dir: Path | None = None) -> dict:
    """A2-08/A2-16: multi-label relationship candidates from an analysis profile."""
    import profile_tools
    return profile_tools.relate(package_dir, profile, knowledge_dir)


def score(package_dir: Path, model_path: Path | None = None) -> list[dict]:
    """A2-07: deterministic opportunity scores (analysis_result `scores` items).
    Factors without evidence are insufficient_data with 0 points — never estimated."""
    model = load(model_path or ROOT / "knowledge" / "scoring" / "opportunity@1.json")
    cand = classify(package_dir)
    parts = [json.loads(l) for l in (Path(package_dir) / "participations.jsonl").read_text(encoding="utf-8").splitlines()]
    companies = sorted({p["company_id"] for p in parts})
    scores = []
    for cid in companies:
        ps = [p for p in parts if p["company_id"] == cid]
        listed = [p for p in ps if p["listing_status"] == "listed"]
        booth = [p for p in listed if p.get("booth")]
        hits = [x for x in cand.get(cid, {}).get("terms", []) if x in model["target_terms"]]
        factors = []
        for f in model["factors"]:
            fid, mx = f["factor_id"], f["max_points"]
            if fid == "domain_fit" and hits:
                factors.append({"factor_id": fid, "label": f["label"], "status": "scored", "points": min(mx, 10 * len(hits)), "max_points": mx,
                                "evidence_source_ids": cand[cid]["source_ids"], "rationale": "符合目標分類：" + "、".join(hits)})
            elif fid == "presence" and listed:
                factors.append({"factor_id": fid, "label": f["label"], "status": "scored", "points": mx, "max_points": mx,
                                "evidence_source_ids": sorted({s for p in listed for s in p["source_ids"]}), "rationale": "目前列於參展名單。"})
            elif fid == "booth_known" and booth:
                factors.append({"factor_id": fid, "label": f["label"], "status": "scored", "points": mx, "max_points": mx,
                                "evidence_source_ids": sorted({s for p in booth for s in p["source_ids"]}), "rationale": f"展位 {booth[0]['booth']}。"})
            else:
                factors.append({"factor_id": fid, "label": f["label"], "status": "insufficient_data", "points": 0, "max_points": mx,
                                "rationale": "沒有足夠證據，不計分。"})
        scores.append({"subject": {"entity_type": "company", "entity_id": cid}, "score_model_id": model["score_model_id"], "factors": factors,
                       "total_points": sum(f["points"] for f in factors), "max_total_points": sum(f["max_points"] for f in factors)})
    scores.sort(key=lambda s: (-s["total_points"], s["subject"]["entity_id"]))
    for i, s in enumerate(scores, 1):
        s["rank"] = i
        s["score_id"] = f"sc-{i:03d}"
    return scores


def validate_analysis(analysis_path: Path, package_dir: Path) -> dict:
    import evidence_check
    import knowledge_check
    a = load(analysis_path)
    errors = evidence_check.validate(a, Path(package_dir))
    errors += knowledge_check.check_analysis_products(a, ROOT / "knowledge")
    return {"validator": "skills/exhibitiq evidence_check (AR1-AR9 + EV1-EV7) + knowledge_check", "ok": not errors, "errors": errors}


ANALYSIS_ROOT = ROOT / "reports" / "analysis"
REVIEW_FIELDS = {"review_status", "reviewed_by", "reviewed_at"}


def save_analysis(analysis_path: Path, package_dir: Path, out_root: Path | None = None) -> dict:
    """Versioned save (A2-14): reports/analysis/<input_dataset_id>/<analysis_id>.json.

    Only validated results are written. A saved result is immutable: re-analysis needs a new
    analysis_id; the only allowed change to an existing file is the human review fields.
    """
    out_root = out_root or ANALYSIS_ROOT
    v = validate_analysis(analysis_path, package_dir)
    if not v["ok"]:
        return {"ok": False, "path": None, "action": "rejected", "errors": v["errors"]}
    a = load(analysis_path)
    target = out_root / a["input_dataset_id"] / f"{a['analysis_id']}.json"
    if target.exists():
        old = load(target)
        if old == a:
            return {"ok": True, "path": str(target), "action": "unchanged", "errors": []}
        changed = {k for k in set(old) | set(a) if old.get(k) != a.get(k)}
        if not changed <= REVIEW_FIELDS:
            return {"ok": False, "path": str(target), "action": "rejected",
                    "errors": [f"{target.name} already exists; saved analyses are immutable (changed: {sorted(changed)}). Re-analysis needs a new analysis_id."]}
        action = "review_updated"
    else:
        if a["review_status"] != "draft":
            return {"ok": False, "path": None, "action": "rejected", "errors": ["a new analysis must start as review_status=draft"]}
        others = list((out_root).glob(f"*/{a['analysis_id']}.json")) if out_root.exists() else []
        if others:
            return {"ok": False, "path": None, "action": "rejected", "errors": [f"analysis_id already used in {others[0]}"]}
        action = "created"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(target), "action": action, "errors": []}


CLAIM = {"fact": "事實", "inference": "AI 推論", "unknown": "資料不足"}
LEVEL = {"low": "低", "medium": "中", "high": "高"}
REL = {"potential_customer": "潛在客戶", "competitor": "競爭對手", "partner": "合作夥伴", "channel": "通路", "unrelated": "不相關", "unknown": "未知"}
REVIEW = {"draft": "未審核（draft）", "human_reviewed": "已人工審核", "approved": "已核准", "rejected": "已退回"}
TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "report-templates.json"


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def render_report(analysis_path: Path, package_dir: Path) -> str:
    """Markdown report (A2-12/A2-13) built ONLY from a validated analysis JSON (+ names and source details from its package).

    Sections and their order come from templates/report-templates.json for the analysis_type. An analysis
    that fails validation is not rendered (LookupError), so an unvalidated report cannot be published.
    """
    v = validate_analysis(analysis_path, package_dir)
    if not v["ok"]:
        raise LookupError("analysis failed validation; no report: " + "; ".join(v["errors"][:5]))
    pkg = Path(package_dir)
    a, m, tpl = load(analysis_path), load(pkg / "manifest.json"), load(TEMPLATES)
    srcs = {r["source_id"]: r for r in _jsonl(pkg / "sources.jsonl")}
    names = {r["company_id"]: r["name"] for r in _jsonl(pkg / "companies.jsonl")}
    ex = load(pkg / "exhibition.json") if (pkg / "exhibition.json").exists() else {}
    claims = {c["claim_id"]: c for c in a["conclusions"]}
    unc = {u["uncertainty_id"]: u for u in a.get("uncertainties", [])}
    num = {sid: i for i, sid in enumerate(a["evidence_source_ids"], 1)}
    cite = lambda ids: "".join(f"[{num[i]}]" for i in ids if i in num) or "—"
    who = lambda e: names.get(e["entity_id"], e["entity_id"]) if e["entity_type"] == "company" else e["entity_id"]
    t = tpl["types"][a["analysis_type"]]
    titles = tpl["section_titles"]

    def header():
        exname = ex.get("name_zh_hant") or ex.get("name") or m["exhibition_id"]
        return [f"- 報告類型：{t['label']}",
                f"- 展覽：{exname}｜屆次：{m.get('edition_year', m['edition_id'])}",
                f"- 資料包：`{a['input_dataset_id']}`（`{a['input_hash']}`）",
                f"- Skill：{a['skill_version']}｜產生時間：{a['generated_at']}",
                f"- **審核狀態：{REVIEW.get(a['review_status'], a['review_status'])}**"]

    def data_status():
        comp = m["completeness"]
        off = "未知" if comp["official_exhibitor_count"] is None else comp["official_exhibitor_count"]
        out = [f"- 資料類型：**{'合成資料（synthetic）：內容為虛構，不代表任何真實展覽或企業' if a['data_origin'] == 'synthetic' else '真實資料'}**",
               f"- 完整度：{m['completeness_status']}（已取得 {comp['collected_participation_count']}／官方公布 {off}）"]
        if m["completeness_status"] != "complete":
            out.append("- ⚠️ 資料不完整，結論與排名可能遺漏。")
        return out

    def summary():
        return [a["summary"]] if a.get("summary") else []

    def conclusions():
        out = []
        for c in a["conclusions"]:
            extra = f"（信心：{LEVEL[c['confidence']]}；理由：{c.get('rationale', '')}）" if c["claim_type"] == "inference" else ""
            missing = f"（缺少：{c['missing_data']}）" if c["claim_type"] == "unknown" else ""
            out.append(f"- **[{CLAIM[c['claim_type']]}]** {c['statement']}{extra}{missing}　來源：{cite(c.get('evidence_source_ids', []))}")
        return out

    def scores():
        out = []
        for s in sorted(a.get("scores", []), key=lambda s: s["rank"]):
            out += [f"### 第 {s['rank']} 名：{who(s['subject'])}　{s['total_points']}／{s['max_total_points']}（{s['score_model_id']}，AI 推論）", "",
                    "| 因子 | 得分 | 理由 | 來源 |", "|---|---|---|---|"]
            for f in s["factors"]:
                st = f"資料不足，不計分（0／{f['max_points']}）" if f["status"] == "insufficient_data" else f"{f['points']}／{f['max_points']}"
                out.append(f"| {f['label']} | {st} | {f.get('rationale', '')} | {cite(f.get('evidence_source_ids', []))} |")
            out.append("")
        return out

    def relationships():
        return [f"- {names.get(r['company_id'], r['company_id'])}：**{REL[r['relationship_type']]}**（AI 推論"
                + (f"，信心：{LEVEL[r['confidence']]}" if r.get("confidence") else "") + f"）{r.get('rationale', '')}　來源：{cite(r.get('evidence_source_ids', []))}"
                for r in a.get("relationships", [])]

    def recommendations():
        out = []
        for r in a["recommendations"]:
            out.append(f"- **[優先度：{LEVEL[r['priority']]}]** {r['statement']}（AI 推論）")
            out.append(f"  - 理由：{r['rationale']}")
            if r.get("assumptions"):
                out.append(f"  - 前提：{'；'.join(r['assumptions'])}")
            out.append(f"  - 依據結論：{'；'.join(claims[c]['statement'] for c in r['based_on_claim_ids'])}")
            if r.get("uncertainty_ids"):
                out.append(f"  - 不確定性：{'；'.join(unc[u]['description'] for u in r['uncertainty_ids'])}")
            out.append(f"  - 來源：{cite(r.get('evidence_source_ids', []))}")
        return out

    def uncertainties():
        return [f"- [影響：{LEVEL[u['impact']]}] {u['description']}" for u in a.get("uncertainties", [])]

    def sources():
        out = ["| # | source_id | 類型 | 網址 | 取得時間 | 快照雜湊 |", "|---|---|---|---|---|---|"]
        for sid, i in num.items():
            r = srcs[sid]
            out.append(f"| [{i}] | `{sid}` | {r['source_type']} | {r.get('url', '—')} | {r['retrieved_at']} | `{r['content_sha256']}` |")
        return out

    fns = {"header": header, "data_status": data_status, "summary": summary, "conclusions": conclusions, "scores": scores,
           "relationships": relationships, "recommendations": recommendations, "uncertainties": uncertainties, "sources": sources}
    # never drop content: a section that has data is rendered even if the template does not list it
    order = list(t["sections"])
    for sec, key in (("scores", "scores"), ("relationships", "relationships")):
        if a.get(key) and sec not in order:
            order.insert(order.index("recommendations"), sec)
    out = [f"# {a['title']}", ""]
    for sec in order:
        body = fns[sec]()
        out += [f"## {titles[sec]}", ""] + (body or ["無"]) + [""]
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="exhibitiq_tools")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("list", "select"):
        sp = sub.add_parser(name)
        if name == "select":
            sp.add_argument("exhibition_id")
            sp.add_argument("year", nargs="?", type=int)
        sp.add_argument("--index", type=Path, default=None)
    sub.add_parser("validate-package").add_argument("package_dir", type=Path)
    sub.add_parser("check-all").add_argument("--index", type=Path, default=None)
    for name in ("classify", "score", "relate"):
        sp = sub.add_parser(name)
        sp.add_argument("package_dir", type=Path)
        sp.add_argument("--profile", default=None, help="analysis profile id or path (knowledge/analysis-profiles/)")
    sub.add_parser("config").add_argument("profile")
    for name in ("validate-analysis", "report", "save-analysis"):
        sp = sub.add_parser(name)
        sp.add_argument("analysis", type=Path)
        sp.add_argument("package_dir", type=Path)
    a = p.parse_args(argv)
    idx = getattr(a, "index", None) or default_index()
    try:
        if a.cmd == "list":
            print(json.dumps(list_exhibitions(idx), ensure_ascii=False, indent=2))
        elif a.cmd == "select":
            print(json.dumps(select_package(idx, a.exhibition_id, a.year), ensure_ascii=False, indent=2))
        elif a.cmd == "check-all":
            rows = check_all(idx); print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0 if all(r["ok"] for r in rows if r["dataset_id"]) else 1
        elif a.cmd == "score":
            if a.profile:
                import profile_tools
                print(json.dumps(profile_tools.score(a.package_dir, a.profile), ensure_ascii=False, indent=2))
            else:  # legacy opportunity@1 draft (kept for comparison until Eric approves a model)
                print(json.dumps(score(a.package_dir), ensure_ascii=False, indent=2))
        elif a.cmd == "config":
            import profile_tools
            print(json.dumps(profile_tools.analysis_config(a.profile), ensure_ascii=False, indent=2))
        elif a.cmd == "relate":
            print(json.dumps(relate(a.package_dir, a.profile), ensure_ascii=False, indent=2))
        elif a.cmd == "classify":
            print(json.dumps(classify(a.package_dir, a.profile), ensure_ascii=False, indent=2))
        elif a.cmd == "validate-package":
            r = validate_package(a.package_dir); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r["ok"] else 1
        elif a.cmd == "validate-analysis":
            r = validate_analysis(a.analysis, a.package_dir); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r["ok"] else 1
        elif a.cmd == "save-analysis":
            r = save_analysis(a.analysis, a.package_dir); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r["ok"] else 1
        elif a.cmd == "report":
            sys.stdout.write(render_report(a.analysis, a.package_dir))
    except LookupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
