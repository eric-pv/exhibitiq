"""ExhibitIQ Skill helper (A2-03). Deterministic I/O around the analysis; no AI here.

Usage (from the repo root):
  python skills/exhibitiq/scripts/exhibitiq_tools.py list   [--index PATH]
  python skills/exhibitiq/scripts/exhibitiq_tools.py select  EXHIBITION_ID [YEAR] [--index PATH]
  python skills/exhibitiq/scripts/exhibitiq_tools.py check-all [--index PATH]
  python skills/exhibitiq/scripts/exhibitiq_tools.py validate-package PACKAGE_DIR
  python skills/exhibitiq/scripts/exhibitiq_tools.py validate-analysis ANALYSIS_JSON PACKAGE_DIR
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
    version = (ROOT / "schemas" / "v1" / "VERSION").read_text(encoding="utf-8").strip()
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
            if m.get("schema_version") != version:
                row["problems"].append(f"schema_version {m.get('schema_version')} != {version}")
            if m.get("content_hash") != sel["content_hash"]:
                row["problems"].append("content_hash differs from the dataset index")
            v = validate_package(Path(sel["package_dir"]))
            row["problems"] += v["errors"]
            row["validator"] = v["validator"]
            row["ok"] = not row["problems"]
            rows.append(row)
    return rows


def classify(package_dir: Path, taxonomy_dir: Path | None = None) -> dict:
    """A2-06: deterministic keyword candidates per company (inference input, never fact)."""
    import re
    tax = [load(p) for p in sorted((taxonomy_dir or ROOT / "knowledge" / "taxonomy").glob("*.json"))]
    words = [(t["term_id"], [t["label"], *t.get("synonyms", [])]) for d in tax for t in d["terms"]]
    out: dict[str, dict] = {}
    for line in (Path(package_dir) / "participations.jsonl").read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        text = " ".join([p["exhibitor_name_as_listed"], *p.get("categories_as_listed", []), *p.get("products_as_listed", [])])
        hits = sorted({tid for tid, ws in words for w in ws
                       if re.search(rf"(?<![A-Za-z]){re.escape(w)}(?:e?s)?(?![A-Za-z])", text, re.IGNORECASE)})
        entry = out.setdefault(p["company_id"], {"terms": set(), "source_ids": set()})
        entry["terms"] |= set(hits)
        if hits:
            entry["source_ids"] |= set(p["source_ids"])
    return {k: {"terms": sorted(v["terms"]), "source_ids": sorted(v["source_ids"])} for k, v in out.items()}


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


CLAIM = {"fact": "事實", "inference": "AI 推論", "unknown": "資料不足"}


def render_report(analysis_path: Path, package_dir: Path) -> str:
    """Markdown report built ONLY from the analysis JSON (+ source details from the package)."""
    a = load(analysis_path)
    m = load(Path(package_dir) / "manifest.json")
    srcs = {json.loads(l)["source_id"]: json.loads(l) for l in (Path(package_dir) / "sources.jsonl").read_text(encoding="utf-8").splitlines()}
    comp = m["completeness"]
    out = [f"# {a['title']}", "",
           f"- 資料包：`{a['input_dataset_id']}`（`{a['input_hash']}`）",
           f"- Skill：{a['skill_version']}｜產生時間：{a['generated_at']}｜**審核狀態：{a['review_status']}**",
           f"- 資料來源類型：**{'合成資料（synthetic）' if a['data_origin'] == 'synthetic' else '真實資料'}**",
           f"- 完整度：{m['completeness_status']}（已取得 {comp['collected_participation_count']}／官方公布 "
           f"{'未知' if comp['official_exhibitor_count'] is None else comp['official_exhibitor_count']}）", ""]
    if a.get("summary"):
        out += ["## 摘要", "", a["summary"], ""]
    out += ["## 結論", ""]
    for c in a["conclusions"]:
        ev = "、".join(f"`{s}`" for s in c.get("evidence_source_ids", [])) or "—"
        extra = f"（信心：{c['confidence']}）" if c["claim_type"] == "inference" else ""
        missing = f"；缺少：{c['missing_data']}" if c["claim_type"] == "unknown" else ""
        out.append(f"- **[{CLAIM[c['claim_type']]}]** {c['statement']}{extra}{missing}　來源：{ev}")
    if a.get("scores"):
        out += ["", "## 評分", ""]
        for s in sorted(a["scores"], key=lambda s: s["rank"]):
            out.append(f"### #{s['rank']} `{s['subject']['entity_id']}`：{s['total_points']}／{s['max_total_points']}（{s['score_model_id']}）")
            for f in s["factors"]:
                st = "資料不足，不計分" if f["status"] == "insufficient_data" else f"{f['points']}／{f['max_points']}"
                out.append(f"- {f['label']}：{st}；{f['rationale']}")
    if a["recommendations"]:
        out += ["", "## 建議", ""]
        for r in a["recommendations"]:
            out.append(f"- **[{r['priority']}]** {r['statement']}　理由：{r['rationale']}"
                       + (f"　前提：{'；'.join(r['assumptions'])}" if r.get("assumptions") else ""))
    out += ["", "## 不確定性與限制", ""] + [f"- [{u['impact']}] {u['description']}" for u in a["uncertainties"]]
    out += ["", "## 來源附錄", "", "| source_id | 類型 | 網址 | 取得時間 | 快照雜湊 |", "|---|---|---|---|---|"]
    for sid in a["evidence_source_ids"]:
        s = srcs.get(sid, {})
        out.append(f"| `{sid}` | {s.get('source_type', '?')} | {s.get('url', '—')} | {s.get('retrieved_at', '?')} | `{s.get('content_sha256', '?')}` |")
    return "\n".join(out) + "\n"


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
    sub.add_parser("classify").add_argument("package_dir", type=Path)
    sub.add_parser("score").add_argument("package_dir", type=Path)
    for name in ("validate-analysis", "report"):
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
            print(json.dumps(score(a.package_dir), ensure_ascii=False, indent=2))
        elif a.cmd == "classify":
            print(json.dumps(classify(a.package_dir), ensure_ascii=False, indent=2))
        elif a.cmd == "validate-package":
            r = validate_package(a.package_dir); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r["ok"] else 1
        elif a.cmd == "validate-analysis":
            r = validate_analysis(a.analysis, a.package_dir); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r["ok"] else 1
        elif a.cmd == "report":
            sys.stdout.write(render_report(a.analysis, a.package_dir))
    except LookupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
