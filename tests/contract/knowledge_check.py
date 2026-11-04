"""Reference checks for the knowledge-base contract (A1-09).

Validates knowledge/ (taxonomy + BXR product cards) and the analysis rule
that recommendations may only cite approved products. See
docs/specs/knowledge-base-contract.md §5.
"""
from __future__ import annotations

import json
from pathlib import Path

import package_check as pc

FIELD_DIMENSION = {"capabilities": "capability", "applications": "application",
                   "target_industries": "industry", "problems_addressed": "problem"}


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def check_taxonomy(doc: dict, filename: str | None = None) -> list[str]:
    errors = [f"KB1 {e.message}" for e in pc.validator("taxonomy").iter_errors(doc)]
    if errors:
        return errors
    if doc["schema_version"] not in pc.ACCEPTED:
        errors.append("KB2 schema_version != VERSION")
    if filename and filename != f"{doc['dimension']}.json":
        errors.append(f"KB3 file {filename} must be named {doc['dimension']}.json")
    ids = [t["term_id"] for t in doc["terms"]]
    if len(ids) != len(set(ids)):
        errors.append("KB3 duplicate term_id")
    for t in doc["terms"]:
        if not t["term_id"].startswith(doc["dimension"] + "."):
            errors.append(f"KB3 {t['term_id']} is not in dimension {doc['dimension']}")
        if t.get("parent_id") and t["parent_id"] not in ids:
            errors.append(f"KB3 {t['term_id']}: parent {t['parent_id']} not found")
    return errors


def check_product(doc: dict, filename: str | None = None, approved_terms: set[str] | None = None) -> list[str]:
    errors = [f"KB1 {e.message}" for e in pc.validator("bxr_product").iter_errors(doc)]
    if errors:
        return errors
    if doc["schema_version"] not in pc.ACCEPTED:
        errors.append("KB2 schema_version != VERSION")
    if filename and filename != f"{doc['product_id']}.json":
        errors.append(f"KB4 file {filename} must be named {doc['product_id']}.json")
    for field, dim in FIELD_DIMENSION.items():
        for term in doc.get(field, []):
            if not term.startswith(dim + "."):
                errors.append(f"KB4 {field} must reference {dim}.* terms, got {term}")
            elif doc["approval_status"] == "approved" and approved_terms is not None and term not in approved_terms:
                errors.append(f"KB6 approved product references unapproved/unknown term {term}")
    for s in doc.get("specifications", []):
        if s["source_index"] >= len(doc["sources"]):
            errors.append(f"KB5 specification {s['name']!r} points to a missing source")
    return errors


def check_knowledge_dir(root: Path) -> list[str]:
    errors: list[str] = []
    approved: set[str] = set()
    for f in sorted((root / "taxonomy").glob("*.json")):
        doc = _load(f)
        errors += [f"{f.name}: {e}" for e in check_taxonomy(doc, f.name)]
        if doc.get("approval_status") == "approved":
            approved |= {t["term_id"] for t in doc.get("terms", [])}
    for f in sorted((root / "bxr-products").glob("*.json")):
        errors += [f"{f.name}: {e}" for e in check_product(_load(f), f.name, approved)]
    return errors


def approved_product_ids(root: Path) -> set[str]:
    return {d["product_id"] for f in (root / "bxr-products").glob("*.json")
            if (d := _load(f)).get("approval_status") == "approved"}


def check_analysis_products(analysis: dict, root: Path) -> list[str]:
    """AR10: recommendations may only cite approved BXR products."""
    ok = approved_product_ids(root)
    return [f"AR10 {r['recommendation_id']}: product {p} is not an approved product card"
            for r in analysis.get("recommendations", []) for p in r.get("product_ids", []) if p not in ok]
