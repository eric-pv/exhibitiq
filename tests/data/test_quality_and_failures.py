"""Data quality and source failure tests (D4-07).

Each source-failure scenario runs the real chain — runner -> evidence store -> quality gate -> dataset index — next to a
valid package that already exists for the edition, and checks the outcomes that matter to a user of the data:

- the failure is recorded (crawl_run status, error code, a valid crawl_run record, a complete evidence directory);
- whatever the source did answer is kept as evidence, even when it could not be parsed;
- a blocked source is asked once and never worked around;
- the quality gate refuses to let the acquisition become a package unseen;
- the existing valid package stays the edition's latest, and the index says what happened.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from crawler.errors import ErrorCode
from crawler.fetch import FetchError
from crawler.file_import import ADAPTER_NAME, FileImportAdapter
from crawler.models import Response
from crawler.runner import RunOptions, run_source
from crawler.store import RunStore, verify_run
from etl.assemble import assemble_package
from etl.changes import carry_forward
from etl.dataset_index import build_index, validate_index
from etl.package import read_package
from etl.quality import CODES, QualityFinding, blocked, check_acquisition
from etl.report import build_report
from etl.schema_registry import SchemaSet
from tests.data.crawl_testkit import T0, FakeClock, FakeFetcher, fixed_rand, make_config
from tests.data.test_assemble import COLUMNS, CSV, ORIGIN, pipeline

SCHEMAS = SchemaSet()
LATER = T0 + timedelta(days=2)
GENERATOR = {"name": "exhibitiq-etl", "version": "1.0.0"}
HEADER = b"Company,Booth,Country,Site\n"


def config(fmt: str = "csv"):
    return make_config(name="imp", adapter=ADAPTER_NAME, start_urls=(ORIGIN,), allowed_domains=("example.com",), source_type="csv_import",
                       max_retries=2, options={"mapping": {"format": fmt, "columns": COLUMNS}})


def csv(body: bytes, media: str = "text/csv") -> Response:
    return Response(ORIGIN, ORIGIN, 200, {}, body, media)


@pytest.fixture()
def edition(tmp_path: Path) -> dict[str, Any]:
    """An edition with one valid package (2 listed participations from the shared CSV)."""
    fixed_rand.counter = 0
    kwargs = pipeline(tmp_path)
    package = assemble_package(tmp_path / "packages", **kwargs)
    return {"root": tmp_path / "packages", "package": package, "kwargs": kwargs, "tmp": tmp_path}


def acquire(tmp_path: Path, answer: Any, *, fmt: str = "csv"):
    """Run the import source once more, two days later, with the evidence store as sink."""
    cfg = config(fmt)
    fetcher = FakeFetcher({ORIGIN: answer})
    store = RunStore(tmp_path / "raw2", cfg)
    result = run_source(cfg, FileImportAdapter(), fetcher, clock=FakeClock(LATER), options=RunOptions(respect_robots=False, backoff_base_seconds=0.0),
                        rand=fixed_rand, sink=store)
    run_dir = store.finalize(result)
    return result, fetcher, run_dir


SCENARIOS = {
    # name: (answer, format, expected status, expected error codes, responses that arrived)
    "403 access blocked": (403, "csv", "failed", {ErrorCode.ACCESS_BLOCKED}, 0),
    "429 rate limited": (429, "csv", "failed", {ErrorCode.ACCESS_BLOCKED}, 0),
    "404 list removed": (404, "csv", "failed", {ErrorCode.HTTP_ERROR}, 0),
    "500 server error after retries": (500, "csv", "failed", {ErrorCode.HTTP_ERROR}, 0),
    "timeout": (FetchError(ErrorCode.TIMEOUT, "timed out", retryable=True), "csv", "failed", {ErrorCode.TIMEOUT}, 0),
    "network down": (FetchError(ErrorCode.NETWORK_ERROR, "connection refused", retryable=True), "csv", "failed", {ErrorCode.NETWORK_ERROR}, 0),
    "redirect off the allowed domains": (Response(ORIGIN, "https://elsewhere.example.org/list.csv", 200, {}, CSV.encode(), "text/csv"), "csv", "failed", None, 0),
    "empty body": (csv(b""), "csv", "partial", {ErrorCode.PARSE_ERROR}, 1),
    "columns renamed": (csv(b"Name,Stand\nA,1\n"), "csv", "partial", {ErrorCode.PARSE_ERROR}, 1),
    "not text": (csv(b"\xff\xfe\x00garbage"), "csv", "partial", {ErrorCode.PARSE_ERROR}, 1),
    "html table gone": (csv(b"<html><body>no table</body></html>", "text/html"), "html_table", "partial", {ErrorCode.PARSE_ERROR}, 1),
    # the dangerous ones: the source answers 200 and the run "succeeds" with nothing in it
    "header only": (csv(HEADER), "csv", "succeeded", set(), 1),
    "names blank": (csv(HEADER + b",A1,,\n  ,B2,,\n"), "csv", "succeeded", set(), 1),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_source_failure_is_recorded_kept_gated_and_does_not_replace_good_data(edition: dict[str, Any], name: str) -> None:
    answer, fmt, status, error_codes, arrived = SCENARIOS[name]
    result, fetcher, run_dir = acquire(edition["tmp"], answer, fmt=fmt)
    run = result.crawl_run

    # recorded
    assert result.status == status and run["status"] == status
    if error_codes is not None:
        assert {e.code for e in result.errors} == error_codes
    assert SCHEMAS.errors("crawl_run", run) == []
    assert verify_run(run_dir) == []
    assert run["stats"]["records_extracted"] == 0 and result.records == []

    # kept: a response that arrived is stored as evidence, even if it could not be parsed
    snapshots = list((run_dir / "snapshots").iterdir()) if (run_dir / "snapshots").is_dir() else []
    assert len(snapshots) == arrived
    if arrived:
        assert snapshots[0].read_bytes() == answer.content

    # never worked around: a block is asked exactly once (no retry, no other URL)
    if error_codes == {ErrorCode.ACCESS_BLOCKED}:
        assert fetcher.calls == [ORIGIN]

    # gated: nothing listed -> block (Q2); a failed run -> block (Q1)
    previous = read_package(edition["package"].path)
    carried = carry_forward(previous.records, companies=[], participations=[], sources=[], crawl_runs=[run])
    findings = check_acquisition([run], carried.participations, previous_participations=previous.records["participations"])
    codes = {f.code for f in findings if f.level == "block"}
    assert blocked(findings) and "Q2" in codes and "Q3" in codes
    assert ("Q1" in codes) == (status == "failed")

    # good data stays: the existing package is still the latest, the index explains what happened
    index = build_index(edition["root"], generated_at=LATER + timedelta(hours=1), generator=GENERATOR, extra_runs=[run])
    assert validate_index(index, packages_root=edition["root"]) == []
    ed = index["exhibitions"][0]["editions"][0]
    assert ed["latest_dataset_id"] == edition["package"].manifest["dataset_id"]
    last = ed["last_acquisition"]
    assert (last["crawl_run_id"], last["status"], last["records_extracted"]) == (run["crawl_run_id"], status, 0) and "dataset_id" not in last
    if status == "failed":
        assert last["notes"].startswith("failed:") and any(n["level"] == "warning" and "failed" in n["message"] for n in index["notices"])
    if status == "partial":
        assert last["notes"].startswith("partial:")


def test_the_previous_package_is_never_touched_by_a_failed_acquisition(edition: dict[str, Any]) -> None:
    path = Path(edition["package"].path)
    before = {p.name: p.read_bytes() for p in path.iterdir()}
    for name in ("403 access blocked", "header only"):
        answer, fmt, *_ = SCENARIOS[name]
        acquire(edition["tmp"] / name.replace(" ", "-"), answer, fmt=fmt)
    assert {p.name: p.read_bytes() for p in path.iterdir()} == before


# --------------------------------------------------------------------------------------- quality gate


def part(n: int, status: str = "listed") -> dict[str, Any]:
    return {"participation_id": f"pt_{n}", "listing_status": status}


def run_record(status: str = "succeeded", extracted: int = 3, **kw: Any) -> dict[str, Any]:
    return {"crawl_run_id": kw.pop("crawl_run_id", "run_1"), "status": status, "stats": {"records_extracted": extracted, "error_count": kw.pop("errors", 0)}, **kw}


def codes_of(findings: list[QualityFinding], level: str | None = None) -> list[str]:
    return [f.code for f in findings if level is None or f.level == level]


def test_a_normal_acquisition_passes() -> None:
    assert check_acquisition([run_record()], [part(1), part(2), part(3)]) == []
    assert check_acquisition([run_record()], [part(1), part(2), part(3)], previous_participations=[part(1), part(2)]) == []  # growth is fine


@pytest.mark.parametrize("before, after, expected", [(10, 5, False), (10, 4, True), (3, 1, True), (2, 1, False), (1, 0, True), (0, 0, False)])
def test_q3_blocks_a_drop_of_more_than_half(before: int, after: int, expected: bool) -> None:
    findings = check_acquisition([run_record(extracted=after)], [part(i) for i in range(after)], previous_participations=[part(i) for i in range(before)])
    assert ("Q3" in codes_of(findings, "block")) is expected


def test_q3_counts_only_listed_and_the_threshold_is_configurable() -> None:
    previous = [part(1), part(2), part(3), part(4, "removed")]
    current = [part(1), part(2, "removed"), part(3, "removed"), part(4, "removed")]  # carried forward: 3 listed -> 1
    assert "Q3" in codes_of(check_acquisition([run_record(extracted=1)], current, previous_participations=previous), "block")
    assert "Q3" not in codes_of(check_acquisition([run_record(extracted=1)], current, previous_participations=previous, max_drop_ratio=0.9))
    with pytest.raises(ValueError, match="max_drop_ratio"):
        check_acquisition([run_record()], current, max_drop_ratio=1.0)


def test_q1_q2_q4_q5() -> None:
    failed = run_record("failed", 0, error_samples=[{"code": "access_blocked", "message": "HTTP 403 for x"}])
    findings = check_acquisition([failed], [])
    assert codes_of(findings, "block") == ["Q1", "Q2"] and "HTTP 403 for x" in findings[0].message
    assert codes_of(check_acquisition([run_record("cancelled", 0)], []), "block") == ["Q1", "Q2"]
    partial = check_acquisition([run_record("partial", 2, errors=1, notes="cut short")], [part(1), part(2)])
    assert [(f.code, f.level) for f in partial] == [("Q4", "warn")] and "cut short" in partial[0].message
    merged = check_acquisition([run_record(extracted=3)], [part(1), part(2)])
    assert [(f.code, f.level) for f in merged] == [("Q5", "warn")]


def test_a_person_can_accept_a_block_and_it_stays_visible() -> None:
    findings = check_acquisition([run_record(extracted=1)], [part(1)], previous_participations=[part(i) for i in range(5)], accept={"Q3"})
    q3 = next(f for f in findings if f.code == "Q3")
    assert q3.level == "warn" and q3.accepted and "accepted by a person" in q3.message and not blocked(findings)
    assert q3.to_dict() == {"code": "Q3", "level": "warn", "message": q3.message, "accepted": True}
    still = check_acquisition([run_record("failed", 0)], [], accept={"Q3"})
    assert blocked(still)  # accepting one code does not accept the others
    with pytest.raises(ValueError, match="unknown quality codes"):
        check_acquisition([run_record()], [part(1)], accept={"Q9"})
    with pytest.raises(ValueError, match="at least one crawl run"):
        check_acquisition([], [part(1)])
    assert CODES == ("Q1", "Q2", "Q3", "Q4", "Q5")


def test_the_shared_csv_pipeline_passes_the_gate_with_only_the_merge_warning(tmp_path: Path) -> None:
    fixed_rand.counter = 0
    kwargs = pipeline(tmp_path)
    findings = check_acquisition(kwargs["crawl_runs"], kwargs["participations"])
    assert [(f.code, f.level) for f in findings] == [("Q5", "warn")]  # 3 rows, 2 companies: SYNTHETIC OPTICS LTD is the same company


# ------------------------------------------------------------------------------- data quality in packages


def test_report_flags_an_official_count_the_listing_does_not_reach(edition: dict[str, Any]) -> None:
    from etl.assemble import OfficialCount

    kwargs = dict(edition["kwargs"], created_at=edition["kwargs"]["created_at"] + timedelta(hours=1))
    package = assemble_package(edition["root"], **kwargs, official_count=OfficialCount(5, kwargs["sources"][0]["source_id"]))
    report = build_report(package.path)
    assert report["completeness"]["status"] == "partial" and report["completeness"]["official_exhibitor_count"] == 5
    assert "The official count is 5 but 2 listed participations were collected (difference +3)." in report["gaps"]
    assert {"flag": "companies_without_website", "count": 1} in report["quality_flags"]


def test_report_flags_a_package_without_an_official_count(edition: dict[str, Any]) -> None:
    report = build_report(edition["package"].path)
    assert any("No official exhibitor count" in g for g in report["gaps"])
