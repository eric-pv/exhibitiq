"""Reference checks for analysis profiles and analysis_config (A2-15, docs/specs/analysis-profile-contract.md).

profile_hash = "sha256:" + SHA-256 of the canonical JSON (keys sorted at every level, separators "," and ":",
UTF-8 without escaping). The Dashboard computes the same hash in the browser.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import package_check as pc

PROFILES_DIR = pc.ROOT / "knowledge" / "analysis-profiles"
NON_BXR_MODES = {"industry_research", "competitor_research"}


def canonical(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def profile_hash(doc: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()


def check_profile(doc: dict, filename: str | None = None) -> list[str]:
    errors = [f"PF1 {e.message}" for e in pc.validator("analysis_profile").iter_errors(doc)]
    if errors:
        return errors
    if filename and filename != f"{doc['profile_id']}.json":
        errors.append(f"PF2 file name {filename} != {doc['profile_id']}.json")
    ids = [k["term_id"] for k in doc["keywords"]]
    if len(ids) != len(set(ids)):
        errors.append("PF3 duplicate keyword term_id")
    missing = set(doc.get("targets", {}).get("focus_term_ids", [])) - set(ids)
    if missing:
        errors.append(f"PF4 focus_term_ids not in keywords: {sorted(missing)}")
    if doc["mode"] in NON_BXR_MODES and doc.get("targets", {}).get("bxr_product_ids"):
        errors.append("PF5 modes B and C must not depend on BXR product cards")
    return errors


def load_profiles(directory: Path = PROFILES_DIR) -> dict[str, dict]:
    if not directory.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))}


def check_analysis_config(result: dict, profiles: dict[str, dict] | None = None) -> list[str]:
    """AR11. Results without analysis_config (older ones) are still valid."""
    cfg = result.get("analysis_config")
    if cfg is None:
        return []
    errors = []
    snap = cfg["keywords_snapshot"]
    ids = [k["term_id"] for k in snap]
    if len(ids) != len(set(ids)):
        errors.append("AR11 keywords_snapshot has duplicate term_id")
    if any(not k["enabled"] for k in snap):
        errors.append("AR11 keywords_snapshot must contain only the enabled keywords used")
    scores = result.get("scores", [])
    if not cfg.get("score_model_id") and scores:
        errors.append("AR11 scores present but the profile has no score model")
    if cfg.get("score_model_id") and any(s["score_model_id"] != cfg["score_model_id"] for s in scores):
        errors.append("AR11 scores use a different score model than analysis_config")
    if cfg["mode"] in NON_BXR_MODES:
        if cfg.get("bxr_products_status", "not_used") != "not_used":
            errors.append("AR11 modes B and C must not use BXR product cards")
        if any(r.get("product_ids") for r in result.get("recommendations", [])):
            errors.append("AR11 modes B and C cannot recommend BXR products")
    elif cfg.get("bxr_products_status") is None:
        errors.append("AR11 mode bxr_opportunity must state bxr_products_status")
    prof = (profiles if profiles is not None else load_profiles()).get(cfg["profile_id"])
    if prof is not None and prof["version"] == cfg["profile_version"]:
        if profile_hash(prof) != cfg["profile_hash"]:
            errors.append("AR11 profile_hash does not match the stored profile of the same version")
        if prof["mode"] != cfg["mode"]:
            errors.append("AR11 mode differs from the stored profile")
        enabled = sorted((k for k in prof["keywords"] if k["enabled"]), key=lambda k: k["term_id"])
        if enabled != sorted(snap, key=lambda k: k["term_id"]):
            errors.append("AR11 keywords_snapshot differs from the stored profile's enabled keywords")
    return errors
