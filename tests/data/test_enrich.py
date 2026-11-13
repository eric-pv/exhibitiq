"""Tests for etl.enrich: a new package version with what exhibitors' own websites state."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crawler.fetch import FetchError
from crawler.errors import ErrorCode
from crawler.models import Response
from etl.enrich import EnrichError, acquire, build_enriched, load_targets, main
from etl.package import read_package
from etl.validate import validate_package
from tests.data.crawl_testkit import FakeClock, FakeFetcher, fixed_rand
from tests.data.test_company_site import FEED, PAGE

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "data" / "samples" / "sample-fair" / "2026" / "sample-fair-2026.20261104T020000Z"
CREATED = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
HOME = "https://www.acme.example.com/"
TARGETS = {
    "identified": "test fixture",
    "news_keywords": ["vr", "simulat"], "news_months": 12,
    "targets": [
        {"exhibitor_name_as_listed": "SYNTHETIC OPTICS LTD", "homepage": HOME, "allowed_domains": ["acme.example.com"]},
        {"exhibitor_name_as_listed": "Test Harness Labs", "homepage": "https://down.example.org/", "allowed_domains": ["down.example.org"]},
        {"exhibitor_name_as_listed": "Sample Cyber Range LLC", "homepage": "https://cyber.example.net/", "allowed_domains": ["example.net"]},
    ],
    "not_found": [{"exhibitor_name_as_listed": "Sample Mobility Works", "reason": "no site found in the fixture"}],
}
SCRIPT = {
    HOME: Response(HOME, HOME, 200, {}, PAGE, "text/html"),
    "https://www.acme.example.com/feed/": Response("https://www.acme.example.com/feed/", "https://www.acme.example.com/feed/", 200, {}, FEED, "application/rss+xml"),
    "https://down.example.org/": FetchError(ErrorCode.NETWORK_ERROR, "connection refused", retryable=False),
    "https://cyber.example.net/": Response("https://cyber.example.net/", "https://cyber.example.net/home", 200, {},
                                           b'<html><head><meta name="description" content="Synthetic cyber ranges."></head><body>Hi</body></html>', "text/html"),
}


@pytest.fixture()
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    shutil.copytree(V2, tmp_path / "data" / "packages" / "sample-fair" / "2026" / V2.name)
    (tmp_path / "targets.json").write_text(json.dumps(TARGETS), encoding="utf-8")
    return tmp_path


def enrich(work: Path):
    fixed_rand.counter = 0
    runs = acquire(TARGETS, exhibition_id="sample-fair", edition_id="sample-fair-2026", raw_root="data/raw", fetcher=FakeFetcher(SCRIPT), clock=FakeClock(), rand=fixed_rand)
    return runs, build_enriched(work / "data" / "packages" / "sample-fair" / "2026" / V2.name, runs, TARGETS, created_at=CREATED, rand=fixed_rand)


def by_name(built, name):
    part = next(p for p in built["participations"] if p["exhibitor_name_as_listed"] == name)
    return part, next(c for c in built["companies"] if c["company_id"] == part["company_id"])


def test_profile_news_and_statements_are_recorded_with_sources(work: Path) -> None:
    runs, built = enrich(work)
    part, company = by_name(built, "SYNTHETIC OPTICS LTD")
    sources = {s["source_id"]: s for s in built["sources"]}
    original = by_name({"participations": read_package(V2).records["participations"], "companies": read_package(V2).records["companies"]}, "SYNTHETIC OPTICS LTD")[1]
    assert company["website"] == original["website"]  # an existing value is never replaced
    assert company["description"] == original["description"]
    news = [sources[s] for s in company["source_ids"] if sources[s]["source_type"] == "press_release"]
    assert [(n["title"], n["url"]) for n in news] == [("Acme launches VR trainer", "https://www.acme.example.com/news/vr")]  # old, off-topic and undated items dropped
    assert "published 2026-03-03" in news[0]["notes"] and news[0]["publisher"] == "Acme Training"
    feed_source = next(s for s in runs[0].sources if s["url"].endswith("/feed/"))
    assert news[0]["content_sha256"] == feed_source["content_sha256"] and news[0]["snapshot"] == feed_source["snapshot"]
    assert "authorized distributor of Beta Optics" in part["notes"] and "exclusive dealer for Gamma Systems" in part["notes"]
    assert "test fixture" in company["notes"]


def test_missing_values_are_filled_from_the_site_with_field_sources(work: Path) -> None:
    runs, built = enrich(work)
    _, company = by_name(built, "Test Harness Labs")  # its site was down: nothing filled, the failure is noted
    assert "could not be read" in company["notes"] and "connection refused" in company["notes"] and "website" not in company
    _, company = by_name(built, "Sample Cyber Range LLC")
    home = next(sid for sid, r in runs[2].records if r["record_type"] == "profile")
    assert company["website"] == "https://cyber.example.net/home" and company["description"] == "Synthetic cyber ranges."
    assert company["field_sources"] == {"website": [home], "description": [home]} and home in company["source_ids"]
    _, company = by_name(built, "Sample Mobility Works")
    assert "No official website identified (test fixture): no site found in the fixture" in company["notes"]


def test_new_package_is_valid_and_the_previous_one_is_untouched(work: Path) -> None:
    before = {p.name: p.read_bytes() for p in (work / "data/packages/sample-fair/2026" / V2.name).iterdir()}
    code = main(["--package", f"data/packages/sample-fair/2026/{V2.name}", "--targets", "targets.json", "--created-at", "2026-11-12T09:00:00Z"],
                fetcher=FakeFetcher(SCRIPT))
    assert code == 0
    new = work / "data/packages/sample-fair/2026/sample-fair-2026.20261112T090000Z"
    assert validate_package(new).ok, validate_package(new).text()
    manifest = read_package(new).manifest
    assert manifest["previous_dataset_id"] == V2.name and manifest["completeness_status"] == read_package(V2).manifest["completeness_status"]
    assert {p.name: p.read_bytes() for p in (work / "data/packages/sample-fair/2026" / V2.name).iterdir()} == before
    changes = read_package(new).records["changes"]
    assert changes and all(c["change_type"] == "modified" for c in changes)
    statuses = sorted(r["status"] for r in read_package(new).records["crawl_runs"])
    assert "failed" in statuses  # the failed site visit is kept as a record


def test_a_target_not_in_the_package_is_refused(work: Path) -> None:
    bad = {**TARGETS, "targets": [], "not_found": [{"exhibitor_name_as_listed": "Nobody", "reason": "x"}]}
    with pytest.raises(EnrichError, match="not an exhibitor"):
        build_enriched(work / "data/packages/sample-fair/2026" / V2.name, [], bad, created_at=CREATED)


@pytest.mark.parametrize("data, message", [
    ({"targets": []}, "identified"),
    ({"identified": "x", "targets": [{"homepage": "h"}]}, "targets\\[0\\]"),
    ({"identified": "x", "targets": [], "news_months": 0}, "news_months"),
    ({"identified": "x", "targets": [], "news_keywords": "x"}, "news_keywords"),
    ({"identified": "x", "targets": [], "not_found": [{"exhibitor_name_as_listed": "a"}]}, "not_found\\[0\\]"),
    ({"identified": "x", "targets": [{"exhibitor_name_as_listed": "a", "homepage": "h", "allowed_domains": ["d"]}],
      "not_found": [{"exhibitor_name_as_listed": "a", "reason": "r"}]}, "twice"),
])
def test_bad_targets_files(tmp_path: Path, data, message) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(EnrichError, match=message):
        load_targets(path)
