"""Enrich an existing package with what exhibitors' own websites say (D2-02 enrichment; Issue #114 item 1A).

    python -m etl.enrich --package data/packages/<ex>/<year>/<dataset_id> --targets TARGETS.json
                         [--raw data/raw] [--packages data/packages] [--created-at 2026-11-12T08:00:00Z] [--notes TEXT]

``TARGETS.json`` (exhibition-specific data, kept in ``data/sources/``)::

    {"identified": "how the websites were identified (for example: web search on 2026-11-12)",
     "news_keywords": ["training", "simulat", "drone", ...], "news_months": 12,
     "targets": [{"exhibitor_name_as_listed": "...", "homepage": "https://...", "allowed_domains": ["..."]}],
     "not_found": [{"exhibitor_name_as_listed": "...", "reason": "..."}]}

For each target the ``company-site`` adapter reads the homepage (and the RSS/Atom feeds it links to) through the normal
runner (robots.txt, rate limit, allowed domains) and ``crawler.store`` keeps every response as evidence. A **new**
package is then assembled from the previous one (which is not changed):

- ``company.website`` (if absent): the page's canonical URL, else the address that answered; ``company.description``
  (if absent): the site's own description. Both cite the homepage source in ``field_sources``.
- Explicit distribution statements (``authorized distributor`` ...) are copied into the participation ``notes`` with
  their page; exhibitors of the same package named in a statement are noted. Nothing is recorded when none is stated.
- Feed items from the last ``news_months`` months whose title or link contains a keyword become ``press_release``
  source records (title, link and date as the feed gives them; the snapshot is the feed) and are cited by the company.
- Sites that cannot be read and targets without a known website are written to the company ``notes`` with the reason,
  and their crawl runs are kept, so the failure is visible.
- Every record keeps ``verification_status: unverified``: the website was identified outside the exhibitor list.

Exit codes: 0 package written, 1 the package could not be assembled, 2 bad input.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from crawler.company_site import ADAPTER_NAME, CompanySiteAdapter
from crawler.fetch import Fetcher, UrllibFetcher
from crawler.runner import RunOptions, run_source
from crawler.source_config import ConfigError, parse_source_config
from crawler.store import RunStore, verify_run
from etl.assemble import AssembleError, OfficialCount, assemble_package, dataset_id_for, load_run
from etl.changes import diff_records
from etl.ids import make_id
from etl.normalize import name_keys
from etl.package import read_package

PRODUCER = {"name": "exhibitiq-etl-enrich", "version": "1.0.0"}
MAX_TEXT = 4000


class EnrichError(ValueError):
    """The targets file or the package cannot be used."""


@dataclass
class TargetRun:
    target: dict[str, Any]
    run_dir: Path
    status: str
    sources: list[dict[str, Any]]
    crawl_run: dict[str, Any]
    records: list[tuple[str, dict[str, Any]]] = field(default_factory=list)  # (source_id, record)
    errors: list[str] = field(default_factory=list)


def load_targets(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EnrichError(f"cannot read {path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("targets"), list) or not isinstance(data.get("identified"), str) or not data["identified"].strip():
        raise EnrichError(f"{path}: needs 'identified' (text) and 'targets' (list)")
    keywords = data.get("news_keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) and k for k in keywords):
        raise EnrichError(f"{path}: news_keywords must be a list of words")
    months = data.get("news_months", 12)
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 120:
        raise EnrichError(f"{path}: news_months must be an integer from 1 to 120")
    names = []
    for i, target in enumerate(data["targets"]):
        if not isinstance(target, dict) or not all(isinstance(target.get(k), str) and target[k] for k in ("exhibitor_name_as_listed", "homepage")) \
                or not isinstance(target.get("allowed_domains"), list) or not target["allowed_domains"]:
            raise EnrichError(f"{path}: targets[{i}] needs exhibitor_name_as_listed, homepage and allowed_domains")
        names.append(target["exhibitor_name_as_listed"])
    for i, missing in enumerate(data.get("not_found", [])):
        if not isinstance(missing, dict) or not all(isinstance(missing.get(k), str) and missing[k] for k in ("exhibitor_name_as_listed", "reason")):
            raise EnrichError(f"{path}: not_found[{i}] needs exhibitor_name_as_listed and reason")
        names.append(missing["exhibitor_name_as_listed"])
    if len(set(names)) != len(names):
        raise EnrichError(f"{path}: an exhibitor is listed twice")
    return data


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "site"


def acquire(targets: Mapping[str, Any], *, exhibition_id: str, edition_id: str, raw_root: str, fetcher: Fetcher,
            clock: Any = None, rand: Callable[[int], bytes] | None = None) -> list[TargetRun]:
    """Read each target's site with the company-site adapter; evidence goes to ``raw_root`` (``crawler.store``)."""
    runs: list[TargetRun] = []
    adapter = CompanySiteAdapter()
    for target in targets["targets"]:
        try:
            config = parse_source_config({
                "name": f"{edition_id}-{_slug(target['exhibitor_name_as_listed'])}-site", "exhibition_id": exhibition_id, "edition_id": edition_id,
                "source_type": "exhibitor_website", "start_urls": [target["homepage"]], "allowed_domains": target["allowed_domains"],
                "rate_limit_per_second": 0.5, "max_retries": 1, "adapter": ADAPTER_NAME,
            })
        except ConfigError as exc:
            raise EnrichError(f"{target['exhibitor_name_as_listed']}: {exc}") from None
        store = RunStore(raw_root, config, root_label=raw_root.rstrip("/"))
        kwargs: dict[str, Any] = {"clock": clock, "options": RunOptions(max_requests=6), "sink": store}
        if rand is not None:
            kwargs["rand"] = rand
        result = run_source(config, adapter, fetcher, **kwargs)
        run_dir = store.finalize(result)
        problems = verify_run(run_dir)
        if problems:
            raise EnrichError(f"{run_dir}: evidence does not verify: {problems}")
        sources, crawl_run = load_run(run_dir)
        runs.append(TargetRun(target, run_dir, result.status, sources, crawl_run,
                              [(r.source_id, dict(r.data)) for r in result.records], [f"{e.code}: {e.message}" for e in result.errors]))
    return runs


