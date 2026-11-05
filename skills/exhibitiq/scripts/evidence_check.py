"""Production analysis validator (A2-11): fact / inference / unknown separation and evidence rules.

Runs the contract checks (AR1-AR9, tests/contract/analysis_check.py) and then the Skill's
evidence rules (EV1-EV7, skills/exhibitiq/references/evidence-rules.md). An analysis with any
error must not be published (written to reports/analysis/ or shown on the Dashboard).
"""
from __future__ import annotations

import json
from pathlib import Path

import analysis_check

FACT_STATUSES = {"verified", "unverified", "human_confirmed"}
# a fact may not claim a stronger status than its weakest subject record in the package
STRENGTH = {"insufficient_data": 0, "unverified": 1, "human_confirmed": 2, "verified": 2}
CLASSIFIED = {"potential_customer", "competitor", "partner", "channel"}


def _records(pkg: Path, name: str, key: str) -> dict[str, dict]:
    p = pkg / name
    if not p.exists():
        return {}
    return {r[key]: r for r in (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())}


def check_evidence(a: dict, pkg: Path | None = None) -> list[str]:
    errors: list[str] = []
    claims = {c["claim_id"]: c for c in a.get("conclusions", [])}
    subjects_status: dict[str, str] = {}
    complete = True
    if pkg is not None:
        for name, key in (("companies.jsonl", "company_id"), ("participations.jsonl", "participation_id")):
            subjects_status.update({k: r["verification_status"] for k, r in _records(pkg, name, key).items()})
        complete = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))["completeness_status"] == "complete"

    for c in claims.values():
        cid, t = c["claim_id"], c["claim_type"]
        ev = c.get("evidence_source_ids", [])
        if t == "fact":  # EV1
            if not ev:
                errors.append(f"EV1 {cid}: fact without evidence")
            vs = c.get("verification_status")
            if vs not in FACT_STATUSES:
                errors.append(f"EV1 {cid}: fact needs verification_status in {sorted(FACT_STATUSES)}")
            if c.get("confidence") is not None:
                errors.append(f"EV1 {cid}: a fact carries no AI confidence")
            for s in c.get("subjects", []):
                rec = subjects_status.get(s["entity_id"])
                if vs and rec and STRENGTH.get(vs, 0) > STRENGTH.get(rec, 0):
                    errors.append(f"EV1 {cid}: claims '{vs}' but package record {s['entity_id']} is '{rec}'")
        elif t == "inference":  # EV2
            if not ev:
                errors.append(f"EV2 {cid}: inference without evidence")
            for k in ("rationale", "confidence"):
                if not c.get(k):
                    errors.append(f"EV2 {cid}: inference without {k}")
            if not c.get("uncertainty_ids"):
                errors.append(f"EV2 {cid}: inference without uncertainty_ids")
            if c.get("verification_status"):
                errors.append(f"EV2 {cid}: an inference cannot carry a fact verification_status")
        elif t == "unknown":  # EV3
            if not c.get("missing_data"):
                errors.append(f"EV3 {cid}: unknown without missing_data")
            if c.get("confidence") is not None:
                errors.append(f"EV3 {cid}: unknown cannot have confidence (no guessing)")

    for s in a.get("scores", []):  # EV4
        for f in s["factors"]:
            where = f"{s['score_id']}.{f['factor_id']}"
            if f["status"] == "scored":
                if not f.get("evidence_source_ids"):
                    errors.append(f"EV4 {where}: scored without evidence")
                if any(claims.get(i, {}).get("claim_type") == "unknown" for i in f.get("claim_ids", [])):
                    errors.append(f"EV4 {where}: scored on an unknown claim")
            elif f["points"] != 0:
                errors.append(f"EV4 {where}: insufficient_data must score 0")

    for r in a.get("relationships", []):  # EV5
        if r["relationship_type"] in CLASSIFIED:
            if not r.get("evidence_source_ids"):
                errors.append(f"EV5 {r['relationship_id']}: classified relationship without evidence")
            if not r.get("confidence"):
                errors.append(f"EV5 {r['relationship_id']}: classified relationship without confidence")

    if not complete:  # EV6
        if not a.get("uncertainties"):
            errors.append("EV6 input package is not complete but no uncertainty is listed")
        for r in a.get("recommendations", []):
            if not r.get("uncertainty_ids"):
                errors.append(f"EV6 {r['recommendation_id']}: incomplete input but no uncertainty cited")

    import re
    money = re.compile(r"(NT\$|US\$|\$|€|£|¥|新台幣|台幣|美元|歐元|預算|元整|萬元|千元|budget|USD|TWD|EUR)", re.IGNORECASE)
    for r in a.get("recommendations", []):  # EV7
        if not r.get("evidence_source_ids"):
            errors.append(f"EV7 {r['recommendation_id']}: recommendation without evidence")
        # EV8 (Eric 2026-11-05): business value only — no budget or money amounts in any recommendation
        text = " ".join([r["statement"], r.get("rationale", ""), *r.get("assumptions", [])])
        if money.search(text):
            errors.append(f"EV8 {r['recommendation_id']}: recommendations must not contain budget or money amounts")
        if r["recommendation_type"] == "participation_decision" and not (r.get("score_ids") or r.get("based_on_claim_ids")):
            errors.append(f"EV8 {r['recommendation_id']}: participation decision must cite scores or conclusions")
    return errors


def validate(a: dict, pkg: Path | None = None) -> list[str]:
    errors = analysis_check.check_analysis(a, pkg)
    if errors and errors[0].startswith("AR1"):
        return errors
    return errors + check_evidence(a, pkg)
