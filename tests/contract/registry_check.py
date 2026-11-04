"""Reference checks for the exhibition registry contract (A1-10).

Registry layout: data/registry/<exhibition_id>/registration.json
(docs/specs/exhibition-registry-contract.md §6). The production writer and
validator belong to data engineering (D2-13).
"""
from __future__ import annotations

import json
from pathlib import Path

import package_check as pc


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def check_registration(doc: dict, folder: str | None = None) -> list[str]:
    errors = [f"RG1 {e.message}" for e in pc.validator("exhibition_registration").iter_errors(doc)]
    if errors:
        return errors
    if doc["schema_version"] not in pc.ACCEPTED:
        errors.append("RG2 schema_version != VERSION")
    if folder is not None and folder != doc["exhibition_id"]:
        errors.append(f"RG3 folder {folder} != exhibition_id {doc['exhibition_id']}")
    if doc.get("duplicate_of") and doc["registration_status"] != "rejected":
        errors.append("RG4 duplicate_of is only allowed on rejected registrations")
    if doc.get("duplicate_of") == doc["exhibition_id"]:
        errors.append("RG4 duplicate_of points to itself")
    return errors


def load_registry(root: Path) -> dict[str, dict]:
    return {p.parent.name: _load(p) for p in sorted(root.glob("*/registration.json"))}


def check_registry_dir(root: Path) -> list[str]:
    errors: list[str] = []
    regs = load_registry(root)
    for folder, doc in regs.items():
        errors += [f"{folder}: {e}" for e in check_registration(doc, folder)]
    for folder, doc in regs.items():
        target = doc.get("duplicate_of")
        if target and regs.get(target, {}).get("registration_status") != "accepted":
            errors.append(f"{folder}: RG5 duplicate_of {target} is not an accepted registration")
    for p in sorted(root.iterdir()) if root.exists() else []:
        if p.is_dir() and not (p / "registration.json").is_file():
            errors.append(f"{p.name}: RG3 folder without registration.json")
    return errors


def check_registry_vs_index(root: Path, index: dict) -> list[str]:
    """RG6: the dataset index lists exactly the accepted registrations, for the registered years."""
    regs = {k: v for k, v in load_registry(root).items() if v.get("registration_status") == "accepted"}
    listed = {e["exhibition_id"]: e for e in index["exhibitions"]}
    errors = [f"RG6 accepted registration {k} missing from dataset index" for k in sorted(set(regs) - set(listed))]
    errors += [f"RG6 dataset index lists {k} without an accepted registration" for k in sorted(set(listed) - set(regs))]
    for k in sorted(set(regs) & set(listed)):
        years = {ed["year"] for ed in listed[k]["editions"]}
        missing = sorted(set(regs[k]["years"]) - years)
        if missing:
            errors.append(f"RG6 {k}: registered years {missing} have no edition in the dataset index")
    return errors
