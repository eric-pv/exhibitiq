"""Reference checks for the v1 analysis-result contract (A1-06).

Proves that schemas/v1/examples/analysis/ satisfies every rule in
docs/specs/analysis-result-contract.md §8. The production analysis
validator belongs to the Skill (A2-11, skills/exhibitiq/); once it exists,
these tests should call it instead of this module.
"""
from __future__ import annotations

import json
from pathlib import Path

import package_check as pc


def _local_ids(result: dict) -> dict[str, list[str]]:
    return {
        "cl": [c["claim_id"] for c in result.get("conclusions", [])],
        "un": [u["uncertainty_id"] for u in result.get("uncertainties", [])],
        "sc": [s["score_id"] for s in result.get("scores", [])],
        "rel": [r["relationship_id"] for r in result.get("relationships", [])],
        "rec": [r["recommendation_id"] for r in result.get("recommendations", [])],
    }


def _all_evidence(result: dict) -> set[str]:
    out: set[str] = set()
    for c in result.get("conclusions", []):
        out |= set(c.get("evidence_source_ids", []))
    for s in result.get("scores", []):
        for f in s["factors"]:
            out |= set(f.get("evidence_source_ids", []))
    for key in ("relationships", "recommendations"):
        for r in result.get(key, []):
            out |= set(r.get("evidence_source_ids", []))
    return out


def _package_records(pkg: Path, name: str) -> list[dict]:
    text = (pkg / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def check_analysis(result: dict, pkg: Path | None = None) -> list[str]:
    """Return rule violations (empty = valid). ``pkg`` is the input package."""
    errors = [f"AR1 {e.message}" for e in pc.validator("analysis_result").iter_errors(result)]
    if errors:
        return errors  # structural errors make the remaining rules meaningless

    # AR2 schema version
    if result["schema_version"] not in pc.ACCEPTED:
        errors.append("AR2 schema_version != VERSION")

    # AR3 local IDs unique
    local = _local_ids(result)
    for kind, ids in local.items():
        if len(ids) != len(set(ids)):
            errors.append(f"AR3 duplicate {kind}- IDs")

    # AR4 internal references resolve
    known = {k: set(v) for k, v in local.items()}

    def need(kind: str, refs, where: str):
        missing = set(refs) - known[kind]
        if missing:
            errors.append(f"AR4 {where}: unknown {kind}- IDs {sorted(missing)}")

    for c in result["conclusions"]:
        need("un", c.get("uncertainty_ids", []), c["claim_id"])
    for s in result.get("scores", []):
        for f in s["factors"]:
            need("cl", f.get("claim_ids", []), f"{s['score_id']}.{f['factor_id']}")
    for r in result.get("relationships", []):
        need("cl", r.get("claim_ids", []), r["relationship_id"])
        need("un", r.get("uncertainty_ids", []), r["relationship_id"])
    for r in result["recommendations"]:
        need("cl", r["based_on_claim_ids"], r["recommendation_id"])
        need("sc", r.get("score_ids", []), r["recommendation_id"])
        need("un", r.get("uncertainty_ids", []), r["recommendation_id"])
        # a recommendation cannot rest only on unknown claims
        types = {c["claim_id"]: c["claim_type"] for c in result["conclusions"]}
        if all(types.get(cid) == "unknown" for cid in r["based_on_claim_ids"]):
            errors.append(f"AR4 {r['recommendation_id']}: based only on unknown claims")

    # AR5 top-level evidence == union of nested evidence
    if set(result["evidence_source_ids"]) != _all_evidence(result):
        errors.append("AR5 evidence_source_ids != union of nested evidence")

    # AR6 score arithmetic and ranking
    by_model: dict[str, list[dict]] = {}
    for s in result.get("scores", []):
        pts = sum(f["points"] for f in s["factors"])
        mx = sum(f["max_points"] for f in s["factors"])
        if abs(pts - s["total_points"]) > 1e-9:
            errors.append(f"AR6 {s['score_id']}: total_points != sum of factor points")
        if abs(mx - s["max_total_points"]) > 1e-9:
            errors.append(f"AR6 {s['score_id']}: max_total_points != sum of factor max_points")
        for f in s["factors"]:
            if f["points"] > f["max_points"]:
                errors.append(f"AR6 {s['score_id']}.{f['factor_id']}: points > max_points")
        by_model.setdefault(s["score_model_id"], []).append(s)
    for model, scores in by_model.items():
        factor_sets = {tuple(sorted(f["factor_id"] for f in s["factors"])) for s in scores}
        if len(factor_sets) != 1:
            errors.append(f"AR6 {model}: scores use different factor sets")
        ranks = sorted(s["rank"] for s in scores)
        if ranks != list(range(1, len(scores) + 1)):
            errors.append(f"AR6 {model}: ranks must be 1..n without gaps")
        ordered = sorted(scores, key=lambda s: s["rank"])
        if any(a["total_points"] < b["total_points"] for a, b in zip(ordered, ordered[1:])):
            errors.append(f"AR6 {model}: rank order does not follow total_points")

    # AR7-AR9 need the input package
    if pkg is not None:
        manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
        # AR7 input identity
        if result["input_dataset_id"] != manifest["dataset_id"]:
            errors.append("AR7 input_dataset_id != package dataset_id")
        if result["input_hash"] != manifest["content_hash"]:
            errors.append("AR7 input_hash != package content_hash")
        # AR8 provenance: every cited source and subject exists in the package
        sources = {s["source_id"] for s in _package_records(pkg, "sources.jsonl")}
        missing = set(result["evidence_source_ids"]) - sources
        if missing:
            errors.append(f"AR8 evidence not in package sources: {sorted(missing)}")
        entities = {
            "company": {r["company_id"] for r in _package_records(pkg, "companies.jsonl")},
            "participation": {r["participation_id"] for r in _package_records(pkg, "participations.jsonl")},
            "exhibition": {manifest["exhibition_id"]},
            "edition": {manifest["edition_id"]},
        }
        subjects = [s for c in result["conclusions"] for s in c.get("subjects", [])]
        subjects += [s["subject"] for s in result.get("scores", [])]
        subjects += [s for r in result["recommendations"] for s in r.get("subjects", [])]
        subjects += [{"entity_type": "company", "entity_id": r["company_id"]} for r in result.get("relationships", [])]
        for s in subjects:
            if s["entity_id"] not in entities[s["entity_type"]]:
                errors.append(f"AR8 unknown {s['entity_type']} {s['entity_id']}")
        # AR9 synthetic input cannot produce a 'collected' analysis
        if manifest["data_origin"] == "synthetic" and result["data_origin"] != "synthetic":
            errors.append("AR9 analysis of synthetic data must be data_origin=synthetic")

    # AR11 analysis_config (A2-15): reproducible analysis settings
    import profile_check
    errors += profile_check.check_analysis_config(result)

    return errors
