"""Command line: one file from a source -> evidence -> records -> quality gate -> data package (D2-02).

    python -m etl.import_file --config SOURCE.toml --file LOCAL_FILE --info PACKAGE_INFO.json
                              [--origin URL] [--raw data/raw] [--packages data/packages]
                              [--registry data/registry/companies.json] [--official-count N --official-as-of YYYY-MM-DD]
                              [--data-origin collected] [--created-at 2026-11-09T08:00:00Z] [--accept Q3 ...] [--notes TEXT]

Generic: everything about a particular exhibition is in the source config (adapter and its options) and the
package info file. Steps, each the existing module's own behaviour:

1. ``crawler.file_import.import_files`` with the source's adapter; ``crawler.store.RunStore`` keeps the file as an
   immutable snapshot (``--raw``) and ``verify_run`` checks it. The evidence is kept even if a later step stops.
2. ``etl.build_records`` with the company registry (``--registry``; created when absent).
3. When the edition already has a valid package: ``etl.changes.carry_forward`` and ``diff_records``.
4. ``etl.quality.check_acquisition``; a blocking finding stops here (exit 1) unless a person passes ``--accept``.
5. ``etl.assemble.assemble_package`` (validates R1-R11 before publishing); the registry is saved only after that.

``--info`` is ``{"exhibition": {...}, "edition": {...}}`` with the fields to record (for example ``name``,
``start_date``, ``city``). Every value must be stated by the imported file itself: the records cite that file as their
only source (``source_ids``) and are marked ``unverified``. ``--official-count`` is the exhibitor count the file
states, with the same source.

Exit codes: 0 package written, 1 stopped by the quality gate or a failed acquisition (evidence kept, nothing published),
2 bad input.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import crawler.file_import  # noqa: F401  (registers the file-import adapter)
import crawler.printed_listing  # noqa: F401  (registers the printed-listing adapter)
from crawler.file_import import import_files
from crawler.source_config import ConfigError, load_source_config
from crawler.store import RunStore, StoreError, verify_run
from etl.assemble import AssembleError, OfficialCount, assemble_package, dataset_id_for, load_run
from etl.build_records import BuildError, RawListing, build_records
from etl.changes import carry_forward, diff_records
from etl.package import read_package
from etl.quality import CODES, blocked, check_acquisition
from etl.registry import CompanyRegistry, RegistryError
from etl.validate import validate_package

PRODUCER = {"name": "exhibitiq-etl-import-file", "version": "1.0.0"}
_RESERVED = {"source_ids", "verification_status", "field_sources", "exhibition_id", "edition_id"}


def _utc(text: str) -> datetime:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError("use the form 2026-11-09T08:00:00Z") from None


def _day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("use the form 2026-11-09") from None


def load_info(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from None
    if not isinstance(data, dict) or set(data) != {"exhibition", "edition"} or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError(f"{path}: expected {{\"exhibition\": {{...}}, \"edition\": {{...}}}}")
    for part in ("exhibition", "edition"):
        reserved = sorted(_RESERVED & set(data[part]))
        if reserved:
            raise ValueError(f"{path}: {part} must not set {', '.join(reserved)} (they come from the source config and the imported file)")
    if not isinstance(data["edition"].get("year"), int):
        raise ValueError(f"{path}: edition.year (integer) is required")
    return data["exhibition"], data["edition"]


def _log_warnings(log_text: str) -> list[str]:
    found = []
    for line in log_text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("level") == "WARNING":
            found.append(str(event.get("message", "")) + (f" ({event['warning']})" if event.get("warning") else ""))
    return found


def latest_valid_package(packages: Path, exhibition_id: str, year: int) -> Path | None:
    edition_dir = packages / exhibition_id / str(year)
    if not edition_dir.is_dir():
        return None
    candidates = sorted((p for p in edition_dir.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.encode(), reverse=True)
    return next((p for p in candidates if validate_package(p).ok), None)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.import_file", description="Import one file into a validated data package.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--info", required=True, type=Path)
    parser.add_argument("--origin", help="the URL the file was obtained from (default: the config's first start_url)")
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--packages", default="data/packages", type=Path)
    parser.add_argument("--registry", default="data/registry/companies.json", type=Path)
    parser.add_argument("--official-count", type=int)
    parser.add_argument("--official-as-of", type=_day)
    parser.add_argument("--data-origin", default="collected", choices=["collected", "synthetic"])
    parser.add_argument("--created-at", type=_utc)
    parser.add_argument("--accept", nargs="*", default=[], choices=list(CODES))
    parser.add_argument("--notes", help="how the file was obtained (written to manifest.notes)")
    args = parser.parse_args(argv)

    try:
        config = load_source_config(args.config)
        exhibition_info, edition_info = load_info(args.info)
        if not args.file.is_file():
            raise ValueError(f"{args.file} is not a file")
        origin = args.origin or config.start_urls[0]
        registry = CompanyRegistry.load(args.registry) if args.registry.is_file() else CompanyRegistry()
    except (ConfigError, RegistryError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    year = edition_info["year"]

    # 1. evidence first
    try:
        store = RunStore(args.raw, config, root_label=args.raw.rstrip("/"))
        result = import_files(config, {origin: args.file}, sink=store)
        run_dir = store.finalize(result)
    except (ConfigError, StoreError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    problems = verify_run(run_dir)
    if problems:
        print(f"error: the evidence directory {run_dir} does not verify: {problems}", file=sys.stderr)
        return 2
    sources, crawl_run = load_run(run_dir)
    summary: dict[str, Any] = {"run_dir": run_dir.as_posix(), "crawl_run_id": crawl_run["crawl_run_id"], "status": crawl_run["status"],
                               "records_extracted": crawl_run["stats"]["records_extracted"], "errors": [f"{e.code}: {e.message}" for e in result.errors],
                               "warnings": _log_warnings(result.log_text)}

    # 2. records
    source_id = sources[0]["source_id"]
    stamps = {s["source_id"]: s["retrieved_at"] for s in sources}
    try:
        built = build_records([RawListing(r.data, r.source_id) for r in result.records], edition_id=config.edition_id, retrieved_at=stamps, registry=registry)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    summary["build"] = built.report.summary()

    # 3. previous package of the edition
    previous_dir = latest_valid_package(args.packages, config.exhibition_id, year)
    companies, participations, all_sources, runs, changes = built.companies, built.participations, sources, [crawl_run], []
    previous_id = None
    previous_parts = None
    created_at = args.created_at or datetime.now(timezone.utc).replace(microsecond=0)
    if previous_dir is not None:
        previous = read_package(previous_dir)
        previous_id, previous_parts = previous.manifest["dataset_id"], previous.records["participations"]
        carried = carry_forward(previous.records, companies=companies, participations=participations, sources=sources, crawl_runs=[crawl_run])
        companies, participations, all_sources, runs = carried.companies, carried.participations, carried.sources, carried.crawl_runs
        detected = created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        changes = diff_records(previous.records, {"companies": companies, "participations": participations},
                               dataset_id=dataset_id_for(config.edition_id, created_at), previous_dataset_id=previous_id, detected_at=detected)
    summary["previous_dataset_id"] = previous_id

    # 4. quality gate
    findings = check_acquisition([crawl_run], participations, previous_participations=previous_parts, accept=args.accept)
    summary["quality"] = [f.to_dict() for f in findings]
    if blocked(findings):
        summary["published"] = False
        print(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True))
        print("stopped by the quality gate; the evidence is kept, nothing was published", file=sys.stderr)
        return 1

    # 5. package
    common = {"source_ids": [source_id], "verification_status": "unverified"}
    exhibition = {"exhibition_id": config.exhibition_id, **exhibition_info, **common}
    edition = {"edition_id": config.edition_id, "exhibition_id": config.exhibition_id, **edition_info, **common}
    official = None
    if args.official_count is not None:
        official = OfficialCount(args.official_count, source_id, args.official_as_of)
    try:
        package = assemble_package(args.packages, exhibition=exhibition, edition=edition, companies=companies, participations=participations,
                                   sources=all_sources, crawl_runs=runs, data_origin=args.data_origin, producer=PRODUCER, created_at=created_at,
                                   previous_dataset_id=previous_id, changes=changes, official_count=official, notes=args.notes)
    except AssembleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for finding in exc.findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    registry.save(args.registry)
    summary.update(published=True, package=Path(package.path).as_posix(), dataset_id=package.manifest["dataset_id"],
                   completeness_status=package.manifest["completeness_status"], completeness=package.manifest["completeness"])
    print(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