def _note(existing: str | None, addition: str) -> str:
    return (f"{existing} | {addition}" if existing else addition)[:MAX_TEXT]


def _keyword_match(record: Mapping[str, Any], keywords: Sequence[str]) -> bool:
    haystack = f"{record.get('title', '')} {record.get('url', '')}".lower()
    return not keywords or any(k.lower() in haystack for k in keywords)


def build_enriched(previous_dir: Path, runs: Sequence[TargetRun], targets: Mapping[str, Any], *, created_at: datetime,
                   rand: Callable[[int], bytes] | None = None) -> dict[str, Any]:
    """Records of the new package (``assemble_package`` keyword arguments without output_root/producer)."""
    previous = read_package(previous_dir)
    records = copy.deepcopy(previous.records)
    companies = {c["company_id"]: c for c in records["companies"]}
    by_name: dict[str, dict[str, Any]] = {}
    for part in records["participations"]:
        by_name.setdefault(part["exhibitor_name_as_listed"], part)
    keys = {}
    for name in by_name:
        try:
            keys[name_keys(name).exact] = name
        except ValueError:
            continue
    day = created_at.astimezone(timezone.utc).date()
    since = (day - timedelta(days=round(30.4 * targets.get("news_months", 12))))
    keywords = targets.get("news_keywords", [])
    identified = targets["identified"].strip()
    sources = list(records["sources"])
    crawl_runs = list(records["crawl_runs"])
    id_kwargs = {"rand": rand} if rand is not None else {}
    summary: list[dict[str, Any]] = []

    def find(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        part = by_name.get(name)
        if part is None:
            raise EnrichError(f"{name!r} is not an exhibitor of {previous.manifest['dataset_id']}")
        return part, companies[part["company_id"]]

    for missing in targets.get("not_found", []):
        part, company = find(missing["exhibitor_name_as_listed"])
        company["notes"] = _note(company.get("notes"), f"No official website identified ({identified}): {missing['reason']}")
        summary.append({"exhibitor": missing["exhibitor_name_as_listed"], "result": "website not found"})

    for run in runs:
        name = run.target["exhibitor_name_as_listed"]
        part, company = find(name)
        sources.extend(run.sources)
        crawl_runs.append(run.crawl_run)
        source_by_id = {s["source_id"]: s for s in run.sources}
        profiles = [(sid, r) for sid, r in run.records if r.get("record_type") == "profile"]
        news = [(sid, r) for sid, r in run.records if r.get("record_type") == "news"]
        entry: dict[str, Any] = {"exhibitor": name, "crawl_status": run.status, "description": False, "website": False, "news": 0, "distribution_statements": 0}
        if not profiles:
            reason = "; ".join(run.errors) or "no page could be read"
            company["notes"] = _note(company.get("notes"), f"Website {run.target['homepage']} could not be read on {day.isoformat()} ({identified}): {reason[:300]}")
            entry["result"] = "site not readable"
            summary.append(entry)
            continue
        sid, profile = profiles[0]
        field_sources = company.setdefault("field_sources", {})
        if not company.get("website"):
            company["website"] = profile.get("canonical_url") or profile["page_url"]
            field_sources["website"] = [sid]
            entry["website"] = True
        if profile.get("description") and not company.get("description"):
            company["description"] = profile["description"][:MAX_TEXT]
            field_sources["description"] = [sid]
            entry["description"] = True
        if not field_sources:
            company.pop("field_sources")
        company["source_ids"] = sorted(set(company["source_ids"]) | {sid})
        company["notes"] = _note(company.get("notes"), f"Website identified outside the exhibitor list ({identified}); description as the site states it (meta description of {profile['page_url']}).")
        for statement in profile.get("distribution_statements", []):
            named = sorted({keys[k] for k in keys if k and len(k) > 3 and k in name_keys(statement).exact and keys[k] != name}) if any(c.isalnum() for c in statement) else []
            text = f"Distribution statement on {profile['page_url']}: \"{statement}\""
            if named:
                text += f" (names exhibitors of this list: {', '.join(named)})"
            part["notes"] = _note(part.get("notes"), text)
            part["source_ids"] = sorted(set(part["source_ids"]) | {sid})
            entry["distribution_statements"] += 1
        seen_urls: set[str] = set()
        for feed_sid, item in news:
            published = item.get("published")
            if not published or date.fromisoformat(published) < since or not _keyword_match(item, keywords) or item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            feed = source_by_id[feed_sid]
            news_source = {
                "source_id": make_id("src", **id_kwargs), "source_type": "press_release", "url": item["url"], "title": item["title"][:500],
                "retrieved_at": feed["retrieved_at"], "content_sha256": feed["content_sha256"], "snapshot": dict(feed["snapshot"]),
                "crawl_run_id": feed["crawl_run_id"],
                "notes": f"Item of the site's feed {item['feed_url']} published {published}; title, link and date as the feed gives them. The article itself was not fetched; the snapshot is the feed.",
            }
            if feed.get("media_type"):
                news_source["media_type"] = feed["media_type"]
            if profile.get("site_name"):
                news_source["publisher"] = profile["site_name"][:500]
            sources.append(news_source)
            company["source_ids"] = sorted(set(company["source_ids"]) | {news_source["source_id"]})
            entry["news"] += 1
        entry["result"] = "enriched"
        summary.append(entry)

    sources.sort(key=lambda s: s["source_id"].encode())
    crawl_runs.sort(key=lambda r: r["crawl_run_id"].encode())
    new_companies = sorted(companies.values(), key=lambda c: c["company_id"].encode())
    dataset_id = dataset_id_for(previous.manifest["edition_id"], created_at)
    changes = diff_records(previous.records, {"companies": new_companies, "participations": records["participations"]},
                           dataset_id=dataset_id, previous_dataset_id=previous.manifest["dataset_id"],
                           detected_at=created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **id_kwargs)
    completeness = previous.manifest["completeness"]
    official = None
    if completeness.get("official_exhibitor_count") is not None:
        as_of = completeness.get("official_count_as_of")
        official = OfficialCount(completeness["official_exhibitor_count"], completeness["official_count_source_id"], date.fromisoformat(as_of) if as_of else None)
    return {
        "exhibition": previous.exhibition, "edition": previous.edition, "companies": new_companies, "participations": records["participations"],
        "sources": sources, "crawl_runs": crawl_runs, "changes": changes, "data_origin": previous.manifest["data_origin"],
        "previous_dataset_id": previous.manifest["dataset_id"], "official_count": official, "created_at": created_at, "summary": summary,
    }


def _utc(text: str) -> datetime:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError("use the form 2026-11-12T08:00:00Z") from None


def main(argv: Sequence[str] | None = None, *, fetcher: Fetcher | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m etl.enrich", description="Enrich a package with exhibitors' own websites (new package version).")
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--packages", default="data/packages", type=Path)
    parser.add_argument("--created-at", type=_utc)
    parser.add_argument("--notes")
    args = parser.parse_args(argv)
    try:
        targets = load_targets(args.targets)
        previous = read_package(args.package)
        runs = acquire(targets, exhibition_id=previous.manifest["exhibition_id"], edition_id=previous.manifest["edition_id"],
                       raw_root=args.raw, fetcher=fetcher or UrllibFetcher())
        created_at = args.created_at or datetime.now(timezone.utc).replace(microsecond=0)
        built = build_enriched(args.package, runs, targets, created_at=created_at)
    except (EnrichError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = built.pop("summary")
    try:
        package = assemble_package(args.packages, producer=PRODUCER, notes=args.notes, **built)
    except AssembleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for finding in exc.findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print(json.dumps({"package": Path(package.path).as_posix(), "dataset_id": package.manifest["dataset_id"],
                      "previous_dataset_id": package.manifest["previous_dataset_id"], "changes": len(built["changes"]), "targets": summary},
                     ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
