"""Search across data packages, an edition's package timeline, and a diff between two packages (D3-04).

Read-only tools over ``data/packages/<exhibition>/<year>/<dataset_id>/``. They never write or change a package.

- ``search_companies``: find companies by name, Traditional Chinese name, alias, website host or ``company_id`` in the
  latest **valid** package of each edition (or in the package directories given), with their participations.
  Matching uses ``etl.normalize.name_keys`` (the same keys the company registry uses), so case, width, punctuation
  and trailing legal forms do not matter. Results are facts copied from the packages; nothing is scored or inferred.
- ``edition_timeline``: every package of one edition, oldest first, with validation status, record counts,
  completeness and the change counts recorded in ``changes.jsonl``; ``previous_dataset_id`` links are checked and any
  break in the chain is reported as a notice, not repaired.
- ``diff_packages``: recompute what changed between any two valid packages of the same edition with
  ``etl.changes.diff_records`` (literal field comparison). When the newer package names the older one as
  ``previous_dataset_id``, the result also lists where the recomputed changes and the recorded ``changes.jsonl``
  disagree (by entity and change type).

Packages that fail validation (R1-R11) or cannot be read are listed in ``skipped`` with the reason; they are never
used silently. ``data_origin`` is carried on every result so synthetic data is never mistaken for collected data.

Command line (JSON on stdout; exit 0 = done, 2 = bad input)::

    python -m etl.catalog search  [--packages data/packages] [QUERY] [--country ZZ] [--exhibition ID] [--year 2026] [--status listed]
    python -m etl.catalog timeline [--packages data/packages] EXHIBITION_ID YEAR
    python -m etl.catalog diff OLDER_PACKAGE_DIR NEWER_PACKAGE_DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from etl.changes import diff_records
from etl.history import latest_package_dirs
from etl.normalize import name_keys
from etl.package import Package, PackageError, read_package
from etl.validate import validate_package

CATALOG_VERSION = 1
CHANGE_TYPES = ("added", "modified", "removed")
# A fixed id source for recomputed changes: change_id/detected_at are dropped from the output, so they only need to be valid.
_ZERO_RAND = (lambda n: bytes(n))  # noqa: E731


class CatalogError(ValueError):
    """The request cannot be answered from the given packages (bad input, not a data problem)."""


def _skip(path: Path, report_or_exc: Any) -> dict[str, str]:
    if isinstance(report_or_exc, Exception):
        return {"path": path.as_posix(), "reason": f"cannot be read: {report_or_exc}"}
    return {"path": path.as_posix(), "reason": f"fails validation ({len(report_or_exc.findings)} finding(s), first: {report_or_exc.findings[0]})"}


def _load_valid(directory: Path) -> tuple[Package | None, dict[str, str] | None]:
    try:
        report = validate_package(directory)
        if not report.ok:
            return None, _skip(directory, report)
        return read_package(directory), None
    except (PackageError, OSError, ValueError) as exc:
        return None, _skip(directory, exc)


# ----------------------------------------------------------------------------- search


def _keys(text: str) -> tuple[str, str] | None:
    try:
        keys = name_keys(text)
    except ValueError:
        return None
    return keys.exact, keys.loose


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _candidates(company: dict[str, Any]) -> list[tuple[str, str]]:
    out = [("name", company["name"])]
    if company.get("name_zh_hant"):
        out.append(("name_zh_hant", company["name_zh_hant"]))
    out.extend(("alias", alias["name"]) for alias in company.get("aliases", []))
    return out


def _match(company: dict[str, Any], query: str | None) -> list[dict[str, str]]:
    """How ``company`` matches ``query`` (empty list = no match). No query matches every company."""
    if query is None:
        return [{"field": "*", "value": ""}]
    text = query.strip()
    if text == company["company_id"]:
        return [{"field": "company_id", "value": text}]
    found: list[dict[str, str]] = []
    wanted = _keys(text)
    if wanted is not None:
        exact, loose = wanted
        for field, value in _candidates(company):
            keys = _keys(value)
            if keys is not None and (exact in keys[0] or loose == keys[1]):
                found.append({"field": field, "value": value})
    host = text.lower().removeprefix("www.")
    if "." in host:
        hosts = {("website", company["website"])} if company.get("website") else set()
        hosts |= {("domains", d) for d in company.get("domains", [])}
        for field, value in sorted(hosts):
            if host == _host(value if field == "website" else f"https://{value}"):
                found.append({"field": field, "value": value})
    return found


def search_companies(
    packages: str | Path | Iterable[str | Path],
    query: str | None = None,
    *,
    country: str | None = None,
    exhibition_id: str | None = None,
    year: int | None = None,
    listing_status: str | None = None,
) -> dict[str, Any]:
    """``packages`` is a packages root (latest package of each edition is used) or an iterable of package directories."""
    if query is not None and not query.strip():
        raise CatalogError("query is empty")
    dirs = latest_package_dirs(packages) if isinstance(packages, (str, Path)) else [Path(p) for p in packages]
    skipped: list[dict[str, str]] = []
    used: list[str] = []
    results: dict[str, dict[str, Any]] = {}
    for directory in dirs:
        package, skip = _load_valid(directory)
        if package is None:
            skipped.append(skip)
            continue
        manifest = package.manifest
        if exhibition_id is not None and manifest["exhibition_id"] != exhibition_id:
            continue
        if year is not None and manifest["edition_year"] != year:
            continue
        used.append(manifest["dataset_id"])
        companies = {c["company_id"]: c for c in package.records["companies"]}
        for part in package.records["participations"]:
            if listing_status is not None and part["listing_status"] != listing_status:
                continue
            company = companies.get(part["company_id"])
            if company is None or (country is not None and company.get("country") != country):
                continue
            matched = _match(company, query)
            if not matched:
                continue
            entry = results.setdefault(company["company_id"], {"company_id": company["company_id"], "name": company["name"], "matched_on": [], "participations": []})
            for key in ("country", "website", "status", "merged_into"):
                if company.get(key) and key not in entry:
                    entry[key] = company[key]
            for item in matched:
                if item not in entry["matched_on"]:
                    entry["matched_on"].append(item)
            record = {
                "exhibition_id": manifest["exhibition_id"], "edition_id": manifest["edition_id"], "edition_year": manifest["edition_year"],
                "dataset_id": manifest["dataset_id"], "data_origin": manifest["data_origin"], "participation_id": part["participation_id"],
                "listing_status": part["listing_status"], "exhibitor_name_as_listed": part["exhibitor_name_as_listed"], "source_ids": list(part["source_ids"]),
            }
            for optional in ("booth", "hall"):
                if part.get(optional):
                    record[optional] = part[optional]
            entry["participations"].append(record)
    hits = []
    for entry in results.values():
        entry["matched_on"].sort(key=lambda m: (m["field"], m["value"]))
        entry["participations"].sort(key=lambda r: (r["edition_year"], r["exhibition_id"], r["edition_id"], r["participation_id"]))
        hits.append(entry)
    hits.sort(key=lambda e: (e["name"].casefold(), e["company_id"]))
    return {
        "version": CATALOG_VERSION, "kind": "search",
        "query": {"text": query, "country": country, "exhibition_id": exhibition_id, "year": year, "listing_status": listing_status},
        "datasets": sorted(used), "results": hits, "skipped": sorted(skipped, key=lambda s: (s["path"], s["reason"])),
    }


# --------------------------------------------------------------------------- timeline


def _change_counts(changes: Sequence[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = {"company": Counter(), "participation": Counter()}
    for change in changes:
        counts.setdefault(change["entity_type"], Counter())[change["change_type"]] += 1
    return {entity: {t: counter.get(t, 0) for t in CHANGE_TYPES} for entity, counter in sorted(counts.items())}


def edition_timeline(packages_root: str | Path, exhibition_id: str, year: int) -> dict[str, Any]:
    """Every package of ``<packages_root>/<exhibition_id>/<year>/``, oldest first, and notices about the chain."""
    edition_dir = Path(packages_root) / exhibition_id / str(year)
    if not edition_dir.is_dir():
        raise CatalogError(f"no packages for {exhibition_id} {year}: {edition_dir} is not a directory")
    entries: list[dict[str, Any]] = []
    notices: list[str] = []
    for directory in sorted((p for p in edition_dir.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.encode()):
        package, skip = _load_valid(directory)
        if package is None:  # nothing is read from a package that fails validation
            entries.append({"dataset_id": directory.name, "path": directory.as_posix(), "validation": "failed", "reason": skip["reason"]})
            notices.append(f"{directory.name}: {skip['reason']}; not used in the history")
            continue
        m = package.manifest
        entries.append({
            "dataset_id": m["dataset_id"], "path": directory.as_posix(), "created_at": m["created_at"], "data_origin": m["data_origin"],
            "previous_dataset_id": m["previous_dataset_id"], "validation": "passed", "record_counts": dict(m["record_counts"]),
            "completeness_status": m["completeness_status"], "official_exhibitor_count": m["completeness"]["official_exhibitor_count"],
            "collected_participation_count": m["completeness"]["collected_participation_count"], "recorded_changes": _change_counts(package.records["changes"]),
        })
        if m["dataset_id"] != directory.name:
            notices.append(f"{directory.name}: directory name differs from manifest dataset_id {m['dataset_id']}")

    known = [e for e in entries if e["validation"] == "passed"]
    by_id = {e["dataset_id"]: e for e in known}
    for position, entry in enumerate(known):
        prev = entry["previous_dataset_id"]
        if prev is None:
            if position > 0:
                notices.append(f"{entry['dataset_id']}: previous_dataset_id is null although older packages exist; the history restarts here")
        elif prev not in by_id:
            reason = "fails validation" if prev in {e["dataset_id"] for e in entries} else "is not a package of this edition"
            notices.append(f"{entry['dataset_id']}: previous_dataset_id {prev} {reason}")
        elif prev.encode() >= entry["dataset_id"].encode():
            notices.append(f"{entry['dataset_id']}: previous_dataset_id {prev} is not older")
        elif position > 0 and prev != known[position - 1]["dataset_id"]:
            notices.append(f"{entry['dataset_id']}: previous_dataset_id {prev} skips {known[position - 1]['dataset_id']}")
    passed = [e["dataset_id"] for e in known]
    return {
        "version": CATALOG_VERSION, "kind": "timeline", "exhibition_id": exhibition_id, "edition_year": year,
        "latest_valid_dataset_id": max(passed, key=lambda d: by_id[d]["created_at"]) if passed else None,
        "packages": entries, "notices": notices,
    }


# ------------------------------------------------------------------------------- diff


def _strip(change: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in change.items() if k not in {"change_id", "detected_at", "dataset_id", "previous_dataset_id"}}


def diff_packages(older: str | Path, newer: str | Path) -> dict[str, Any]:
    """Changes from ``older`` to ``newer`` (two valid packages of the same edition, ``older`` created first)."""
    loaded = []
    for directory in (Path(older), Path(newer)):
        package, skip = _load_valid(directory)
        if package is None:
            raise CatalogError(f"{skip['path']}: {skip['reason']}")
        loaded.append(package)
    a, b = loaded
    ma, mb = a.manifest, b.manifest
    if ma["edition_id"] != mb["edition_id"]:
        raise CatalogError(f"packages are of different editions: {ma['edition_id']} and {mb['edition_id']}")
    if ma["dataset_id"] == mb["dataset_id"]:
        raise CatalogError(f"both arguments are the same package: {ma['dataset_id']}")
    if (ma["created_at"], ma["dataset_id"].encode()) > (mb["created_at"], mb["dataset_id"].encode()):
        raise CatalogError(f"{ma['dataset_id']} is newer than {mb['dataset_id']}; give the older package first")
    sets = ("companies", "participations")
    found = diff_records({s: a.records[s] for s in sets}, {s: b.records[s] for s in sets},
                         dataset_id=mb["dataset_id"], previous_dataset_id=ma["dataset_id"], detected_at=mb["created_at"], rand=_ZERO_RAND, now_ms=0)
    changes = sorted((_strip(c) for c in found), key=lambda c: (c["entity_type"], c["entity_id"].encode(), c["change_type"]))
    result: dict[str, Any] = {
        "version": CATALOG_VERSION, "kind": "diff", "edition_id": mb["edition_id"],
        "older": {"dataset_id": ma["dataset_id"], "created_at": ma["created_at"], "data_origin": ma["data_origin"]},
        "newer": {"dataset_id": mb["dataset_id"], "created_at": mb["created_at"], "data_origin": mb["data_origin"]},
        "summary": _change_counts(changes), "changes": changes,
    }
    if mb["previous_dataset_id"] == ma["dataset_id"]:
        recomputed = {(c["entity_type"], c["entity_id"], c["change_type"]) for c in changes}
        recorded = {(c["entity_type"], c["entity_id"], c["change_type"]) for c in b.records["changes"]}
        as_list = lambda keys: [{"entity_type": t, "entity_id": i, "change_type": c} for t, i, c in sorted(keys)]  # noqa: E731
        result["recorded_comparison"] = {"only_recomputed": as_list(recomputed - recorded), "only_recorded": as_list(recorded - recomputed)}
    return result


# -------------------------------------------------------------------------------- CLI


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.catalog", description="Search, timeline and diff over data packages (read-only).")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="find companies in the latest valid package of each edition")
    search.add_argument("query", nargs="?")
    search.add_argument("--packages", default="data/packages")
    search.add_argument("--country")
    search.add_argument("--exhibition")
    search.add_argument("--year", type=int)
    search.add_argument("--status", choices=["listed", "removed"])
    timeline = sub.add_parser("timeline", help="every package of one edition, oldest first")
    timeline.add_argument("exhibition_id")
    timeline.add_argument("year", type=int)
    timeline.add_argument("--packages", default="data/packages")
    diff = sub.add_parser("diff", help="changes between two packages of the same edition")
    diff.add_argument("older")
    diff.add_argument("newer")
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            out = search_companies(args.packages, args.query, country=args.country, exhibition_id=args.exhibition, year=args.year, listing_status=args.status)
        elif args.command == "timeline":
            out = edition_timeline(args.packages, args.exhibition_id, args.year)
        else:
            out = diff_packages(args.older, args.newer)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
