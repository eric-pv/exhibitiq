"""Dataset index and pipeline status (D2-12): the file the Dashboard reads (`data/index/datasets.json`).

``build_index`` walks the data packages under a root, validates each one (R1-R11), and writes the index described in
``docs/specs/dataset-index-contract.md``: per exhibition the acquisition assessment, per edition the last acquisition
(**failures included**) and a summary of every package. ``validate_index`` checks IR1-IR7 so a bad index is never
published. Packages are versioned by their ``dataset_id``; the index points at them and never changes them.

Honest defaults: an exhibition without a recorded assessment is ``undetermined`` / ``not_assessed``. A failed
acquisition has a note and no dataset. A package that fails the validator is listed with its findings but is never
the "latest". Exhibition-specific facts come from the packages and from the assessments file; no exhibition is named here.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.package import PackageError, read_package
from etl.schema_registry import SchemaSet
from etl.validate import validate_package

MAX_MESSAGES = 20
VALIDATOR = {"name": "exhibitiq-etl-validate", "version": "1.0.0"}


def _ts(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _package_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for ex in root.iterdir() if ex.is_dir() and not ex.name.startswith(".") for yr in ex.iterdir() if yr.is_dir() and not yr.name.startswith(".") for p in yr.iterdir() if p.is_dir() and not p.name.startswith("."))


def _last_run(runs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return max(runs, key=lambda r: (r["finished_at"], r["crawl_run_id"]), default=None)


def build_index(
    packages_root: str | Path,
    *,
    generated_at: datetime,
    generator: Mapping[str, str],
    assessments: Mapping[str, Mapping[str, Any]] | None = None,
    extra_runs: Sequence[Mapping[str, Any]] = (),
    locator_prefix: str = "data/packages",
    schemas: SchemaSet | None = None,
) -> dict[str, Any]:
    """``assessments``: ``{exhibition_id: {method, status, assessed_at, report_path, notes, name?}}`` from the source assessment.
    ``extra_runs``: ``crawl_run`` records (e.g. failed runs that produced no package), each carrying ``exhibition_id`` / ``edition_id``."""
    schemas = schemas or SchemaSet()
    assessments = assessments or {}
    root = Path(packages_root)
    now = _ts(generated_at)
    exhibitions: dict[str, dict[str, Any]] = {}
    editions: dict[tuple[str, str], dict[str, Any]] = {}
    runs_of: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    run_dataset: dict[str, str] = {}  # crawl_run_id -> the newest passed package that contains it
    notices: list[dict[str, Any]] = []

    for directory in _package_dirs(root):
        try:
            report = validate_package(directory, schema_dir=schemas.directory)
            package = read_package(directory)
        except (PackageError, OSError, ValueError) as exc:
            notices.append({"level": "error", "message": f"{directory.name} cannot be read and is not indexed: {exc}"[:500], "occurred_at": now})
            continue
        manifest, exhibition = package.manifest, package.exhibition
        ex_id, ed_id = manifest["exhibition_id"], manifest["edition_id"]
        entry = exhibitions.setdefault(ex_id, {"exhibition_id": ex_id, "name": exhibition["name"], "editions": []})
        for key in ("name_zh_hant", "country", "website"):
            if exhibition.get(key) and key not in entry:
                entry[key] = exhibition[key]
        edition = editions.setdefault((ex_id, ed_id), {"edition_id": ed_id, "year": manifest["edition_year"], "datasets": []})
        validation: dict[str, Any] = {"status": "passed" if report.ok else "failed", "validated_at": now, "validator": dict(VALIDATOR), "error_count": len(report.findings)}
        if not report.ok:
            validation["messages"] = [str(f)[:500] for f in report.findings[:MAX_MESSAGES]]
            notices.append({"level": "error", "message": f"{manifest['dataset_id']} failed validation ({len(report.findings)} finding(s)); it is listed but not used as the latest.", "occurred_at": now, "exhibition_id": ex_id, "dataset_id": manifest["dataset_id"]})
        completeness = manifest["completeness"]
        edition["datasets"].append({
            "dataset_id": manifest["dataset_id"], "location": {"storage": "git", "locator": f"{locator_prefix}/{ex_id}/{manifest['edition_year']}/{manifest['dataset_id']}"},
            "created_at": manifest["created_at"], "data_origin": manifest["data_origin"], "schema_version": manifest["schema_version"], "content_hash": manifest["content_hash"],
            "record_counts": {k: manifest["record_counts"][k] for k in ("companies", "participations", "sources")}, "completeness_status": manifest["completeness_status"],
            "official_exhibitor_count": completeness["official_exhibitor_count"], "collected_participation_count": completeness["collected_participation_count"], "validation": validation,
        })
        runs_of.setdefault((ex_id, ed_id), []).extend(package.records["crawl_runs"])
        if report.ok:
            for run in package.records["crawl_runs"]:
                run_dataset[run["crawl_run_id"]] = max(manifest["dataset_id"], run_dataset.get(run["crawl_run_id"], ""))

    for run in extra_runs:
        key = (run["exhibition_id"], run["edition_id"])
        runs_of.setdefault(key, []).append(run)
        if key not in editions:
            year = int(run["edition_id"].split("-")[-1]) if run["edition_id"].split("-")[-1].isdigit() else int(run["edition_id"].split("-")[-2])
            editions[key] = {"edition_id": run["edition_id"], "year": year, "datasets": []}
        exhibitions.setdefault(run["exhibition_id"], {"exhibition_id": run["exhibition_id"], "name": assessments.get(run["exhibition_id"], {}).get("name", run["exhibition_id"]), "editions": []})

    for (ex_id, ed_id), edition in sorted(editions.items()):
        edition["datasets"].sort(key=lambda d: (d["created_at"], d["dataset_id"]))
        passed = [d for d in edition["datasets"] if d["validation"]["status"] == "passed"]
        latest = passed[-1]["dataset_id"] if passed else None
        edition["latest_dataset_id"] = latest
        method = assessments.get(ex_id, {}).get("method", "undetermined")
        run = _last_run(runs_of.get((ex_id, ed_id), []))
        if run is not None:
            stats = run["stats"]
            last: dict[str, Any] = {"method": method, "status": run["status"], "crawl_run_id": run["crawl_run_id"], "finished_at": run["finished_at"], "records_extracted": stats["records_extracted"], "error_count": stats["error_count"]}
            owner = run_dataset.get(run["crawl_run_id"])
            if run["status"] in ("succeeded", "partial") and owner:
                last["dataset_id"] = owner
            if run["status"] in ("failed", "cancelled") or run["status"] == "partial":
                samples = run.get("error_samples") or []
                reason = samples[0]["message"] if samples else (run.get("notes") or "no further detail was recorded")
                last["notes"] = f"{run['status']}: {reason}"[:4000]
            if run["status"] == "failed":
                notices.append({"level": "warning", "message": f"{ed_id}: the latest acquisition failed ({last['notes'][:300]})", "occurred_at": run["finished_at"], "exhibition_id": ex_id})
            edition["last_acquisition"] = last
        exhibitions[ex_id]["editions"].append(edition)
        for d in edition["datasets"]:
            if d["validation"]["status"] == "passed" and d["completeness_status"] != "complete":
                official = d["official_exhibitor_count"]
                detail = f"official {official}, collected {d['collected_participation_count']}" if official is not None else "no official count"
                notices.append({"level": "info", "message": f"{d['dataset_id']}: completeness is {d['completeness_status']} ({detail}).", "occurred_at": d["created_at"], "exhibition_id": ex_id, "dataset_id": d["dataset_id"]})

    for ex_id, entry in exhibitions.items():
        given = assessments.get(ex_id)
        entry["acquisition"] = {k: v for k, v in (given or {}).items() if k in ("method", "status", "assessed_at", "report_path", "notes") and v is not None} or {"method": "undetermined", "status": "not_assessed"}
        entry["acquisition"].setdefault("method", "undetermined")
    notices.sort(key=lambda n: (n["occurred_at"], n["message"]))
    return {
        "schema_version": schemas.version, "generated_at": now, "generator": dict(generator),
        "exhibitions": [exhibitions[k] for k in sorted(exhibitions)], "notices": notices,
    }


def validate_index(index: Mapping[str, Any], *, packages_root: str | Path | None = None, schemas: SchemaSet | None = None) -> list[str]:
    """Rules IR1-IR7 of the dataset index contract. Empty list = valid. (IR2, the schema version, is enforced by the Schema's `const` inside IR1.)"""
    schemas = schemas or SchemaSet()
    problems = [f"IR1 {m}" for m in schemas.errors("dataset_index", index)]
    if problems:
        return problems
    seen_ex, seen_ed, seen_ds = set(), set(), set()
    all_ds: dict[str, tuple[str, int, dict[str, Any]]] = {}
    for ex in index["exhibitions"]:
        if ex["exhibition_id"] in seen_ex:
            problems.append(f"IR3 duplicate exhibition_id {ex['exhibition_id']}")
        seen_ex.add(ex["exhibition_id"])
        for ed in ex["editions"]:
            if not ed["edition_id"].startswith(ex["exhibition_id"] + "-") or str(ed["year"]) not in ed["edition_id"]:
                problems.append(f"IR3 {ed['edition_id']} must start with '<exhibition_id>-' and contain its year")
            if ed["edition_id"] in seen_ed:
                problems.append(f"IR3 duplicate edition_id {ed['edition_id']}")
            seen_ed.add(ed["edition_id"])
            passed = sorted((d["created_at"], d["dataset_id"]) for d in ed["datasets"] if d["validation"]["status"] == "passed")
            expected = passed[-1][1] if passed else None
            if ed["latest_dataset_id"] != expected:
                problems.append(f"IR4 {ed['edition_id']}: latest_dataset_id is {ed['latest_dataset_id']!r}, expected {expected!r}")
            for d in ed["datasets"]:
                if not d["dataset_id"].startswith(ed["edition_id"] + "."):
                    problems.append(f"IR3 {d['dataset_id']} must start with '<edition_id>.'")
                if d["dataset_id"] in seen_ds:
                    problems.append(f"IR3 duplicate dataset_id {d['dataset_id']}")
                seen_ds.add(d["dataset_id"])
                all_ds[d["dataset_id"]] = (ex["exhibition_id"], ed["year"], d)
            last = ed.get("last_acquisition")
            if last and last.get("dataset_id") and last["dataset_id"] not in {d["dataset_id"] for d in ed["datasets"]}:
                problems.append(f"IR5 {ed['edition_id']}: last_acquisition.dataset_id {last['dataset_id']} is not in datasets")
    if packages_root is not None:
        root = Path(packages_root)
        for dataset_id, (ex_id, year, d) in sorted(all_ds.items()):
            if d["location"]["storage"] != "git":
                continue
            directory = root / ex_id / str(year) / dataset_id
            try:
                manifest = read_package(directory).manifest
            except (PackageError, OSError, ValueError) as exc:
                problems.append(f"IR6 {dataset_id}: package cannot be read ({exc})")
                continue
            comp = manifest["completeness"]
            summary = {"created_at": manifest["created_at"], "data_origin": manifest["data_origin"], "schema_version": manifest["schema_version"], "content_hash": manifest["content_hash"],
                       "completeness_status": manifest["completeness_status"], "official_exhibitor_count": comp["official_exhibitor_count"], "collected_participation_count": comp["collected_participation_count"]}
            for key, value in summary.items():
                if d[key] != value:
                    problems.append(f"IR6 {dataset_id}: {key} differs from the manifest")
            if d["record_counts"] != {k: manifest["record_counts"][k] for k in ("companies", "participations", "sources")}:
                problems.append(f"IR6 {dataset_id}: record_counts differ from the manifest")
            if d["validation"]["status"] == "passed" and not validate_package(directory, schema_dir=schemas.directory).ok:
                problems.append(f"IR6 {dataset_id}: marked passed but the package fails R1-R11")
    for notice in index["notices"]:
        if notice.get("exhibition_id") and notice["exhibition_id"] not in seen_ex:
            problems.append(f"IR7 notice refers to unknown exhibition {notice['exhibition_id']}")
        if notice.get("dataset_id") and notice["dataset_id"] not in seen_ds:
            problems.append(f"IR7 notice refers to unknown dataset {notice['dataset_id']}")
    return problems


def write_index(index: Mapping[str, Any], path: str | Path, *, packages_root: str | Path | None = None, schemas: SchemaSet | None = None) -> None:
    """Validate (IR1-IR7) and write atomically; an invalid index is never written."""
    problems = validate_index(index, packages_root=packages_root, schemas=schemas)
    if problems:
        raise ValueError("the dataset index is invalid; nothing was written:\n" + "\n".join(problems[:20]))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(index, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
