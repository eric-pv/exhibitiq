"""Tests for crawler.runlog (D1-07).

The contract test builds a crawl_run record and validates it against the real
``schemas/v1/crawl_run.schema.json``. The small registry helper below exists
only for these tests; the project's single data-package validator is a
separate work item (D1-05) and does not use this helper.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from crawler.errors import CrawlError, ErrorCode
from crawler.runlog import MAX_ERROR_SAMPLES, RunLog, format_utc

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "v1"
T0 = datetime(2026, 11, 3, 6, 0, 0, tzinfo=timezone.utc)
RUN_ID = "run_01JCR000000000000000000001"  # synthetic ID taken from the contract examples


def make_log(start: datetime = T0) -> tuple[RunLog, io.StringIO]:
    stream = io.StringIO()
    ticks = iter(start + timedelta(seconds=i) for i in range(10_000))
    return RunLog(stream, clock=lambda: next(ticks)), stream


def lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def crawl_run_validator() -> Draft202012Validator:
    registry = Registry()
    for path in SCHEMA_DIR.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema, DRAFT202012))
    schema = json.loads((SCHEMA_DIR / "crawl_run.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=registry)


def build(log: RunLog, **overrides) -> dict:
    kwargs = dict(
        crawl_run_id=RUN_ID,
        exhibition_id="example-expo",
        edition_id="example-expo-2026",
        crawler_name="example-crawler",
        crawler_version="0.0.0",
        trigger="manual",
        started_at=T0,
        finished_at=T0 + timedelta(minutes=5),
        status="succeeded",
    )
    kwargs.update(overrides)
    return log.build_crawl_run(**kwargs)


def test_format_utc_requires_timezone_and_converts() -> None:
    assert format_utc(T0) == "2026-11-03T06:00:00Z"
    taipei = timezone(timedelta(hours=8))
    assert format_utc(datetime(2026, 11, 3, 14, 0, 0, tzinfo=taipei)) == "2026-11-03T06:00:00Z"
    with pytest.raises(ValueError):
        format_utc(datetime(2026, 11, 3, 6, 0, 0))


def test_event_lines_are_canonical_jsonl() -> None:
    log, stream = make_log()
    log.event("INFO", "started", "開始擷取", zeta=1, alpha="é")
    raw = stream.getvalue()
    assert raw.endswith("\n") and raw.count("\n") == 1
    assert raw == '{"alpha":"é","event":"started","level":"INFO","message":"開始擷取","ts":"2026-11-03T06:00:00Z","zeta":1}\n'


def test_invalid_level_and_reserved_fields_are_rejected() -> None:
    log, _ = make_log()
    with pytest.raises(ValueError):
        log.event("TRACE", "x")
    with pytest.raises(ValueError, match="reserved"):
        log.event("INFO", "x", ts="now")


def test_counters_and_events() -> None:
    log, stream = make_log()
    log.log_request("https://www.example.com/a", succeeded=True, http_status=200)
    log.log_request("https://www.example.com/b", succeeded=False, http_status=500)
    log.log_records(2, page=1)
    log.log_error(CrawlError(ErrorCode.HTTP_ERROR, "bad status", url="https://www.example.com/b", http_status=500))
    assert log.stats() == {
        "requests_attempted": 2,
        "requests_succeeded": 1,
        "records_extracted": 2,
        "error_count": 1,
    }
    events = lines(stream)
    assert [(e["event"], e["level"]) for e in events] == [
        ("request", "INFO"),
        ("request", "WARNING"),
        ("records_extracted", "INFO"),
        ("error", "ERROR"),
    ]
    assert events[3]["http_status"] == 500 and events[3]["retryable"] is False


def test_log_error_fills_occurred_at_from_the_clock() -> None:
    log, _ = make_log()
    log.log_error(CrawlError(ErrorCode.TIMEOUT, "slow"))
    assert log.error_samples()[0]["occurred_at"] == "2026-11-03T06:00:00Z"


@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_log_records_rejects_bad_counts(count) -> None:
    log, _ = make_log()
    with pytest.raises(ValueError):
        log.log_records(count)


def test_error_samples_are_capped_but_error_count_keeps_counting() -> None:
    log, _ = make_log()
    for i in range(MAX_ERROR_SAMPLES + 5):
        log.log_error(CrawlError(ErrorCode.PARSE_ERROR, f"error {i}"))
    assert len(log.error_samples()) == MAX_ERROR_SAMPLES
    assert log.stats()["error_count"] == MAX_ERROR_SAMPLES + 5


def test_built_record_validates_against_the_real_crawl_run_schema() -> None:
    log, _ = make_log()
    log.log_request("https://www.example.com/a", succeeded=True, http_status=200)
    log.log_records(2)
    record = build(log)
    assert list(crawl_run_validator().iter_errors(record)) == []
    assert "error_samples" not in record and "notes" not in record  # omitted, never null/empty


def test_record_with_errors_and_optional_fields_validates() -> None:
    log, _ = make_log()
    log.log_request("https://www.example.com/a", succeeded=False, http_status=503)
    log.log_error(CrawlError(ErrorCode.HTTP_ERROR, "bad status", url="https://www.example.com/a", http_status=503))
    record = build(
        log,
        status="partial",
        code_commit="a" * 40,
        github_run_url="https://github.com/example/repo/actions/runs/1",
        notes="合成測試資料",
    )
    assert list(crawl_run_validator().iter_errors(record)) == []
    assert record["error_samples"][0]["code"] == "http_error"


def test_error_samples_cap_matches_the_contract() -> None:
    log, _ = make_log()
    for i in range(MAX_ERROR_SAMPLES + 1):
        log.log_error(CrawlError(ErrorCode.PARSE_ERROR, f"error {i}"))
    record = build(log, status="failed")
    assert len(record["error_samples"]) == MAX_ERROR_SAMPLES
    assert list(crawl_run_validator().iter_errors(record)) == []


def test_validator_helper_actually_rejects_bad_records() -> None:
    """Guards against the contract test passing vacuously."""
    log, _ = make_log()
    record = build(log, status="done")  # not an allowed status
    assert list(crawl_run_validator().iter_errors(record)) != []
