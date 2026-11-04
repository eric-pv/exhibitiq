"""Cross-exhibition, cross-year participation history (D2-08).

Reads every edition's **latest valid** data package under a packages root and answers, for each company: which
editions (of which exhibitions) is it, or was it, a participant in? Because ``company_id`` is stable across packages
(``etl.registry``), the same company's participations line up across years and across exhibitions.

- Only packages that pass the validator (R1-R11) are used; the others are reported in ``skipped`` with the reason,
  never silently ignored.
- "Latest" is the greatest ``dataset_id`` of an edition (the id ends in a UTC timestamp). Older packages of the
  same edition are superseded, not merged.
- ``data_origin`` is carried on every entry so synthetic test data can never be mistaken for collected data.
- Companies a person marked ``merged`` are followed to the surviving ``company_id`` (``canonical_company_id``), with
  a guard against cycles; the original ID is kept.
- Facts are copied, not interpreted: names, booth and hall are as the package says.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etl.package import PackageError, read_package
from etl.validate import validate_package

HISTORY_VERSION = 1


@dataclass
class History:
    companies: dict[str, dict[str, Any]] = field(default_factory=dict)
    packages: list[str] = field(default_factory=list)  # dataset_ids used
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": HISTORY_VERSION,
            "datasets": sorted(self.packages),
            "companies": {cid: self.companies[cid] for cid in sorted(self.companies, key=lambda k: k.encode())},
            "skipped": sorted(self.skipped, key=lambda s: (s["path"], s["reason"])),
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=1) + "\n"

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(self.dumps())
            os.replace(temp, target)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise


def latest_package_dirs(root: str | Path) -> list[Path]:
    """For each ``<exhibition>/<year>`` directory, the package directory with the greatest dataset_id."""
    found: list[Path] = []
    base = Path(root)
    if not base.is_dir():
        return found
    for exhibition in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for year in sorted(p for p in exhibition.iterdir() if p.is_dir() and not p.name.startswith(".")):
            candidates = sorted((p for p in year.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name)
            if candidates:
                found.append(candidates[-1])
    return found


def _canonical(company_id: str, merged_into: Mapping[str, str]) -> str:
    seen = {company_id}
    current = company_id
    while current in merged_into:
        current = merged_into[current]
        if current in seen:  # a cycle: stop at the entry we started from rather than loop
            return company_id
        seen.add(current)
    return current


def build_history(package_dirs: Iterable[str | Path]) -> History:
    history = History()
    for directory in (Path(d) for d in package_dirs):
        try:
            report = validate_package(directory)
            if not report.ok:
                history.skipped.append({"path": directory.as_posix(), "reason": f"fails validation ({len(report.findings)} finding(s), first: {report.findings[0]})"})
                continue
            package = read_package(directory)
        except (PackageError, OSError, ValueError) as exc:
            history.skipped.append({"path": directory.as_posix(), "reason": f"cannot be read: {exc}"})
            continue
        manifest = package.manifest
        history.packages.append(manifest["dataset_id"])
        merged_into = {c["company_id"]: c["merged_into"] for c in package.records["companies"] if c.get("status") == "merged" and c.get("merged_into")}
        names = {c["company_id"]: c["name"] for c in package.records["companies"]}
        for part in package.records["participations"]:
            cid = part["company_id"]
            entry = history.companies.setdefault(cid, {"name": names.get(cid, part["exhibitor_name_as_listed"]), "participations": []})
            record = {
                "exhibition_id": manifest["exhibition_id"], "edition_id": manifest["edition_id"], "edition_year": manifest["edition_year"],
                "dataset_id": manifest["dataset_id"], "data_origin": manifest["data_origin"], "participation_id": part["participation_id"],
                "listing_status": part["listing_status"], "exhibitor_name_as_listed": part["exhibitor_name_as_listed"],
            }
            for optional in ("booth", "hall"):
                if part.get(optional):
                    record[optional] = part[optional]
            canonical = _canonical(cid, merged_into)
            if canonical != cid:
                record["canonical_company_id"] = canonical
            entry["participations"].append(record)
    for entry in history.companies.values():
        entry["participations"].sort(key=lambda r: (r["edition_year"], r["exhibition_id"], r["edition_id"]))
    return history
