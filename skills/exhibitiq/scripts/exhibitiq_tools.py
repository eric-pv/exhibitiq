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
checks in tests/contract and says so in its output. Analysis validation uses the
contract reference checks until A2-11 provides the production validator.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "contract"))
sys.path.insert(0, str(ROOT))

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


def validate_analysis(analysis_path: Path, package_dir: Path) -> dict:
    import analysis_check
    import knowledge_check
    a = load(analysis_path)
    errors = analysis_check.check_analysis(a, Path(package_dir))
    errors += knowledge_check.check_analysis_products(a, ROOT / "knowledge")
    return {"validator": "tests/contract analysis_check + knowledge_check (until A2-11)", "ok": not errors, "errors": errors}


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
