"""Reference checks for the v1 dataset-index contract (A1-07).

Proves schemas/v1/examples/index/ satisfies docs/specs/dataset-index-contract.md §6.
The production index is generated and validated by data engineering (D2-12).
"""
from __future__ import annotations

import json
from pathlib import Path

import package_check as pc


def check_index(index: dict, repo_root: Path = pc.ROOT) -> list[str]:
    errors = [f"IR1 {e.message}" for e in pc.validator("dataset_index").iter_errors(index)]
    if errors:
        return errors
    if index["schema_version"] not in pc.ACCEPTED:
        errors.append("IR2 schema_version != VERSION")

    ex_ids = [e["exhibition_id"] for e in index["exhibitions"]]
    ed_ids, ds_ids = [], []
    for ex in index["exhibitions"]:
        for ed in ex["editions"]:
            ed_ids.append(ed["edition_id"])
            # IR3 identity consistency
            if not ed["edition_id"].startswith(ex["exhibition_id"] + "-"):
                errors.append(f"IR3 {ed['edition_id']}: must start with '{ex['exhibition_id']}-'")
            if f"-{ed['year']}" not in ed["edition_id"]:
                errors.append(f"IR3 {ed['edition_id']}: year {ed['year']} not in edition_id")
            passed = []
            for ds in ed["datasets"]:
                ds_ids.append(ds["dataset_id"])
                if not ds["dataset_id"].startswith(ed["edition_id"] + "."):
                    errors.append(f"IR3 {ds['dataset_id']}: must start with '{ed['edition_id']}.'")
                if ds["validation"]["status"] == "passed":
                    passed.append(ds)
                # IR6 summary must match the package when it is in this repo
                if ds["location"]["storage"] == "git":
                    pkg = repo_root / ds["location"]["locator"]
                    if not (pkg / "manifest.json").is_file():
                        errors.append(f"IR6 {ds['dataset_id']}: package not found at {ds['location']['locator']}")
                        continue
                    m = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
                    comp = m["completeness"]
                    expect = {
                        "dataset_id": m["dataset_id"], "data_origin": m["data_origin"],
                        "schema_version": m["schema_version"], "content_hash": m["content_hash"],
                        "completeness_status": m["completeness_status"],
                        "official_exhibitor_count": comp["official_exhibitor_count"],
                        "collected_participation_count": comp["collected_participation_count"],
                        "created_at": m["created_at"],
                    }
                    for k, v in expect.items():
                        if ds[k] != v:
                            errors.append(f"IR6 {ds['dataset_id']}: {k} != manifest")
                    for k in ("companies", "participations", "sources"):
                        if ds["record_counts"][k] != m["record_counts"][k]:
                            errors.append(f"IR6 {ds['dataset_id']}: record_counts.{k} != manifest")
                    if ds["validation"]["status"] == "passed" and pc.check_package(pkg):
                        errors.append(f"IR6 {ds['dataset_id']}: marked passed but package fails validation")
            # IR4 latest = newest passed dataset, or null when none passed
            want = max(passed, key=lambda d: d["created_at"])["dataset_id"] if passed else None
            if ed["latest_dataset_id"] != want:
                errors.append(f"IR4 {ed['edition_id']}: latest_dataset_id should be {want}")
            # IR5 last acquisition references a listed dataset
            la = ed.get("last_acquisition")
            if la and la.get("dataset_id") and la["dataset_id"] not in {d["dataset_id"] for d in ed["datasets"]}:
                errors.append(f"IR5 {ed['edition_id']}: last_acquisition.dataset_id not listed")

    for label, ids in (("exhibition", ex_ids), ("edition", ed_ids), ("dataset", ds_ids)):
        if len(ids) != len(set(ids)):
            errors.append(f"IR3 duplicate {label} IDs")
    # IR7 notices reference known entities
    for n in index["notices"]:
        if n.get("exhibition_id") and n["exhibition_id"] not in ex_ids:
            errors.append(f"IR7 notice references unknown exhibition {n['exhibition_id']}")
        if n.get("dataset_id") and n["dataset_id"] not in ds_ids:
            errors.append(f"IR7 notice references unknown dataset {n['dataset_id']}")
    return errors
