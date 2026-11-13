"""Completeness, gap and quality report for one data package (D2-09).

Every number is counted from the package; nothing is estimated. The official count (if the package has one) is
compared with the number of ``listed`` participations; the difference is reported as a difference, not as a guess
about what is missing. Quality flags are *observations* for a person to review, never corrections.

Run: ``python -m etl.report <package_dir> [--json]`` (Markdown by default).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from etl.normalize import name_keys
from etl.package import PackageError, read_package
from etl.validate import validate_package

COMPANY_FIELDS = ("name_en", "name_zh_hant", "aliases", "country", "website", "domains", "description")
PARTICIPATION_FIELDS = ("booth", "hall", "country_as_listed", "website_as_listed", "categories_as_listed", "products_as_listed")


def _coverage(records: Sequence[dict[str, Any]], fields: Iterable[str]) -> dict[str, dict[str, Any]]:
    total = len(records)
    out = {}
    for name in fields:
        present = sum(1 for r in records if r.get(name) not in (None, "", [], {}))
        out[name] = {"present": present, "missing": total - present}
    return out


def build_report(package_dir: str | Path) -> dict[str, Any]:
    directory = Path(package_dir)
    validation = validate_package(directory)
    package = read_package(directory)
    manifest, records = package.manifest, package.records
    companies, parts, sources, runs = records["companies"], records["participations"], records["sources"], records["crawl_runs"]
    listed = [p for p in parts if p["listing_status"] == "listed"]

    completeness = dict(manifest["completeness"])
    official = completeness.get("official_exhibitor_count")
    gaps: list[str] = []
    if manifest["completeness_status"] == "unknown":
        gaps.append("No official exhibitor count is known, so completeness cannot be judged.")
    elif official is not None and len(listed) != official:
        gaps.append(f"The official count is {official} but {len(listed)} listed participations were collected (difference {official - len(listed):+d}).")
    if manifest["data_origin"] == "synthetic":
        gaps.append("Synthetic test data: not a fact about any real exhibition.")
    failed = [r for r in runs if r["status"] in ("failed", "partial", "cancelled")]
    if failed:
        gaps.append(f"{len(failed)} crawl run(s) did not fully succeed: " + ", ".join(f"{r['crawl_run_id']} ({r['status']})" for r in failed))
    not_stored = [s["source_id"] for s in sources if s["snapshot"]["storage"] == "not_stored"]
    if not_stored:
        gaps.append(f"{len(not_stored)} source snapshot(s) were not stored; their content cannot be re-checked.")

    flags: list[dict[str, Any]] = []
    groups: dict[str, list[str]] = {}
    for company in companies:
        if company.get("status") == "active":
            groups.setdefault(name_keys(company["name"]).loose, []).append(company["company_id"])
    for key, ids in sorted(groups.items()):
        if len(ids) > 1:
            flags.append({"flag": "possible_duplicate_companies", "company_ids": sorted(ids), "detail": "same name apart from legal form; not merged"})
    no_site = [c["company_id"] for c in companies if c.get("status") == "active" and not c.get("website")]
    if no_site:
        flags.append({"flag": "companies_without_website", "count": len(no_site)})
    if parts and not any(p.get("booth") for p in parts):
        flags.append({"flag": "no_booth_information", "detail": "no participation has a booth"})

    return {
        "dataset_id": manifest["dataset_id"], "edition_id": manifest["edition_id"], "data_origin": manifest["data_origin"],
        "valid": validation.ok, "validation_findings": [str(f) for f in validation.findings],
        "completeness": {"status": manifest["completeness_status"], **completeness, "listed_participations": len(listed)},
        "counts": {
            "companies": len(companies), "participations": len(parts), "listed": len(listed), "removed": len(parts) - len(listed),
            "sources": len(sources), "crawl_runs": len(runs), "changes": len(records["changes"]),
            "by_participation_type": dict(sorted(Counter(p["participation_type"] for p in parts).items())),
            "by_verification_status": dict(sorted(Counter(r["verification_status"] for r in [*companies, *parts]).items())),
            "crawl_runs_by_status": dict(sorted(Counter(r["status"] for r in runs).items())),
        },
        "field_coverage": {"companies": _coverage(companies, COMPANY_FIELDS), "participations": _coverage(parts, PARTICIPATION_FIELDS)},
        "gaps": gaps, "quality_flags": flags,
    }


def to_markdown(report: dict[str, Any]) -> str:
    c, n = report["completeness"], report["counts"]
    lines = [f"# Completeness report: {report['dataset_id']}", "",
             f"- Data origin: **{report['data_origin']}**; validator: **{'passed' if report['valid'] else 'FAILED'}**",
             f"- Completeness: **{c['status']}** (official count: {c['official_exhibitor_count'] if c['official_exhibitor_count'] is not None else 'unknown'}, collected listed: {c['listed_participations']})",
             f"- Companies {n['companies']}, participations {n['participations']} (listed {n['listed']}, removed {n['removed']}), sources {n['sources']}, crawl runs {n['crawl_runs']}, changes {n['changes']}", "", "## Gaps", ""]
    lines += [f"- {g}" for g in report["gaps"]] or ["- none found"]
    lines += ["", "## Field coverage", "", "| entity | field | present | missing |", "|---|---|---:|---:|"]
    for entity, fields in report["field_coverage"].items():
        lines += [f"| {entity} | {name} | {v['present']} | {v['missing']} |" for name, v in fields.items()]
    lines += ["", "## Quality flags (for review; nothing was changed)", ""]
    lines += [f"- {f['flag']}: " + json.dumps({k: v for k, v in f.items() if k != 'flag'}, ensure_ascii=False) for f in report["quality_flags"]] or ["- none"]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.report", description="Completeness and quality report for a data package.")
    parser.add_argument("package_dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.package_dir)
    except (PackageError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else to_markdown(report), end="\n" if args.json else "")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
